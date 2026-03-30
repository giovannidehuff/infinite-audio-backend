from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class CopilotRequest(BaseModel):
    session_brief: str = Field(..., min_length=3, description="What you're working on this session.")
    target_artist: Optional[str] = Field(default=None, description="Artist reference or sound you're going for.")
    mood: Optional[str] = Field(default=None, description="Vibe / energy descriptor.")
    notes: Optional[str] = Field(default=None, description="Any extra context or constraints.")

    # From the audio analyzer (api.py /analyze)
    detected_key: Optional[str] = Field(default=None, description="Key detected from audio, e.g. 'A minor'.")
    detected_bpm: Optional[int] = Field(default=None, ge=40, le=300, description="BPM detected from audio.")

    # Toggles
    enable_key_bpm: bool = Field(default=True)
    enable_session_direction: bool = Field(default=True)

    # Session ownership — anonymous-friendly for V1
    user_id: Optional[str] = Field(default=None)


# ---------------------------------------------------------------------------
# Response cards
# ---------------------------------------------------------------------------

class KeyTempoCard(BaseModel):
    key: str
    bpm: Optional[int] = None
    key_notes: str
    bpm_notes: str


class SonicDirectionCard(BaseModel):
    headline: str
    description: str
    textures: List[str]
    avoid: List[str]


class ArrangementSection(BaseModel):
    name: str
    bars: str
    note: str


class ArrangementOutlineCard(BaseModel):
    sections: List[ArrangementSection]


class ArtistFitCard(BaseModel):
    primary: str
    similar: List[str]
    why: str


class ReferenceTrack(BaseModel):
    artist: str
    title: str
    why: str


class ReferenceSuggestionsCard(BaseModel):
    tracks: List[ReferenceTrack]


class NextMoveCard(BaseModel):
    immediate: str
    options: List[str]


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------

class CopilotResponse(BaseModel):
    session_id: str
    key_and_tempo: KeyTempoCard
    sonic_direction: SonicDirectionCard
    arrangement_outline: ArrangementOutlineCard
    artist_fit: ArtistFitCard
    reference_suggestions: ReferenceSuggestionsCard
    next_move: NextMoveCard
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    provider: str = Field(default="mock")
