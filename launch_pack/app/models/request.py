from pydantic import BaseModel, Field
from typing import Optional


class LaunchPackRequest(BaseModel):
    beat_name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Name of the beat",
        examples=["Midnight Pressure"],
    )
    bpm: int = Field(
        ...,
        ge=40,
        le=300,
        description="Beats per minute",
        examples=[140],
    )
    mood: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Mood descriptors, comma-separated",
        examples=["dark, aggressive, cinematic"],
    )
    genre: str = Field(
        ...,
        min_length=2,
        max_length=80,
        description="Primary genre",
        examples=["drill"],
    )
    subgenre: Optional[str] = Field(
        default=None,
        max_length=80,
        description="Optional subgenre",
        examples=["UK drill"],
    )
    target_artists: Optional[list[str]] = Field(
        default=None,
        max_length=10,
        description="Up to 10 artist references for type beat positioning",
        examples=[["Central Cee", "Headie One"]],
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Short free-text description of the beat",
        examples=["Hard 808s, eerie strings, trap hi-hats"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "beat_name": "Midnight Pressure",
                    "bpm": 140,
                    "mood": "dark, aggressive, cinematic",
                    "genre": "drill",
                    "subgenre": "UK drill",
                    "target_artists": ["Central Cee", "Headie One"],
                    "description": "Hard 808s, eerie strings, trap hi-hats",
                }
            ]
        }
    }
