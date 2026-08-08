import hashlib
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.shared.exceptions import InfrastructureException, UnauthorizedException

try:
    import jwt as _jwt
    _JWT_AVAILABLE = True
except ImportError:
    _jwt = None  # type: ignore[assignment]
    _JWT_AVAILABLE = False

try:
    from passlib.context import CryptContext
    _pwd_context: CryptContext | None = CryptContext(schemes=["bcrypt"], deprecated="auto")
    _PASSLIB_AVAILABLE = True
except ImportError:
    _pwd_context = None
    _PASSLIB_AVAILABLE = False

logger = logging.getLogger("project_defense.security")


class SecurityService:
    """JWT creation/verification and password hashing.

    Requires PyJWT (``pip install PyJWT``) and passlib[bcrypt]
    (``pip install passlib[bcrypt]``).  Both dependencies are optional at
    import time so the app starts in dev/test without them; they are only
    required when the relevant methods are actually called.
    """

    def hash_password(self, plain: str) -> str:
        if not _PASSLIB_AVAILABLE:
            raise InfrastructureException("passlib[bcrypt] is required — run: pip install passlib[bcrypt]")
        return _pwd_context.hash(plain)  # type: ignore[union-attr]

    def verify_password(self, plain: str, hashed: str) -> bool:
        if not _PASSLIB_AVAILABLE:
            raise InfrastructureException("passlib[bcrypt] is required — run: pip install passlib[bcrypt]")
        return _pwd_context.verify(plain, hashed)  # type: ignore[union-attr]

    def create_access_token(
        self,
        sub: str,
        email: str,
        full_name: str,
        role: str,
        org_id: str | None,
    ) -> str:
        self._assert_jwt()
        from app.core.config import settings
        expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_expire_minutes)
        payload = {
            "sub": sub,
            "email": email,
            "full_name": full_name,
            "role": role,
            "org": org_id,
            "type": "access",
            "exp": expire,
            "iat": datetime.now(UTC),
        }
        return _jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)  # type: ignore[union-attr]

    def create_refresh_token(self, sub: str) -> str:
        self._assert_jwt()
        from uuid import uuid4
        from app.core.config import settings
        expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_expire_days)
        payload = {
            "sub": sub,
            "jti": str(uuid4()),
            "type": "refresh",
            "exp": expire,
            "iat": datetime.now(UTC),
        }
        return _jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)  # type: ignore[union-attr]

    def decode_access_token(self, token: str) -> dict:
        return self._decode(token, expected_type="access")

    def decode_refresh_token(self, token: str) -> dict:
        return self._decode(token, expected_type="refresh")

    def _decode(self, token: str, expected_type: str) -> dict:
        self._assert_jwt()
        from app.core.config import settings
        try:
            payload: dict = _jwt.decode(  # type: ignore[union-attr]
                token, settings.secret_key, algorithms=[settings.jwt_algorithm]
            )
        except _jwt.ExpiredSignatureError:  # type: ignore[union-attr]
            raise UnauthorizedException("Token has expired")
        except _jwt.InvalidTokenError as exc:  # type: ignore[union-attr]
            raise UnauthorizedException(f"Invalid token: {exc}")
        if payload.get("type") != expected_type:
            raise UnauthorizedException("Invalid token type")
        return payload

    def hash_token(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    def _assert_jwt(self) -> None:
        if not _JWT_AVAILABLE:
            raise InfrastructureException("PyJWT is required — run: pip install PyJWT")


security = SecurityService()
