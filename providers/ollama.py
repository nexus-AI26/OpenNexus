from typing import Any

from providers.openai import OpenAIProvider


class OllamaProvider(OpenAIProvider):
    name = "ollama"
    base_url = "http://localhost:11434/v1"
    auth_header = ""
    auth_prefix = ""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        if not self.base_url:
            self.base_url = "http://localhost:11434/v1"

    def validate_url(self) -> None:
        if not self.base_url:
            raise ValueError(f"[{self.name}] base_url is not configured.")
