from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class SignInRequest(BaseModel):
    """Request to sign in with email and password."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password")


class SignUpRequest(BaseModel):
    """Request to sign up with email and password."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password")


class AuthResponse(BaseModel):
    """Response containing user session and access token."""

    access_token: str = Field(..., description="JWT access token for API calls")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    refresh_token: str | None = Field(default=None, description="Refresh token for token renewal")
    user: dict = Field(..., description="User information (id, email)")
