import httpx
import json
from app.providers.base import AIProvider, ProviderError
from app.config import get_settings


class AnthropicProvider(AIProvider):
    """
    Anthropic provider using direct HTTP (avoids SDK version lock).
    Swap to 'anthropic' SDK if preferred — interface is identical.
    """

    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self):
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not set in environment.")
        self._model = settings.anthropic_model
        self._api_key = settings.anthropic_api_key

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self._model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(self.API_URL, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["content"][0]["text"]
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"Anthropic HTTP error {e.response.status_code}: {e.response.text}") from e
        except Exception as e:
            raise ProviderError(f"Anthropic call failed: {e}") from e
