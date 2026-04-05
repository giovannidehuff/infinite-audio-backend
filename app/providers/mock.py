from app.models.schemas import (
    ArrangementOutlineCard,
    ArrangementSection,
    ArtistFitCard,
    CopilotRequest,
    CopilotResponse,
    KeyTempoCard,
    NextMoveCard,
    RecommendedToolEntry,
    ReferenceTrack,
    ReferenceSuggestionsCard,
    SonicDirectionCard,
)
from app.providers.base import BaseCopilotProvider


class MockCopilotProvider(BaseCopilotProvider):
    """
    Deterministic mock provider for UI testing and local development.

    Uses request data directly to produce contextual placeholder responses.
    No external calls. No randomness. Same input always returns same output.
    Replace with a real provider by implementing BaseCopilotProvider.
    """

    async def run(self, request: CopilotRequest, session_id: str) -> CopilotResponse:
        key = request.detected_key or "F# minor"
        bpm = request.detected_bpm or 140
        artist = request.target_artist or "the reference artist"
        mood = request.mood or "dark and cinematic"

        return CopilotResponse(
            session_id=session_id,
            provider="mock",
            key_and_tempo=KeyTempoCard(
                key=key,
                bpm=bpm,
                key_notes=(
                    f"{key} carries harmonic weight. Works well with minor pentatonic "
                    f"leads and modal chord movement. Avoid over-resolving — "
                    f"let tension sit."
                ),
                bpm_notes=(
                    f"{bpm} BPM is a strong pocket for contemporary production. "
                    f"Consider a half-time feel on verses to create contrast "
                    f"before the drop."
                ),
            ),
            sonic_direction=SonicDirectionCard(
                headline="Dense, atmospheric, and forward-moving.",
                description=(
                    f"Build from a sparse foundation. Let the low-end breathe. "
                    f"The mood — {mood} — calls for restraint early and release "
                    f"late. Every element should earn its place."
                ),
                textures=[
                    "Detuned sub bass with subtle pitch movement",
                    "Granular pad sitting in the upper-mids",
                    "Dry, close-mic'd snare for weight",
                    "Sparse chord stabs with long reverb tail",
                ],
                avoid=[
                    "Overly bright, washed-out pads",
                    "Busy low-end — keep sub clean and mono",
                    "Clutter in the 200–400 Hz range",
                ],
            ),
            arrangement_outline=ArrangementOutlineCard(
                sections=[
                    ArrangementSection(
                        name="Intro",
                        bars="1–8",
                        note="Texture and atmosphere only. Establish key and space. No full beat yet.",
                    ),
                    ArrangementSection(
                        name="Verse 1",
                        bars="9–24",
                        note="Half-time feel. Introduce melody or top-line lightly. Keep energy low.",
                    ),
                    ArrangementSection(
                        name="Pre-Chorus",
                        bars="25–32",
                        note="Build tension. Layer in harmonic movement. Pull back just before the drop.",
                    ),
                    ArrangementSection(
                        name="Chorus / Drop",
                        bars="33–48",
                        note="Full energy. Commit to the sonic direction. Let the low-end hit.",
                    ),
                    ArrangementSection(
                        name="Verse 2",
                        bars="49–64",
                        note="Strip back slightly from the drop. Introduce a new textural element.",
                    ),
                    ArrangementSection(
                        name="Bridge / Break",
                        bars="65–80",
                        note="Minimal arrangement. Let the key breathe. Set up the final drop.",
                    ),
                    ArrangementSection(
                        name="Outro",
                        bars="81–96",
                        note="Gradual decay. Resolve or leave unresolved depending on mood.",
                    ),
                ]
            ),
            artist_fit=ArtistFitCard(
                primary=request.target_artist or "Fred again..",
                similar=["Four Tet", "Sampha", "James Blake"],
                why=(
                    f"The brief and detected mood align with production choices "
                    f"typical of {artist}: emotional restraint, textural depth, "
                    f"and dynamic contrast between sparse and dense sections."
                ),
            ),
            reference_suggestions=ReferenceSuggestionsCard(
                tracks=[
                    ReferenceTrack(
                        artist="Fred again..",
                        title="Bleu (Orlando's)",
                        why="Emotional restraint, textural pads, strong sub presence.",
                    ),
                    ReferenceTrack(
                        artist="Four Tet",
                        title="Parallel Jalebi",
                        why="Layered rhythmic and melodic elements over a consistent groove.",
                    ),
                    ReferenceTrack(
                        artist="James Blake",
                        title="Limit To Your Love",
                        why="Sparse arrangement with heavy low-end — nothing wasted.",
                    ),
                ]
            ),
            next_move=NextMoveCard(
                immediate=(
                    f"Lock in the drum groove at {bpm} BPM first. "
                    f"Build everything else around the kick-bass relationship."
                ),
                options=[
                    "Write the chord progression before committing to sounds",
                    "Record a scratch vocal or melodic idea to set direction",
                    "Build the drop first, then work backward to the intro",
                    "Pull up a reference mix and A/B from the start",
                ],
            ),
            recommended_tools=[
                RecommendedToolEntry(
                    role="808 sub bass",
                    plugins=["Serum", "Vital", "808 Studio II"],
                    preset_hint="Sine-heavy body, pitch envelope drop ~4–6 semitones, light saturation.",
                ),
                RecommendedToolEntry(
                    role="Trap drum kit",
                    plugins=["Superior Drummer 3", "Battery 4", "Slate Drums"],
                    preset_hint="Tight room kit; shorten snare attack; HPF kick ~40 Hz.",
                ),
                RecommendedToolEntry(
                    role="Wide pad layer",
                    plugins=["Valhalla Supermassive", "Portal", "RC-20"],
                    preset_hint="Long decay, slow filter automation, keep lows mono.",
                ),
            ],
        )
