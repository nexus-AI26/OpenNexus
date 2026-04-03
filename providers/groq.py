from providers.openai import OpenAIProvider


class GroqProvider(OpenAIProvider):
    name = "groq"
    base_url = "https://api.groq.com/openai/v1"
    auth_header = "Authorization"
    auth_prefix = "Bearer"
