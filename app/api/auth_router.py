from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_auth_service, get_current_user
from app.schemas.auth import (
    ChangePasswordRequest,
    CurrentUser,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

_Auth = Annotated[AuthService, Depends(get_auth_service)]
_CurrentUser = Annotated[CurrentUser, Depends(get_current_user)]


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, service: _Auth) -> TokenResponse:
    return await service.register(payload)


@router.post("/token", response_model=TokenResponse)
async def login(payload: LoginRequest, service: _Auth) -> TokenResponse:
    return await service.login(payload)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, service: _Auth) -> TokenResponse:
    return await service.refresh_tokens(payload)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, service: _Auth) -> None:
    await service.logout(payload)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: _CurrentUser,
    service: _Auth,
) -> None:
    await service.change_password(current_user.id, payload)


@router.get("/me", response_model=UserResponse)
async def me(current_user: _CurrentUser, service: _Auth) -> UserResponse:
    return await service.get_profile(current_user.id)
