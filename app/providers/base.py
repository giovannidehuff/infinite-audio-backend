from abc import ABC, abstractmethod
from app.models.schemas import CopilotRequest, CopilotResponse


class BaseCopilotProvider(ABC):
    """
    Interface that every LLM provider must implement.
    Swap mock → openai → anthropic without touching the service or route.
    """

    @abstractmethod
    async def run(self, request: CopilotRequest, session_id: str) -> CopilotResponse:
        """Generate a full Session Co-Pilot response for the given request."""
        ...
