from providers.openai import OpenAIProvider


class CustomProvider(OpenAIProvider):
    name = "custom"
    base_url = ""
    auth_header = "Authorization"
    auth_prefix = "Bearer"
