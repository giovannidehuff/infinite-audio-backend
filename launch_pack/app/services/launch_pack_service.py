import json
import logging
from datetime import datetime, timezone

from app.models.request import LaunchPackRequest
from app.models.response import LaunchPackResponse, LaunchPackMeta
from app.prompts.launch_pack_prompt import SYSTEM_PROMPT, build_user_prompt
from app.providers import get_provider, ProviderError

logger = logging.getLogger(__name__)


class LaunchPackService:
    async def generate(self, req: LaunchPackRequest) -> LaunchPackResponse:
        provider = get_provider()

        user_prompt = build_user_prompt(req)

        logger.info(
            "Generating launch pack",
            extra={"beat": req.beat_name, "provider": provider.provider_name},
        )

        try:
            raw = await provider.complete(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        except ProviderError as e:
            logger.error("Provider error: %s", e)
            raise

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse AI response as JSON: %s\nRaw: %s", e, raw[:500])
            raise ValueError("AI provider returned non-JSON response.") from e

        # Attach meta — not part of the AI response
        data["beat_name"] = req.beat_name
        data["meta"] = {
            "model_used": provider.model_name,
            "generated_at": datetime.now(timezone.utc),
            "provider": provider.provider_name,
        }

        try:
            return LaunchPackResponse(**data)
        except Exception as e:
            logger.error("Response validation failed: %s\nData: %s", e, data)
            raise ValueError(f"AI response did not match expected schema: {e}") from e
