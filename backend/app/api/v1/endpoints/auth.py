from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.api.v1.schemas.auth import (
    AuthResponse,
    SignInRequest,
    SignUpRequest,
)
from app.dependencies import (
    get_auth_service,
    get_current_user,
)
from app.utils.logging import get_logger

if TYPE_CHECKING:
    from app.core.schemas.auth import AuthUser

logger = get_logger(__name__)

# Configure router with authentication-specific settings
router = APIRouter(
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        429: {"description": "Too many requests"}
    }
)


@router.post("/signup", response_model=AuthResponse)
async def sign_up_with_password(
    request: Request,
    payload: SignUpRequest,
    auth_service=Depends(get_auth_service),
):
    """Sign up with email and password."""
    try:
        return await auth_service.sign_up(request, payload)
    except HTTPException as http_exc:
        raise http_exc
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err
    except Exception as err:
        logger.error("Unexpected error during signup", extra={"error": str(err)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from err


@router.post("/signin", response_model=AuthResponse)
async def sign_in_with_password(
    request: Request,
    payload: SignInRequest,
    auth_service=Depends(get_auth_service),
):
    """Sign in with email and password."""
    try:
        return await auth_service.sign_in(request, payload)
    except HTTPException as http_exc:
        raise http_exc
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err
    except Exception as err:
        logger.error("Unexpected error during signin", extra={"error": str(err)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from err


@router.post("/signout")
async def sign_out(
    current_user: AuthUser = Depends(get_current_user),
    auth_service=Depends(get_auth_service),
):
    """Sign out the current user."""
    try:
        result = await auth_service.sign_out(current_user)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=result
        )
    except Exception as err:
        logger.error("Unexpected error during signout", extra={"error": str(err)})
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Signed out successfully"}
        )


@router.get("/validate")
async def validate_token(current_user: AuthUser = Depends(get_current_user)):
    """Validate the current user's token and return user info."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
    }


@router.get("/session")
async def get_session(
    auth_service=Depends(get_auth_service),
):
    """Get the current session data using Supabase's get_session() method."""
    try:
        return await auth_service.get_session()
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(err),
        ) from err
    except Exception as err:
        logger.error("Unexpected error getting session", extra={"error": str(err)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from err


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    request: Request,
    auth_service=Depends(get_auth_service),
):
    """Refresh the access token using a refresh token."""
    try:
        return await auth_service.refresh_token(request)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err
    except Exception as err:
        logger.error("Unexpected error refreshing token", extra={"error": str(err)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from err
