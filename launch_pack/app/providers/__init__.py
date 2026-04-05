from app.providers.base import AIProvider, ProviderError
from app.config import get_settings


def get_provider() -> AIProvider:
    """
    Factory — returns the correct provider based on AI_PROVIDER env var.
    Add new providers here as elif branches.
    """
    settings = get_settings()
    provider = settings.ai_provider.lower()

    if provider == "openai":
        from app.providers.openai_provider import OpenAIProvider
        return OpenAIProvider()

    if provider == "anthropic":
        from app.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider()

    raise ProviderError(
        f"Unknown AI_PROVIDER '{provider}'. Supported: openai, anthropic."
    )


__all__ = ["AIProvider", "ProviderError", "get_provider"]
