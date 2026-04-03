import json
from typing import AsyncGenerator, Any

import httpx

from providers.base import BaseProvider


class AnthropicProvider(BaseProvider):
    name = "anthropic"
    base_url = "https://api.anthropic.com/v1"
    auth_header = "x-api-key"
    auth_prefix = ""

    def get_headers(self) -> dict[str, str]:
        headers = super().get_headers()
        headers["anthropic-version"] = "2023-06-01"
        return headers

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        system: str | None = None,
        stream: bool = True,
    ) -> AsyncGenerator[str, None]:
        self.validate_url()
        url = f"{self.base_url}/messages"
        model = model or self.default_model

        body: dict[str, Any] = {
            "model": model,
            "max_tokens": 4096,
            "messages": messages,
            "stream": stream,
        }
        if system:
            body["system"] = system

        headers = self.get_headers()

        async with httpx.AsyncClient(timeout=120.0) as client:
            if stream:
                async with client.stream(
                    "POST", url, json=body, headers=headers
                ) as resp:
                    if resp.status_code != 200:
                        error_body = await resp.aread()
                        raise RuntimeError(
                            f"[anthropic] HTTP {resp.status_code}: "
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
                        event_type = event.get("type", "")
                        if event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            text = delta.get("text", "")
                            if text:
                                yield text
                        elif event_type == "message_stop":
                            break
            else:
                resp = await client.post(url, json=body, headers=headers)
                if resp.status_code != 200:
                    raise RuntimeError(
                        f"[anthropic] HTTP {resp.status_code}: {resp.text}"
                    )
                data = resp.json()
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        yield block.get("text", "")
