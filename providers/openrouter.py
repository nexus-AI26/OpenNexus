from providers.openai import OpenAIProvider


class OpenRouterProvider(OpenAIProvider):
    name = "openrouter"
    base_url = "https://openrouter.ai/api/v1"
    auth_header = "Authorization"
    auth_prefix = "Bearer"
