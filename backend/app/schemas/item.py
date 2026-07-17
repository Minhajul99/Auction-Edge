import uuid
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_validator

ALLOWED_CATEGORIES = {"Gaming", "Photography", "Audio", "Computers"}


class ItemCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: str
    photos: List[str]

    @field_validator("category")
    @classmethod
    def category_must_be_valid(cls, v):
        if v not in ALLOWED_CATEGORIES:
            raise ValueError(f"category must be one of {ALLOWED_CATEGORIES}")
        return v

    @field_validator("photos")
    @classmethod
    def at_least_one_photo(cls, v):
        if not v or len(v) == 0:
            raise ValueError("at least one photo is required")
        return v

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v):
        if not v or not v.strip():
            raise ValueError("title is required")
        return v


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: Optional[str]
    category: str
    photos: List[str]
    seller_id: uuid.UUID
