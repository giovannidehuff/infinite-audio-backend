import os
import uuid
from typing import Optional

from app.models.schemas import CopilotRequest, CopilotResponse
from app.providers.base import BaseCopilotProvider
from app.providers.anthropic_provider import AnthropicCopilotProvider
from app.providers.mock import MockCopilotProvider

SESSIONS_TABLE = "session_history"


def _get_supabase():
    """
    Lazily create a Supabase client from env vars.
    Returns None if env vars are missing — persistence is optional in V1.
    Intentionally avoids importing at module level so the service works
    without Supabase configured (e.g. local dev without .env).
    """
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as e:
        print(f"[copilot_service] Supabase init failed (non-fatal): {e}")
        return None


async def run_copilot_session(
    request: CopilotRequest,
    provider: Optional[BaseCopilotProvider] = None,
) -> CopilotResponse:
    """
    Entry point for the Session Co-Pilot service layer.

    - Generates a session ID
    - Delegates to the provider (mock by default)
    - Persists the session to Supabase best-effort (never blocks the response)
    """
    if provider is None:
        # Prefer Anthropic when configured; otherwise keep the deterministic mock.
        api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
        if api_key:
            provider = AnthropicCopilotProvider()
        else:
            provider = MockCopilotProvider()

    session_id = str(uuid.uuid4())
    response = await provider.run(request, session_id)

    # Synchronous, best-effort. Runs before the response is returned.
    # A single Supabase insert — fast in practice. If persistence latency
    # ever becomes an issue, promote this to a background task.
    _persist_session(request, response)

    return response


def _persist_session(request: CopilotRequest, response: CopilotResponse) -> None:
    """
    Write the session to Supabase. Silently skips on any failure.
    A logging or monitoring hook can be added here later.
    """
    db = _get_supabase()
    if db is None:
        return

    try:
        db.table(SESSIONS_TABLE).insert({
            "id": response.session_id,
            "user_id": request.user_id,
            "session_brief": request.session_brief,
            "target_artist": request.target_artist,
            "mood": request.mood,
            "detected_key": request.detected_key,
            "detected_bpm": request.detected_bpm,
            "response": response.model_dump(),
            "provider": response.provider,
            "created_at": response.generated_at,
        }).execute()
    except Exception as e:
        print(f"[copilot_service] Supabase persist failed (non-fatal): {e}")
