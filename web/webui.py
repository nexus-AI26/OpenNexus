import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from providers import get_provider
from config import Config
from bot.handlers import user_contexts, user_providers, _execute_shell_and_reply

logger = logging.getLogger("opennexus.web")

class ChatRequest(BaseModel):
    user_id: int
    message: str

def create_app(config: Config) -> FastAPI:
    app = FastAPI(title="OpenNexus")
    
    app.mount("/static", StaticFiles(directory="web/static"), name="static")

    @app.get("/")
    def index():
        return FileResponse("web/static/index.html")

    @app.post("/api/chat")
    async def chat(request: ChatRequest):
        user_id = request.user_id
        if user_id not in config.allowed_users:
            raise HTTPException(status_code=403, detail="Unauthorized user.")
            
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
        # Add instruction for autonomous execution
        system_prompt += "\n\nIf you need to execute a shell command to fulfill the request, output exactly `<execute>the command</execute>`. Wait for the system result before continuing. DO NOT hallucinate command outputs."

        async def agent_loop():
            max_turns = 5
            for turn in range(max_turns):
                full_response = ""
                async for chunk in provider.complete(
                    messages=user_contexts[user_id],
                    model=model,
                    system=system_prompt,
                    stream=True,
                ):
                    full_response += chunk
                    yield json.dumps({"type": "chunk", "content": chunk}) + "\n"
                
                # Check for <execute> tag
                import re
                match = re.search(r'<execute>(.*?)</execute>', full_response, re.DOTALL)
                if match:
                    cmd = match.group(1).strip()
                    user_contexts[user_id].append({"role": "assistant", "content": full_response})
                    yield json.dumps({"type": "execution_start", "command": cmd}) + "\n"
                    
                    # Execute
                    # bypass_allowlist for owner only, else check. But since web UI is owner mainly... let's just use the function
                    class DummyUpdate:
                        class DummyUser:
                            id = request.user_id
                        effective_user = DummyUser()
                        message = None
                        
                    output = await _execute_shell_and_reply(DummyUpdate(), cmd, bypass_allowlist=(user_id == config.owner_id))
                    sys_msg = f"[SYSTEM COMMAND EXECUTION RESULT: {cmd}]\n{output}"
                    user_contexts[user_id].append({"role": "system", "content": sys_msg})
                    yield json.dumps({"type": "execution_result", "output": sys_msg}) + "\n"
                    # continue loop to let AI respond to result
                else:
                    user_contexts[user_id].append({"role": "assistant", "content": full_response})
                    break # no execution, we are done
            
            yield json.dumps({"type": "done"}) + "\n"

        return StreamingResponse(agent_loop(), media_type="application/x-ndjson")

    return app
