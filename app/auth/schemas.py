"""
Pydantic v2 schemas for the authentication module.
"""
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for registering a new user."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)


class UserRead(BaseModel):
    """Schema for returning user details (excluding password)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime
    is_active: bool


class TokenRequest(BaseModel):
    """Schema for request to obtain JWT access token."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Schema for JWT response token details."""
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int
