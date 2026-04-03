from providers.base import BaseProvider
from providers.anthropic import AnthropicProvider
from providers.openai import OpenAIProvider
from providers.openrouter import OpenRouterProvider
from providers.groq import GroqProvider
from providers.ollama import OllamaProvider
from providers.custom import CustomProvider

__all__ = [
    "BaseProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
    "GroqProvider",
    "OllamaProvider",
    "CustomProvider",
    "get_provider",
]

PROVIDER_MAP: dict[str, type[BaseProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "openrouter": OpenRouterProvider,
    "groq": GroqProvider,
    "ollama": OllamaProvider,
    "custom": CustomProvider,
}


def get_provider(name: str, config: dict) -> BaseProvider:
    cls = PROVIDER_MAP.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown provider: '{name}'. "
            f"Available: {', '.join(PROVIDER_MAP.keys())}"
        )
    return cls(config)
