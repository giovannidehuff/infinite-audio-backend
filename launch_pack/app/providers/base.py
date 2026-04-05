from abc import ABC, abstractmethod


class AIProvider(ABC):
    """
    Abstract base for all AI provider implementations.
    Add a new provider by subclassing this and setting AI_PROVIDER in .env.
    """

    @abstractmethod
    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send a system + user prompt pair and return the raw text response.
        Implementations must raise ProviderError on failure.
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier string for logging/meta."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return a short provider slug, e.g. 'openai' or 'anthropic'."""
        ...


class ProviderError(Exception):
    """Raised when an AI provider call fails."""
    pass
