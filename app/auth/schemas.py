"""
Pydantic v2 schemas for the auth module.
All constraints match the Data Security spec (password min 8 chars, email validated, etc.)
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Registration ──────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    """
    Request body for POST /auth/register.
    Password constraints per Data Security spec:
      min_length=8, max_length=72 (bcrypt hard limit)
    """

    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=72,
        description="Minimum 8 characters, maximum 72 (bcrypt limit)",
    )

    @field_validator("password")
    @classmethod
    def password_not_whitespace_only(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("Password cannot be whitespace only")
        return v


class UserRead(BaseModel):
    """Response schema after successful registration."""

    id: uuid.UUID
    email: str
    created_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


# ── Token ─────────────────────────────────────────────────────────────────────


class TokenRequest(BaseModel):
    """
    Request body for POST /auth/token (OAuth2 password flow).
    FastAPI's OAuth2PasswordRequestForm uses form data; we use JSON here
    to stay consistent with the rest of the API.
    """

    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    """JWT access token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int
