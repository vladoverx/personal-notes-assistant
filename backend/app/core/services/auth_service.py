from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from app.api.v1.schemas.auth import AuthResponse, SignInRequest, SignUpRequest
from app.config import settings
from app.dependencies import rate_limit_by_ip
from app.utils.logging import get_logger
from app.utils.validation import validate_password_strength

if TYPE_CHECKING:
    from fastapi import Request

    from app.core.schemas.auth import AuthUser


logger = get_logger(__name__)


class AuthService:
    """Authentication service handling business logic for auth operations."""

    def __init__(self, supabase_client: Any):
        self.supabase = supabase_client

    async def sign_up(self, request: Request, payload: SignUpRequest) -> AuthResponse:
        """Handle user signup with business logic."""
        rate_limit_by_ip(request, "signup")

        is_valid_password, password_error = validate_password_strength(payload.password)
        if not is_valid_password:
            raise ValueError(password_error)

        email = payload.email.lower().strip()
        password = payload.password

        try:
            resp = await asyncio.to_thread(
                lambda: self.supabase.auth.sign_up({
                    "email": email,
                    "password": password,
                })
            )
        except Exception as err:
            error_msg = str(err).lower()

            logger.warning(
                "Sign up failed",
                extra={
                    "email": email,
                    "error_type": type(err).__name__,
                    "error_summary": error_msg[:100] if error_msg else "Unknown error",
                }
            )

            # Gracefully handle invite-only mode (signups disabled in Supabase)
            if any(
                phrase in error_msg
                for phrase in (
                    "signup disabled",
                    "signups disabled",
                    "email signups disabled",
                    "disable signup",
                    "signups not allowed",
                    "signup not allowed",
                )
            ):
                raise ValueError("Signups are disabled. Please request an invite from a support.") from err

            if "already registered" in error_msg or "already exists" in error_msg:
                raise ValueError("An account with this email already exists") from err
            elif "invalid email" in error_msg:
                raise ValueError("Invalid email format") from err
            elif "weak password" in error_msg:
                raise ValueError("Password does not meet security requirements") from err
            else:
                raise ValueError("Failed to create account. Please try again.") from err

        if not resp.user or not getattr(resp, "session", None):
            raise ValueError("Account created but session not established. Please confirm your email or sign in.")

        user_email = resp.user.email or ""

        logger.info("User signed up successfully", extra={"email": user_email, "user_id": str(resp.user.id)})

        user_payload = {
            "id": str(resp.user.id),
            "email": resp.user.email or "",
        }

        return AuthResponse(
            access_token=resp.session.access_token,
            token_type="bearer",
            expires_in=resp.session.expires_in,
            refresh_token=resp.session.refresh_token,
            user=user_payload,
        )

    async def sign_in(self, request: Request, payload: SignInRequest) -> AuthResponse:
        """Handle user signin with business logic."""
        rate_limit_by_ip(request, "signin")

        email = payload.email.lower().strip()
        password = payload.password

        if not email or not password:
            raise ValueError("Email and password are required")

        try:
            resp = await asyncio.to_thread(
                lambda: self.supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password,
                })
            )
        except Exception as err:
            error_msg = str(err).lower()

            logger.warning(
                "Sign in failed",
                extra={
                    "email": email,
                    "error_type": type(err).__name__,
                    "error_summary": error_msg[:100] if error_msg else "Unknown error",
                }
            )

            if "invalid login credentials" in error_msg or "invalid email or password" in error_msg:
                raise ValueError("Invalid email or password") from err
            elif "email not confirmed" in error_msg:
                raise ValueError("Please confirm your email address before signing in") from err
            elif "too many requests" in error_msg:
                raise ValueError("Too many signin attempts. Please try again later.") from err
            else:
                raise ValueError("Authentication service error. Please try again.") from err

        if not resp.user or not getattr(resp, "session", None):
            raise ValueError("Invalid email or password")

        user_email = resp.user.email or ""

        logger.info("User signed in successfully", extra={"email": user_email, "user_id": str(resp.user.id)})

        user_payload = {
            "id": str(resp.user.id),
            "email": resp.user.email or "",
        }

        return AuthResponse(
            access_token=resp.session.access_token,
            token_type="bearer",
            expires_in=resp.session.expires_in,
            refresh_token=resp.session.refresh_token,
            user=user_payload,
        )

    async def sign_out(self, current_user: AuthUser) -> dict[str, str]:
        """Handle user signout with business logic."""
        try:
            await asyncio.to_thread(lambda: self.supabase.auth.sign_out())
            logger.info("User signed out successfully", extra={"user_id": str(current_user.id)})
            return {"message": "Signed out successfully"}
        except Exception as err:
            logger.warning("Sign out failed", extra={"error": str(err), "user_id": str(current_user.id)})
            return {"message": "Signed out successfully"}

    async def get_session(self) -> dict[str, Any]:
        """Get current session data."""
        try:
            session = await asyncio.to_thread(
                lambda: self.supabase.auth.get_session()
            )

            if not session.session:
                raise ValueError("No active session found")

            user = session.user
            if not user:
                raise ValueError("Invalid session data")

            return {
                "user": {
                    "id": str(user.id),
                    "email": user.email or "",
                },
                "session": {
                    "access_token": session.session.access_token,
                    "refresh_token": session.session.refresh_token,
                    "expires_in": session.session.expires_in,
                    "expires_at": session.session.expires_at,
                }
            }

        except Exception as err:
            error_msg = str(err).lower()

            logger.warning("Session retrieval failed", extra={"error": error_msg[:100]})

            if "no session" in error_msg or "invalid" in error_msg:
                raise ValueError("No valid session found") from err
            else:
                raise ValueError("Failed to retrieve session") from err

    async def refresh_token(self, request: Request) -> AuthResponse:
        """Refresh access token."""
        refresh_token = None

        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            refresh_token = auth_header.split(" ", 1)[1].strip()

        if not refresh_token:
            try:
                body = await request.json()
                refresh_token = body.get("refresh_token")
            except Exception:
                pass

        if not refresh_token:
            raise ValueError("Refresh token is required")

        try:
            resp = await asyncio.to_thread(
                lambda: self.supabase.auth.refresh_session(refresh_token)
            )
        except Exception as err:
            error_msg = str(err).lower()

            logger.warning("Token refresh failed", extra={"error": error_msg[:100]})

            if "invalid" in error_msg or "expired" in error_msg:
                raise ValueError("Invalid or expired refresh token") from err
            else:
                raise ValueError("Failed to refresh token") from err

        if not resp.user:
            raise ValueError("Invalid refresh token")

        user_payload = {
            "id": str(resp.user.id),
            "email": resp.user.email or "",
        }

        return AuthResponse(
            access_token=resp.session.access_token,
            token_type="bearer",
            expires_in=resp.session.expires_in,
            refresh_token=resp.session.refresh_token,
            user=user_payload,
        )
