import json
from typing import AsyncGenerator, Any

import httpx

from providers.base import BaseProvider


class OpenAIProvider(BaseProvider):
    name = "openai"
    base_url = "https://api.openai.com/v1"
    auth_header = "Authorization"
    auth_prefix = "Bearer"

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        system: str | None = None,
        stream: bool = True,
    ) -> AsyncGenerator[str, None]:
        self.validate_url()
        url = f"{self.base_url}/chat/completions"
        model = model or self.default_model

        full_messages: list[dict[str, str]] = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        body: dict[str, Any] = {
            "model": model,
            "messages": full_messages,
            "stream": stream,
        }

        headers = self.get_headers()

        async with httpx.AsyncClient(timeout=120.0) as client:
            if stream:
                async with client.stream(
                    "POST", url, json=body, headers=headers
                ) as resp:
                    if resp.status_code != 200:
                        error_body = await resp.aread()
                        raise RuntimeError(
                            f"[{self.name}] HTTP {resp.status_code}: "
                            f"{error_body.decode(errors='replace')}"
                        )
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        choices = event.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
            else:
                resp = await client.post(url, json=body, headers=headers)
                if resp.status_code != 200:
                    raise RuntimeError(
                        f"[{self.name}] HTTP {resp.status_code}: {resp.text}"
                    )
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    yield choices[0].get("message", {}).get("content", "")
