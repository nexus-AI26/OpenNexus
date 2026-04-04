import json
import logging
import re
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from providers import get_provider
from config import Config
from bot.handlers import user_contexts, user_providers, _execute_shell_and_reply

logger = logging.getLogger("opennexus.web")

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

class ChatRequest(BaseModel):
    message: str

class DummyUser:
    def __init__(self, uid): self.id = uid

class DummyUpdate:
    def __init__(self, uid):
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
        prov = config.default_provider
        model = config.providers.get(prov, {}).get("default_model", "unknown")
        return {"provider": prov, "model": model, "owner_id": config.owner_id}

    @app.get("/api/skills")
    def get_skills():
        from skills.manager import SkillManager
        from config import SKILLS_DIR
        mgr = SkillManager(SKILLS_DIR)
        return {"skills": mgr.list_skills()}

    @app.delete("/api/skills/{skill_id}")
    def delete_skill(skill_id: str):
        from skills.manager import SkillManager
        from config import SKILLS_DIR
        mgr = SkillManager(SKILLS_DIR)
        mgr.delete_skill(skill_id)
        return {"status": "deleted"}

    @app.post("/api/clear")
    def clear_context():
        user_id = config.owner_id
        user_contexts.pop(user_id, None)
        return {"status": "cleared"}

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

        prov_name = config.default_provider
        model = config.providers.get(prov_name, {}).get("default_model", "")
        if user_id in user_providers:
            prov_name, model = user_providers[user_id]

        provider_cfg = config.providers.get(prov_name, {})
        provider = get_provider(prov_name, provider_cfg)

        system_prompt = config.system_prompt
        system_prompt += (
            "\n\nIf you need to execute a shell command to fulfill the request, "
            "output exactly `<execute>the command</execute>`. "
            "Wait for the system result before continuing. DO NOT hallucinate command outputs."
        )

        async def agent_loop():
            max_turns = 5
            for turn in range(max_turns):
                full_response = ""
                try:
                    async for chunk in provider.complete(
                        messages=user_contexts[user_id],
                        model=model,
                        system=system_prompt,
                        stream=True,
                    ):
                        full_response += chunk
                        yield json.dumps({"type": "chunk", "content": chunk}) + "\n"
                except Exception as e:
                    yield json.dumps({"type": "error", "content": str(e)}) + "\n"
                    break

                match = re.search(r'<execute>(.*?)</execute>', full_response, re.DOTALL)
                if match:
                    cmd = match.group(1).strip()
                    user_contexts[user_id].append({"role": "assistant", "content": full_response})
                    yield json.dumps({"type": "execution_start", "command": cmd}) + "\n"

                    dummy = DummyUpdate(user_id)
                    output = await _execute_shell_and_reply(dummy, cmd, bypass_allowlist=True)
                    sys_msg = f"[SYSTEM COMMAND EXECUTION RESULT: {cmd}]\n{output}"
                    user_contexts[user_id].append({"role": "system", "content": sys_msg})
                    yield json.dumps({"type": "execution_result", "output": output, "command": cmd}) + "\n"
                else:
                    user_contexts[user_id].append({"role": "assistant", "content": full_response})
                    break

            yield json.dumps({"type": "done"}) + "\n"

        return StreamingResponse(agent_loop(), media_type="application/x-ndjson")

    return app
