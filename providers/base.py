from abc import ABC, abstractmethod
from typing import AsyncGenerator, Any


class BaseProvider(ABC):
    name: str = "base"
    base_url: str = ""
    auth_header: str = ""
    auth_prefix: str = ""
    api_key: str = ""

    def __init__(self, config: dict[str, Any]) -> None:
        self.base_url = config.get("base_url", self.base_url)
        self.api_key = config.get("api_key", "")
        self.auth_header = config.get("auth_header", self.auth_header)
        self.auth_prefix = config.get("auth_prefix", self.auth_prefix)
        self.default_model = config.get("default_model", "")

    def get_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.auth_header and self.api_key:
            value = f"{self.auth_prefix} {self.api_key}".strip() if self.auth_prefix else self.api_key
            headers[self.auth_header] = value
        return headers

    def validate_url(self) -> None:
        if not self.base_url:
            raise ValueError(f"[{self.name}] base_url is not configured.")
        is_localhost = any(
            h in self.base_url
            for h in ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")
        )
        if not is_localhost and not self.base_url.startswith("https://"):
            raise ValueError(
                f"[{self.name}] HTTPS required for non-localhost URLs. "
                f"Got: {self.base_url}"
            )

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        system: str | None = None,
        stream: bool = True,
    ) -> AsyncGenerator[str, None]:
        ...
        yield  # pragma: no cover
