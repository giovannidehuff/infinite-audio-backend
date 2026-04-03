import json
import os
from typing import Any, Dict, Optional

import anthropic

from app.models.schemas import (
    CopilotRequest,
    CopilotResponse,
)
from app.providers.base import BaseCopilotProvider


class AnthropicCopilotProvider(BaseCopilotProvider):
    """
    Real Anthropic Messages API provider for Session Co-Pilot.

    The model is instructed to output valid JSON only and we validate it
    against the existing `CopilotResponse` schema.
    """

    def __init__(self) -> None:
        api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("Missing ANTHROPIC_API_KEY in environment.")

        model = (os.getenv("ANTHROPIC_MODEL") or "").strip() or "claude-sonnet-4-20250514"

        # Async client so this provider can be used in the FastAPI async flow.
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    def _extract_text_block(self, message: Any) -> str:
        """
        Guard against empty/unexpected Anthropic content blocks.
        """
        content_blocks = getattr(message, "content", None)
        if not isinstance(content_blocks, list) or not content_blocks:
            raise ValueError("Anthropic returned no content blocks.")

        text_chunks = []
        for block in content_blocks:
            if getattr(block, "type", None) != "text":
                continue
            text = getattr(block, "text", None)
            if isinstance(text, str) and text.strip():
                text_chunks.append(text.strip())

        if not text_chunks:
            raise ValueError("Anthropic returned no text content.")

        # Messages API may return multiple text blocks; join defensively.
        return "\n".join(text_chunks).strip()

    def _parse_json_strict(self, raw_text: str) -> Dict[str, Any]:
        # Primary attempt: strict JSON parse.
        parsed = json.loads(raw_text)
        if not isinstance(parsed, dict):
            raise ValueError("Expected a top-level JSON object.")
        return parsed

    async def run(self, request: CopilotRequest, session_id: str) -> CopilotResponse:
        target_artist = (request.target_artist or "").strip()
        mood = (request.mood or "").strip()
        notes = (request.notes or "").strip()

        detected_key = (request.detected_key or "").strip()
        detected_bpm: Optional[int] = request.detected_bpm

        system_prompt = (
            "You are a world-class music producer and arrangement consultant. "
            "Generate producer-ready guidance for creating an original track/session based on the user brief. "
            "Output must be strictly valid JSON and nothing else.\n\n"
            "Hard requirements for quality:\n"
            "- Adapt the plan to the target artist (specific production traits, drum feel, arrangement pacing).\n"
            "- Adapt the plan to the mood/vibe (energy curve, density, sonic contrast).\n"
            "- If mood or brief is weak/ambiguous, infer reasonable choices from the target artist + detected key/BPM.\n"
            "- Avoid generic filler. Make each section distinct and actionable.\n"
            "- Provide practical guidance (what to do next in production, not motivational fluff).\n"
            "- Keep outputs concise but concrete.\n\n"
            "Return only JSON that conforms to the requested schema. Do not wrap in markdown fences."
        )

        user_prompt = {
            "session_brief": request.session_brief,
            "target_artist": target_artist or None,
            "mood": mood or None,
            "notes": notes or None,
            "detected_key": detected_key or None,
            "detected_bpm": detected_bpm,
            "enable_key_bpm": request.enable_key_bpm,
            "enable_session_direction": request.enable_session_direction,
            "task": (
                "Create a complete Session Co-Pilot response. "
                "Return a single JSON object with EXACTLY these top-level keys: "
                "`key_and_tempo`, `sonic_direction`, `arrangement_outline`, `artist_fit`, "
                "`reference_suggestions`, `next_move`.\n\n"
                "Do NOT include `session_id`, `provider`, or `generated_at` (these are added by the backend).\n\n"
                "Schema details:\n"
                "- `key_and_tempo`: { key: string, bpm: number|null, key_notes: string, bpm_notes: string }\n"
                "- `sonic_direction`: { headline: string, description: string, textures: string[], avoid: string[] }\n"
                "- `arrangement_outline`: { sections: [ { name: string, bars: string, note: string }, ... ] }\n"
                "- `artist_fit`: { primary: string, similar: string[], why: string }\n"
                "- `reference_suggestions`: { tracks: [ { artist: string, title: string, why: string }, ... ] }\n"
                "- `next_move`: { immediate: string, options: string[] }\n\n"
                "For `arrangement_outline.sections`, prefer 7 sections with these names: "
                "Intro, Verse 1, Pre-Chorus, Chorus / Drop, Verse 2, Bridge / Break, Outro.\n\n"
                "Use detected key/BPM when provided AND enabled; otherwise infer intelligently."
            ),
        }

        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=1400,
            temperature=0.7,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": [{"type": "text", "text": json.dumps(user_prompt)}],
                }
            ],
        )

        raw_text = self._extract_text_block(resp)

        # Primary strict parsing. If the model accidentally returns surrounding whitespace,
        # stripping usually makes it parseable while still enforcing JSON-only.
        try:
            parsed = self._parse_json_strict(raw_text.strip())
        except Exception:
            # Secondary attempt: extract the first JSON object substring.
            # This only kicks in when the model adds non-JSON text despite instructions.
            start = raw_text.find("{")
            end = raw_text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            parsed = self._parse_json_strict(raw_text[start : end + 1])

        payload = {
            **parsed,
            "session_id": session_id,
            "provider": "anthropic",
        }

        # Validate against the existing schema; any mismatch should fail fast.
        return CopilotResponse.model_validate(payload)

