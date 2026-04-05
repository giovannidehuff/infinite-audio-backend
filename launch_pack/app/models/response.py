from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TypeBeatPositioning(BaseModel):
    primary_tag: str = Field(description="Primary 'type beat' tag, e.g. 'Central Cee Type Beat'")
    secondary_tags: list[str] = Field(description="2–4 additional type beat tags")
    positioning_rationale: str = Field(description="1–2 sentence reasoning for the positioning")


class YouTubePack(BaseModel):
    title: str = Field(description="Optimised YouTube video title including type beat tag")
    description: str = Field(description="Full YouTube description with sections and CTAs")
    tags: list[str] = Field(description="25–35 SEO-optimised tags")


class ShortFormContent(BaseModel):
    tiktok: list[str] = Field(description="3 TikTok video concepts/hooks")
    reels: list[str] = Field(description="3 Instagram Reels video concepts/hooks")
    shorts: list[str] = Field(description="3 YouTube Shorts video concepts/hooks")


class EmailTemplate(BaseModel):
    subject: str = Field(description="Email subject line")
    body: str = Field(description="Full email body")


class OutreachCopy(BaseModel):
    artist_dm: str = Field(description="DM template targeting the artist directly")
    collaborator_dm: str = Field(description="DM template for producer-to-producer collab outreach")
    email: EmailTemplate


class LaunchDay(BaseModel):
    day: int = Field(description="Day number 1–7")
    title: str = Field(description="Short title for the day's focus")
    actions: list[str] = Field(description="2–4 concrete actions to take on this day")


class LaunchPackMeta(BaseModel):
    model_used: str
    generated_at: datetime
    provider: str


class LaunchPackResponse(BaseModel):
    beat_name: str
    title_ideas: list[str] = Field(description="5 beat title variations")
    type_beat_positioning: TypeBeatPositioning
    youtube_pack: YouTubePack
    short_form_content: ShortFormContent
    outreach_copy: OutreachCopy
    launch_plan: list[LaunchDay] = Field(description="7-day launch plan")
    meta: LaunchPackMeta
