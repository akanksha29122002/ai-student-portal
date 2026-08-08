from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import Field

from app.domain.enums import UserRole
from app.schemas.base import ApiModel, Entity


class RefreshTokenCreate(ApiModel):
    user_id: UUID
    token_hash: str
    expires_at: datetime
    device_hint: str | None = None


class RefreshTokenRecord(Entity):
    user_id: UUID
    token_hash: str
    expires_at: datetime
    used_at: datetime | None = None
    revoked_at: datetime | None = None
    device_hint: str | None = None


class UserCreate(ApiModel):
    email: str = Field(min_length=5, max_length=254)
    hashed_password: str
    full_name: str = Field(min_length=2, max_length=160)
    role: UserRole = UserRole.STUDENT
    organization_id: UUID | None = None


class User(Entity):
    email: str
    hashed_password: str
    full_name: str
    role: UserRole
    organization_id: UUID | None = None
    is_active: bool = True
    last_login_at: datetime | None = None


class CurrentUser(ApiModel):
    id: UUID
    email: str
    full_name: str
    role: UserRole
    organization_id: UUID | None = None
    is_active: bool = True

    def can(self, *roles: UserRole) -> bool:
        return self.role == UserRole.SYSTEM or self.role in roles


class RegisterRequest(ApiModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=160)
    role: UserRole = UserRole.STUDENT
    organization_id: UUID | None = None


class LoginRequest(ApiModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(ApiModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(ApiModel):
    refresh_token: str


class ChangePasswordRequest(ApiModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class LogoutRequest(ApiModel):
    refresh_token: str


class UserResponse(ApiModel):
    id: UUID
    email: str
    full_name: str
    role: UserRole
    organization_id: UUID | None = None
    is_active: bool
