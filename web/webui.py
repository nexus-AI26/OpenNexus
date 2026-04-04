import json
import logging
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from providers import get_provider
from config import Config, SKILLS_DIR, augment_system_prompt
from bot.handlers import (
    user_contexts,
    user_providers,
    user_system_prompts,
    _execute_shell_and_reply,
    _get_gen_control,
    enqueue_generation_note,
    request_generation_stop,
)
from skills.manager import SkillManager
from tools.search import web_search

logger = logging.getLogger("opennexus.web")

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

VALID_PROVIDERS = frozenset(
    {"anthropic", "openai", "openrouter", "groq", "ollama", "custom"}
)


class ChatRequest(BaseModel):
    message: str


class WaitNoteRequest(BaseModel):
    message: str


class ModelBody(BaseModel):
    provider: str
    model: str


class SystemPromptBody(BaseModel):
    prompt: str


class SearchBody(BaseModel):
    query: str


class DummyUser:
    def __init__(self, uid: int) -> None:
        self.id = uid


class DummyUpdate:
    def __init__(self, uid: int) -> None:
        self.effective_user = DummyUser(uid)
        self.message = None


def create_app(config: Config) -> FastAPI:
    app = FastAPI(title="OpenNexus")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.get("/api/info")
    def info():
        uid = config.owner_id
        if uid in user_providers:
            prov, model = user_providers[uid]
        else:
            prov = config.default_provider
            model = config.providers.get(prov, {}).get("default_model", "unknown")
        return {
            "provider": prov,
            "model": model,
            "owner_id": config.owner_id,
        }

    @app.get("/api/providers")
    def providers_catalog():
        rows = []
        for name, pc in config.providers.items():
            rows.append(
                {
                    "id": name,
                    "default_model": pc.get("default_model", ""),
                    "configured": bool(pc.get("api_key"))
                    or name in ("ollama", "custom"),
                }
            )
        return {"providers": rows, "default_provider": config.default_provider}

    @app.get("/api/model")
    def get_model():
        uid = config.owner_id
        if uid in user_providers:
            p, m = user_providers[uid]
            return {"provider": p, "model": m}
        p = config.default_provider
        m = config.providers.get(p, {}).get("default_model", "")
        return {"provider": p, "model": m}

    @app.post("/api/model")
    def set_model(body: ModelBody):
        p = body.provider.strip().lower()
        if p not in VALID_PROVIDERS:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown provider. Use: {', '.join(sorted(VALID_PROVIDERS))}",
            )
        user_providers[config.owner_id] = (p, body.model.strip())
        return {"provider": p, "model": body.model.strip()}

    @app.get("/api/system-prompt")
    def get_system_prompt():
        uid = config.owner_id
        return {"prompt": user_system_prompts.get(uid, config.system_prompt)}

    @app.post("/api/system-prompt")
    def set_system_prompt(body: SystemPromptBody):
        raw = (body.prompt or "").strip()
        if not raw:
            raise HTTPException(status_code=400, detail="prompt is empty")
        uid = config.owner_id
        user_system_prompts[uid] = augment_system_prompt(raw)
        return {"status": "ok"}

    @app.get("/api/tokens")
    def token_stats():
        uid = config.owner_id
        hist = user_contexts.get(uid, [])
        total_chars = sum(len(m.get("content", "")) for m in hist)
        return {
            "messages": len(hist),
            "chars": total_chars,
            "approx_tokens": total_chars // 4,
        }

    @app.post("/api/search")
    async def search_api(body: SearchBody):
        q = (body.query or "").strip()
        if not q:
            return {"results": []}
        results = await web_search(q)
        return {"results": results or []}

    @app.get("/api/skills")
    def get_skills():
        mgr = SkillManager(SKILLS_DIR)
        return {"skills": mgr.list_skills()}

    @app.delete("/api/skills/{skill_id}")
    def delete_skill(skill_id: str):
        mgr = SkillManager(SKILLS_DIR)
        mgr.delete_skill(skill_id)
        return {"status": "deleted"}

    @app.post("/api/clear")
    def clear_context():
        user_id = config.owner_id
        user_contexts.pop(user_id, None)
        return {"status": "cleared"}

    @app.post("/api/chat/stop")
    def chat_stop():
        user_id = config.owner_id
        request_generation_stop(user_id)
        return {"status": "stop_requested"}

    @app.post("/api/chat/wait")
    def chat_wait(body: WaitNoteRequest):
        user_id = config.owner_id
        note = (body.message or "").strip()
        if not note:
            return {"status": "ignored", "reason": "empty"}
        enqueue_generation_note(user_id, note)
        return {"status": "queued"}

    @app.get("/api/history")
    def get_history():
        user_id = config.owner_id
        return {"history": user_contexts.get(user_id, [])}

    @app.post("/api/chat")
    async def chat(request: ChatRequest):
        user_id = config.owner_id
        text = request.message

        if user_id not in user_contexts:
            user_contexts[user_id] = []

        user_contexts[user_id].append({"role": "user", "content": text})

        ctrl = _get_gen_control(user_id)
        ctrl.stop_requested = False
        while ctrl.pending_notes:
            note = ctrl.pending_notes.pop(0)
            user_contexts[user_id].append({
                "role": "system",
                "content": "[User note:]\n" + note,
            })

        prov_name = config.default_provider
        model = config.providers.get(prov_name, {}).get("default_model", "")
        if user_id in user_providers:
            prov_name, model = user_providers[user_id]

        provider_cfg = config.providers.get(prov_name, {})
        provider = get_provider(prov_name, provider_cfg)

        base_system = user_system_prompts.get(user_id, config.system_prompt)
        system_prompt = base_system + (
            "\n\nIf you need to execute a shell command to fulfill the request, "
            "output exactly `<execute>the command</execute>`. "
            "Wait for the system result before continuing. DO NOT hallucinate command outputs."
        )
        skill_mgr = SkillManager(SKILLS_DIR)
        extra = skill_mgr.build_skill_injection(text, system_prompt)
        if extra:
            system_prompt += extra

        async def agent_loop():
            max_turns = 5
            user_aborted = False
            for turn in range(max_turns):
                if user_aborted:
                    break
                turn_segments: list[str] = []
                stopped = False

                while True:
                    current_stream = ""
                    restart_stream = False
                    try:
                        async for chunk in provider.complete(
                            messages=user_contexts[user_id],
                            model=model,
                            system=system_prompt,
                            stream=True,
                        ):
                            current_stream += chunk

                            if ctrl.stop_requested:
                                ctrl.stop_requested = False
                                stopped = True
                                break

                            if ctrl.pending_notes:
                                if current_stream.strip():
                                    user_contexts[user_id].append({
                                        "role": "assistant",
                                        "content": current_stream,
                                    })
                                    turn_segments.append(current_stream)
                                while ctrl.pending_notes:
                                    note = ctrl.pending_notes.pop(0)
                                    user_contexts[user_id].append({
                                        "role": "system",
                                        "content": (
                                            "[User interjection while you were replying — continue and apply this:]\n"
                                            + note
                                        ),
                                    })
                                restart_stream = True
                                break

                            yield json.dumps({"type": "chunk", "content": chunk}) + "\n"
                    except Exception as e:
                        yield json.dumps({"type": "error", "content": str(e)}) + "\n"
                        user_aborted = True
                        break

                    if stopped:
                        agg = "".join(turn_segments) + current_stream
                        if current_stream.strip():
                            user_contexts[user_id].append({
                                "role": "assistant",
                                "content": current_stream + "\n\n[Generation stopped by user.]",
                            })
                        elif turn_segments:
                            user_contexts[user_id].append({
                                "role": "system",
                                "content": "[User stopped generation.]",
                            })
                        yield json.dumps({"type": "stopped", "text": agg}) + "\n"
                        user_aborted = True
                        break

                    if restart_stream:
                        continue

                    if current_stream.strip():
                        user_contexts[user_id].append({
                            "role": "assistant",
                            "content": current_stream,
                        })
                        turn_segments.append(current_stream)
                    break

                if user_aborted:
                    break

                full_response = "".join(turn_segments)
                match = re.search(r'<execute>(.*?)</execute>', full_response, re.DOTALL)
                if match:
                    cmd = match.group(1).strip()
                    yield json.dumps({"type": "execution_start", "command": cmd}) + "\n"

                    dummy = DummyUpdate(user_id)
                    output = await _execute_shell_and_reply(dummy, cmd, bypass_allowlist=True)
                    sys_msg = f"[SYSTEM COMMAND EXECUTION RESULT: {cmd}]\n{output}"
                    user_contexts[user_id].append({"role": "system", "content": sys_msg})
                    yield json.dumps({"type": "execution_result", "output": output, "command": cmd}) + "\n"
                else:
                    break

            yield json.dumps({"type": "done"}) + "\n"

        return StreamingResponse(
            agent_loop(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    return app
