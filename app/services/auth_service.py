from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.core.security import security
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RefreshTokenCreate,
    RegisterRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.shared.exceptions import ConflictException, ForbiddenException, NotFoundException, UnauthorizedException


class AuthService:
    def __init__(self, uow) -> None:
        self._uow = uow

    async def register(self, payload: RegisterRequest) -> TokenResponse:
        async with self._uow:
            existing = await self._uow.users.get_by_email(payload.email)
            if existing is not None:
                raise ConflictException(f"Email '{payload.email}' is already registered")
            user = await self._uow.users.create(UserCreate(
                email=payload.email,
                hashed_password=security.hash_password(payload.password),
                full_name=payload.full_name,
                role=payload.role,
                organization_id=payload.organization_id,
            ))
            access_token = security.create_access_token(
                sub=str(user.id),
                email=user.email,
                full_name=user.full_name,
                role=str(user.role),
                org_id=str(user.organization_id) if user.organization_id else None,
            )
            raw_refresh = security.create_refresh_token(sub=str(user.id))
            from app.core.config import settings
            expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_expire_days)
            await self._uow.refresh_tokens.create(RefreshTokenCreate(
                user_id=user.id,
                token_hash=security.hash_token(raw_refresh),
                expires_at=expires_at,
            ))

        return TokenResponse(access_token=access_token, refresh_token=raw_refresh)

    async def login(self, payload: LoginRequest) -> TokenResponse:
        async with self._uow:
            user = await self._uow.users.get_by_email(payload.email)

            if user is None or not security.verify_password(payload.password, user.hashed_password):
                raise UnauthorizedException("Invalid email or password")

            if not user.is_active:
                raise UnauthorizedException("Account is disabled")

            access_token = security.create_access_token(
                sub=str(user.id),
                email=user.email,
                full_name=user.full_name,
                role=str(user.role),
                org_id=str(user.organization_id) if user.organization_id else None,
            )
            raw_refresh = security.create_refresh_token(sub=str(user.id))
            from app.core.config import settings
            expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_expire_days)
            await self._uow.refresh_tokens.create(RefreshTokenCreate(
                user_id=user.id,
                token_hash=security.hash_token(raw_refresh),
                expires_at=expires_at,
            ))

        return TokenResponse(access_token=access_token, refresh_token=raw_refresh)

    async def refresh_tokens(self, payload: RefreshRequest) -> TokenResponse:
        claims = security.decode_refresh_token(payload.refresh_token)
        user_id = UUID(claims["sub"])
        token_hash = security.hash_token(payload.refresh_token)

        async with self._uow:
            record = await self._uow.refresh_tokens.get_by_hash(token_hash)

            if record is not None:
                if record.used_at is not None:
                    # Reuse detected — revoke all tokens for this user (breach signal)
                    await self._uow.refresh_tokens.revoke_all_for_user(user_id)
                    await self._uow.commit()  # persist revocations before raising
                    raise UnauthorizedException("Refresh token reuse detected — all sessions revoked")
                if record.revoked_at is not None:
                    raise UnauthorizedException("Refresh token has been revoked")
                if record.expires_at < datetime.now(UTC):
                    raise UnauthorizedException("Refresh token has expired")
                await self._uow.refresh_tokens.mark_used(record.id)

            user = await self._uow.users.get_by_id(user_id)
            if user is None or not user.is_active:
                raise UnauthorizedException("Invalid or expired refresh token")

            access_token = security.create_access_token(
                sub=str(user.id),
                email=user.email,
                full_name=user.full_name,
                role=str(user.role),
                org_id=str(user.organization_id) if user.organization_id else None,
            )
            raw_refresh = security.create_refresh_token(sub=str(user.id))
            from app.core.config import settings
            expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_expire_days)
            await self._uow.refresh_tokens.create(RefreshTokenCreate(
                user_id=user.id,
                token_hash=security.hash_token(raw_refresh),
                expires_at=expires_at,
            ))

        return TokenResponse(access_token=access_token, refresh_token=raw_refresh)

    async def logout(self, payload: LogoutRequest) -> None:
        try:
            claims = security.decode_refresh_token(payload.refresh_token)
        except Exception:
            return
        token_hash = security.hash_token(payload.refresh_token)
        async with self._uow:
            record = await self._uow.refresh_tokens.get_by_hash(token_hash)
            if record is not None and record.revoked_at is None:
                await self._uow.refresh_tokens.revoke(record.id)

    async def change_password(self, user_id: UUID, payload: ChangePasswordRequest) -> None:
        async with self._uow:
            user = await self._uow.users.get_by_id(user_id)
            if user is None:
                raise NotFoundException("User not found")
            if not security.verify_password(payload.old_password, user.hashed_password):
                raise ForbiddenException("Current password is incorrect")
            new_hashed = security.hash_password(payload.new_password)
            await self._uow.users.update_password(user_id, new_hashed)
            await self._uow.refresh_tokens.revoke_all_for_user(user_id)

    async def get_profile(self, user_id: UUID) -> UserResponse:
        async with self._uow:
            user = await self._uow.users.get_by_id(user_id)

        if user is None:
            raise NotFoundException(f"User {user_id} not found")

        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            organization_id=user.organization_id,
            is_active=user.is_active,
        )
