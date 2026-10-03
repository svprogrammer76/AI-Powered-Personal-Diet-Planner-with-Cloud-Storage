from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class Profile(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=13, le=110)
    height_cm: float = Field(gt=80, le=250)
    weight_kg: float = Field(gt=25, le=350)
    activity_level: Literal["low", "moderate", "high"] = "moderate"
    dietary_preference: Literal["vegetarian", "vegan", "general"] = "general"
    goal: Literal["balanced", "weight_management", "fitness"] = "balanced"
    allergies: list[str] = Field(default_factory=list, max_length=20)


class UserProfile(Profile):
    model_config = ConfigDict(from_attributes=True)
    user_id: str
    email: EmailStr
    created_at: datetime


class DietPlan(BaseModel):
    plan_id: str
    user_id: str
    breakfast: str
    lunch: str
    snack: str
    dinner: str
    nutrition_summary: str
    hydration_reminder: str
    educational_notice: str
    source: str
    created_at: datetime


class FileRecord(BaseModel):
    file_id: str
    user_id: str
    filename: str
    storage_path: str
    uploaded_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
