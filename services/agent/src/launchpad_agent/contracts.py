from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BrandKit(BaseModel):
    """Small, validated visual identity carried with a production request."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(default="", max_length=60)
    primary_color: str = Field(default="#ff9900", pattern=r"^#[0-9a-fA-F]{6}$")


class GenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Untitled production", min_length=1, max_length=100)
    website_url: str = Field(min_length=8, max_length=2048)
    authorization_confirmed: bool
    brief: str = Field(min_length=10, max_length=4000)
    audience: str = Field(default="Product teams", max_length=120)
    duration_seconds: Literal[30, 45, 60, 90, 120, 180] = 45
    tone: str = Field(default="Clear and credible", max_length=100)
    narration_voice: Literal["female", "male"] = "female"
    format: Literal["presentation", "product", "spotlight", "short"] = "presentation"
    orientation: Literal["landscape", "portrait"] = "landscape"
    call_to_action: str = Field(default="Explore the product", max_length=100)
    captions: bool = True
    # Kept for backward-compatible stored jobs. The renderer no longer applies
    # animated camera zoom, even when an older request contains true.
    zoom: bool = False
    review_plan: bool = False
    brand: BrandKit = Field(default_factory=BrandKit)
    idempotency_key: str = Field(min_length=12, max_length=128)


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=2, max_length=75)
    on_screen_copy: str = Field(min_length=2, max_length=180)
    narration: str = Field(min_length=5, max_length=600)
    source_ids: list[str] = Field(min_length=1, max_length=3)
    page_id: str
    scroll: Literal["top", "middle", "bottom"] = "top"


class Storyboard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenes: list[Scene] = Field(min_length=3, max_length=12)


class CaptureAction(BaseModel):
    kind: Literal["click", "scroll", "wait"]
    page_id: str
    position: Literal["top", "middle", "bottom"] = "top"
