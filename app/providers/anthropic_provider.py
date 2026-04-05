import json
import os
import re
from typing import Any, Dict, Iterator, List, Optional

import anthropic

from app.models.schemas import (
    CopilotRequest,
    CopilotResponse,
)
from app.providers.base import BaseCopilotProvider

# Post-generation guardrails (string values only — avoids false hits on JSON keys like "sonic_direction").
BANNED_PHRASES: List[str] = [
    "build tension",
    "create space",
    "emotional depth",
    "flowing delivery",
    "full cinematic arrangement",
    "introspective tracks",
    "let it breathe",
    "maintain the mood",
    "sonic DNA",
    "sonic landscape",
    "record violin",
    "record cello",
    "record strings",
    "recorded violin",
    "recorded strings",
    "recorded cello",
    "tracking session",
    "room takes",
]

_MAX_RESPONSE_VALUE_CHARS = 2100

_IMMEDIATE_BAD_PREFIXES = (
    "start with ",
    "begin with ",
    "consider ",
    "try ",
    "maybe ",
    "you ",
    "first ",
    "explore ",
)

# Imperative openers that satisfy "DAW-first" (extend as needed).
_IMMEDIATE_VERBS = frozenset({
    "load", "draw", "print", "commit", "bounce", "slice", "record", "program",
    "set", "copy", "mute", "solo", "route", "bus", "send", "automate", "duplicate",
    "quantize", "render", "export", "import", "layer", "stack", "pitch", "detune",
    "resample", "compress", "sidechain", "filter", "tune", "transpose", "consolidate",
    "freeze", "trim", "fade", "group", "arm", "monitor", "write", "open", "save",
    "pull", "drop", "drag", "normalize", "stem", "bypass", "disable", "enable",
    "reduce", "cut", "boost", "high-pass", "low-pass", "hpf", "lpf", "eq", "gain-stage",
    "gainstage", "consolidate", "render", "export", "import", "duplicate", "split",
    "merge", "glue", "sum", "route", "patch", "assign", "map",
})

_RETRY_USER_NUDGE = (
    "REWRITE: Your last JSON failed post-checks (banned mood/tutorial phrasing in any string, "
    "total text too long, or next_move.immediate not opening with a concrete DAW verb). "
    "Return one valid JSON object only. Strip cinematic/mood words. Shorten all strings. "
    "next_move.immediate must start with an imperative like Load, Draw, Program, Slice, Commit — "
    "not “start with” or “consider”."
)

_RETRY_FILLER_NUDGE = (
    "Your last output still contained banned filler/tutorial phrasing. "
    "Remove all cinematic, emotional, atmospheric, and explanatory language. "
    "Rewrite tighter and more technical. "
    "Return one valid JSON object only with the same top-level keys."
)

_MAX_GENERATION_ATTEMPTS = 3


def _iter_json_string_values(obj: Any) -> Iterator[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_json_string_values(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_json_string_values(item)


def _values_char_count(response_json: dict) -> int:
    return sum(len(s) for s in _iter_json_string_values(response_json))


def _immediate_opener_valid(immediate: str) -> bool:
    s = (immediate or "").strip()
    if not s:
        return False
    low = s.lower()
    for bad in _IMMEDIATE_BAD_PREFIXES:
        if low.startswith(bad):
            return False
    first = s.split()[0]
    first = re.sub(r"^[^A-Za-z0-9]+", "", first)
    first = re.sub(r"[^A-Za-z0-9\-]+$", "", first)
    if not first:
        return False
    token = first.lower()
    if token in _IMMEDIATE_VERBS:
        return True
    head = token.split("-", 1)[0]
    return head in _IMMEDIATE_VERBS


def is_response_valid(response_json: dict) -> bool:
    """
    Lightweight post-model checks before Pydantic. Operates on the parsed model JSON only
    (no session_id / provider).
    """
    blob = " ".join(s.lower() for s in _iter_json_string_values(response_json))
    for phrase in BANNED_PHRASES:
        if phrase.lower() in blob:
            return False

    if _values_char_count(response_json) > _MAX_RESPONSE_VALUE_CHARS:
        return False

    immediate = (response_json.get("next_move") or {}).get("immediate", "")
    if not _immediate_opener_valid(str(immediate)):
        return False

    return True


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

    def _parse_model_json(self, raw_text: str) -> Dict[str, Any]:
        try:
            return self._parse_json_strict(raw_text.strip())
        except Exception:
            start = raw_text.find("{")
            end = raw_text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            return self._parse_json_strict(raw_text[start : end + 1])

    async def run(self, request: CopilotRequest, session_id: str) -> CopilotResponse:
        target_artist = (request.target_artist or "").strip()
        mood = (request.mood or "").strip()
        notes = (request.notes or "").strip()

        detected_key = (request.detected_key or "").strip()
        detected_bpm: Optional[int] = request.detected_bpm

        system_prompt = (
            "You are Session Co-Pilot: one producer passing session notes to another advanced producer. "
            "Not a tutorial, blog, or product blurb.\n"
            "This is a 100% in-the-box tool. Every output assumes the producer is in a DAW with software only — "
            "no hardware, no live recording, no microphones, no outboard gear. Any reference to live instruments "
            "must be silently translated to its software equivalent before output.\n\n"
            "OUTPUT\n"
            "Return one JSON object only. No markdown fences, no text before or after the object. "
            "Top-level keys must be exactly: key_and_tempo, sonic_direction, arrangement_outline, artist_fit, "
            "reference_suggestions, next_move, recommended_tools. Never echo session_brief, mood, or other request fields. "
            "Do not output session_id, provider, or generated_at.\n\n"
            "GLOBAL RULES\n"
            "Assume an advanced producer. Never explain fundamentals. Never describe basic concepts "
            "(808s, reverb, EQ, arrangement basics).\n"
            "Ban soft, filler, or cinematic/mood fluff in every JSON string. Never generate these or close paraphrases: "
            "build tension; create space; emotional depth; cinematic width; dreamy textures; atmospheric layers; "
            "establish the mood; foundation; backbone; add movement; keep energy; let it breathe; melodic accessibility; "
            "signature bounce; sonic landscape; sonic DNA; compliments the artist; fits the vibe.\n"
            "If any banned phrase appears, the output is considered failed. Rewrite internally before returning.\n"
            "If a sentence could appear in a YouTube tutorial, rewrite it.\n"
            "Tone: short sentences; verb-first when possible; no storytelling; no adjectives unless they change a production "
            "decision; prefer nouns and verbs over description.\n"
            "Every sentence must imply a musical decision, a DAW action, a sound choice, or an arrangement change.\n"
            "Prioritize compression over elegance. Fast session notes, not writing.\n"
            "Never describe how the music feels unless that directly changes a production decision.\n\n"
            "FIELD RULES (same schema)\n"
            "key_and_tempo.key — One clear tonal center; must match harmony in key_notes.\n"
            "key_and_tempo.key_notes — EXACTLY 1 short sentence: brief tonal reason + 1–2 harmonic moves "
            "(Roman numerals or chords). No descriptive adjectives.\n"
            "key_and_tempo.bpm_notes — EXACTLY 1 short sentence; must include groove mechanics "
            "(swing %, subdivision, half-time vs full-time, hat grid, etc.). No general tempo explanation.\n"
            "sonic_direction.headline — MAX 8 words. Production direction, not a vibe. No cinematic/mood language, no marketing.\n"
            "sonic_direction.description — MAX 2 sentences. Each sentence = one concrete production move. No abstract description.\n"
            "sonic_direction.textures — EXACTLY 4 lines: sub → mids → top → glue. Each line = one actionable layer or processing "
            "move. No descriptive filler.\n"
            "sonic_direction.avoid — EXACTLY 3 lines: frequency clashes, arrangement mistakes, or masking — specific to THIS "
            "mix. No generic advice.\n"
            "artist_fit.primary — Target or best fit. similar — exactly 3 artist names.\n"
            "artist_fit.why — EXACTLY 1 sentence. No praise. No obvious stylistic similarity lecture.\n"
            "reference_suggestions.tracks — Exactly 3. Each why: EXACTLY 1 short sentence; only 2–3 production traits. "
            "No emotional or descriptive commentary.\n"
            "arrangement_outline.sections — 5–9 sections; functional names; believable bars.\n"
            "arrangement_outline.sections[].note — EXACTLY 1 sentence: what enters, drops, doubles, mutes, or shifts. "
            "No vague phrases.\n"
            "next_move.immediate — MUST start with a verb. MUST be one concrete DAW action. MAX 20 words. No “start with”.\n"
            "next_move.immediate — ADDITIONAL CONSTRAINTS:\n"
            "- Never mention \"click track\", \"over a click\", \"metronome\", or \"over BPM click\" — the producer knows to use a click.\n"
            "- Never state obvious DAW defaults (quantize to grid, use headphones, etc.).\n"
            "- Never explain WHY to do the action — just state the action.\n"
            "- The instruction must be something only THIS session would need, not generic advice.\n"
            "next_move.options — EXACTLY 4 options; each a distinct execution path; MAX 15 words each. "
            "Ban generic actions: add texture, experiment, build atmosphere.\n"
            "recommended_tools — EXACTLY 3–5 objects. Each object: role (string), plugins (array of 2–4 plugin name strings), "
            "preset_hint (string). Tailor to this session’s sounds. Follow PLUGIN RULE and RECOMMENDED TOOLS RULE below.\n\n"
            "KEY AND BPM (no trap autopilot)\n"
            "Do not reflexively pick F# minor or 138–142 BPM. Use F# minor only when brief + artist + mood warrant it; "
            "otherwise rotate centers (e.g. A/B/D/G/E/C#/Eb minor darker; D/A/B/F#/Eb major brighter lift). "
            "Modal or Phrygian color in key_notes if it fits.\n"
            "Bright / uptempo / open-texture briefs: favor major or modal lift, slower or longer phrases, wider BPM range — "
            "not the same minor grid every time.\n"
            "No detected key/BPM: infer from session_brief + mood + target_artist if present. “Trap” alone ≠ F# + ~140.\n"
            "No target_artist: infer from brief + mood (experimental / weird / distorted → rarer centers, broken swing, "
            "off-grid drift where appropriate).\n"
            "If detected_bpm is supplied: keep it unless it fights the brief.\n"
            "Tempo bands (guides): half-time 66–84; mid swing/skip 86–112; driving 118–128; busy bounce 130–150; "
            "broken 70–95 or uneven phrasing.\n\n"
            "ARRANGEMENT\n"
            "Avoid the same 7-part skeleton every time. Vary bar plans. Wide-score sections ≠ pocket bounce unless the brief "
            "asks for both.\n\n"
            "REFERENCES\n"
            "Three tracks: overlap in drum/bass/vocal/mix moves with this session — not lazy chart defaults.\n"
            "\n"
            "---\n"
            "\n"
            "SCOPE RULE — ABSOLUTE:\n"
            "This tool is 100% in-the-box. The producer is working in a DAW with software only.\n"
            "\n"
            "NEVER output:\n"
            "- Any instruction to capture live audio (e.g. mic a violin, track acoustic drums, room takes)\n"
            "- Any hardware unit by name (API, SSL, Neve, Echoplex, tape machines, preamps, amps)\n"
            "- Any reference to microphones, DI boxes, or physical signal chain\n"
            "- The word \"record\" unless it means draw/edit MIDI in the piano roll or bounce/export audio in the DAW\n"
            "\n"
            "ALWAYS output:\n"
            "- Instrument or sound descriptions followed by plugin examples in parentheses\n"
            "- MIDI programming instructions\n"
            "- DAW routing (sends, buses, sidechains, automation lanes)\n"
            "- Software-based mix decisions\n"
            "\n"
            "PLUGIN RULE:\n"
            "Never prescribe a specific plugin as the only option.\n"
            "Always describe the sound or instrument type first, then suggest 2–3 plugin examples in parentheses as options.\n"
            "Format: string ensemble patch (Kontakt, Arcade, Spitfire LABS)\n"
            "Format: analog bass synth (Serum, Massive, Vital)\n"
            "Format: room reverb (Valhalla Room, Eventide Blackhole)\n"
            "The producer chooses what they have. You only guide the sound direction.\n"
            "\n"
            "If the brief implies live instruments → translate silently to software equivalent:\n"
            "- live strings → string ensemble patch (Kontakt, Arcade, Spitfire LABS)\n"
            "- live drums → drum sampler (Superior Drummer, Battery, Slate Drums)\n"
            "- live guitar → guitar VST (Shreddage, Amplesoft, Strum GS)\n"
            "Never acknowledge the translation. Just output the in-the-box version.\n"
            "\n"
            "---\n"
            "\n"
            "RECOMMENDED TOOLS RULE:\n"
            "Every response must include a recommended_tools array (3–5 entries) based on sounds and textures in the session.\n"
            "Each entry must have: role (string), plugins (array of 2–4 plugin name strings), preset_hint (string).\n"
            "preset_hint = general dial-in guidance, not an exact preset name.\n"
            "Example entry: role \"808 sub bass\", plugins [\"Serum\", \"Vital\", \"808 Studio II\"], "
            "preset_hint \"Sine wave start, pitch envelope drop 4–6 semitones, light saturation\"\n"
            "Example entry: role \"Orchestral string ensemble\", plugins [\"Kontakt\", \"Spitfire LABS\", \"Arcade\"], "
            "preset_hint \"Legato or sustain articulations, layer two patches panned slightly L and R\"\n"
            "Example entry: role \"Trap drum kit\", plugins [\"Superior Drummer 3\", \"Battery 4\", \"Slate Drums\"], "
            "preset_hint \"Punchy room kit, pull snare attack back, HPF kick above 40Hz\"\n"
            "Include recommended_tools on every generation regardless of brief.\n"
            "\n"
            "---\n"
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
                "Create a complete Session Co-Pilot response for an advanced producer: compressed, peer-level "
                "copy in every string — same schema, tighter wording (see system prompt).\n"
                "Return a single JSON object with EXACTLY these top-level keys: "
                "`key_and_tempo`, `sonic_direction`, `arrangement_outline`, `artist_fit`, "
                "`reference_suggestions`, `next_move`, `recommended_tools`.\n\n"
                "Do NOT include `session_id`, `provider`, or `generated_at` (these are added by the backend).\n\n"
                "Schema details:\n"
                "- `key_and_tempo`: { key: string, bpm: number|null, key_notes: string, bpm_notes: string }\n"
                "  If enable_key_bpm is false, keep key/bpm plausible but keep notes short.\n"
                "- `sonic_direction`: { headline: string, description: string, textures: string[], avoid: string[] }\n"
                "  textures: exactly 4 (stack order). avoid: exactly 3.\n"
                "- `arrangement_outline`: { sections: [ { name: string, bars: string, note: string }, ... ] }\n"
                "  5–9 sections; names and bar ranges must feel bespoke — follow the arrangement rules in the system prompt.\n"
                "- `artist_fit`: { primary: string, similar: string[], why: string }\n"
                "  similar: exactly 3 artists.\n"
                "- `reference_suggestions`: { tracks: [ { artist: string, title: string, why: string }, ... ] }\n"
                "  exactly 3 tracks.\n"
                "- `next_move`: { immediate: string, options: string[] }\n"
                "  options: exactly 4 strings.\n"
                "- `recommended_tools`: [ { role: string, plugins: string[], preset_hint: string }, ... ]\n"
                "  3–5 entries; each plugins array has 2–4 plugin names.\n\n"
                "When detected_key and detected_bpm are null and enable_key_bpm is true, infer key and BPM per "
                "the KEY AND BPM section of the system prompt."
            ),
        }

        messages: List[dict] = [
            {
                "role": "user",
                "content": [{"type": "text", "text": json.dumps(user_prompt)}],
            }
        ]

        parsed: Optional[Dict[str, Any]] = None
        last_raw = ""

        for attempt in range(_MAX_GENERATION_ATTEMPTS):
            resp = await self._client.messages.create(
                model=self._model,
                max_tokens=1800,
                temperature=0.78,
                system=system_prompt,
                messages=messages,
            )
            last_raw = self._extract_text_block(resp)
            import logging
            logging.getLogger(__name__).warning("RAW MODEL OUTPUT: %s", last_raw)
            try:
                parsed = self._parse_model_json(last_raw)
            except Exception:
                if attempt >= _MAX_GENERATION_ATTEMPTS - 1:
                    raise
                messages.append(
                    {"role": "assistant", "content": [{"type": "text", "text": last_raw}]}
                )
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": _RETRY_USER_NUDGE
                                + " Also: previous output was not valid JSON — return one JSON object only.",
                            }
                        ],
                    }
                )
                continue

            if is_response_valid(parsed):
                break

            if attempt < _MAX_GENERATION_ATTEMPTS - 1:
                messages.append(
                    {"role": "assistant", "content": [{"type": "text", "text": last_raw}]}
                )
                messages.append(
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": _RETRY_FILLER_NUDGE}],
                    }
                )

        if parsed is None:
            raise ValueError("Anthropic returned no parseable JSON.")

        if not is_response_valid(parsed):
            raise ValueError(
                "Session Co-Pilot could not generate a clean response. "
                "Please try again with a shorter or more specific brief."
            )

        payload = {
            **parsed,
            "session_id": session_id,
            "provider": "anthropic",
        }

        # Validate against the existing schema; any mismatch should fail fast.
        return CopilotResponse.model_validate(payload)

