"""Student bulk-import from CSV, XLSX, or JSON.

Supports flexible column names — maps common aliases to the canonical fields.
Creates both a Student record and a User (login) account per row.
"""
from __future__ import annotations

import csv
import io
import json
import secrets
import string
from dataclasses import dataclass, field
from uuid import UUID

from app.core.security import security
from app.domain.enums import Track, UserRole
from app.schemas.auth import UserCreate
from app.schemas.core import StudentCreate

# ---------------------------------------------------------------------------
# Column alias map — key = canonical field, value = accepted header variants
# ---------------------------------------------------------------------------

_ALIASES: dict[str, list[str]] = {
    "full_name": ["full_name", "name", "student_name", "fullname", "full name", "student name", "studentname"],
    "email": ["email", "email_address", "mail", "emailaddress", "e-mail"],
    "track": ["track", "track_name", "program_track", "programme_track"],
    "mentor_id": ["mentor_id", "mentor", "assigned_mentor", "mentorid"],
    "password": ["password", "pass", "initial_password", "temp_password"],
    "github_username": ["github_username", "github", "github_handle", "github_user"],
}

# Reverse map: lower-cased variant → canonical field
_HEADER_MAP: dict[str, str] = {
    variant.lower(): canonical
    for canonical, variants in _ALIASES.items()
    for variant in variants
}

_TRACK_MAP: dict[str, Track] = {
    "a": Track.TRACK_A,
    "track_a": Track.TRACK_A,
    "track a": Track.TRACK_A,
    "b": Track.TRACK_B,
    "track_b": Track.TRACK_B,
    "track b": Track.TRACK_B,
}


def _map_headers(raw_headers: list[str]) -> dict[str, str]:
    """Return {raw_header: canonical_field} for each recognized header."""
    return {
        h: _HEADER_MAP[h.strip().lower()]
        for h in raw_headers
        if h.strip().lower() in _HEADER_MAP
    }


def _map_row(row: dict, header_map: dict[str, str]) -> dict[str, str]:
    """Normalize a raw row dict using the header map."""
    return {header_map[k]: v for k, v in row.items() if k in header_map and v}


def _random_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _parse_json(content: bytes) -> list[dict]:
    data = json.loads(content.decode("utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "students" in data:
        return data["students"]
    raise ValueError("JSON must be a list or {students: [...]}")


def _parse_xlsx(content: bytes) -> list[dict]:
    try:
        import openpyxl
    except ModuleNotFoundError as exc:
        raise ImportError("openpyxl is required for XLSX import. Install it: pip install openpyxl") from exc
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h) if h is not None else "" for h in rows[0]]
    result = []
    for row in rows[1:]:
        if all(v is None for v in row):
            continue
        result.append({headers[i]: (str(v) if v is not None else "") for i, v in enumerate(row)})
    return result


def _parse_file(filename: str, content: bytes) -> list[dict]:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "csv":
        return _parse_csv(content)
    if ext in ("xlsx", "xls"):
        return _parse_xlsx(content)
    if ext == "json":
        return _parse_json(content)
    # Attempt CSV fallback
    try:
        return _parse_csv(content)
    except Exception:
        raise ValueError(f"Unsupported file type '{ext}'. Use CSV, XLSX, or JSON.")


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class ImportResult:
    imported: int = 0
    skipped: int = 0
    errors: list[dict] = field(default_factory=list)
    student_ids: list[UUID] = field(default_factory=list)
    generated_passwords: list[dict] = field(default_factory=list)  # [{email, password}] when auto-generated


# ---------------------------------------------------------------------------
# Import service
# ---------------------------------------------------------------------------


class StudentImportService:
    """Parses uploaded files and bulk-creates Student + User records."""

    def __init__(self, uow, auth_uow) -> None:
        self._uow = uow
        self._auth_uow = auth_uow

    async def import_file(
        self,
        filename: str,
        content: bytes,
        organization_id: UUID,
        batch_id: UUID,
        default_track: Track = Track.TRACK_A,
        mentor_id: UUID | None = None,
        send_passwords: bool = False,
    ) -> ImportResult:
        rows = _parse_file(filename, content)
        if not rows:
            return ImportResult()

        header_map = _map_header_map_from_rows(rows)
        result = ImportResult()

        for i, raw_row in enumerate(rows, start=1):
            row = _map_row(raw_row, header_map)
            email = (row.get("email") or "").strip().lower()
            full_name = (row.get("full_name") or "").strip()

            if not email or not full_name:
                result.skipped += 1
                result.errors.append({
                    "row": i,
                    "reason": "missing required field",
                    "missing": [f for f in ("email", "full_name") if not row.get(f)],
                    "raw": {k: v for k, v in raw_row.items()},
                })
                continue

            raw_track = (row.get("track") or "").strip().lower()
            track = _TRACK_MAP.get(raw_track, default_track)

            row_mentor_id = None
            if row.get("mentor_id"):
                try:
                    row_mentor_id = UUID(row["mentor_id"])
                except ValueError:
                    pass
            effective_mentor_id = row_mentor_id or mentor_id

            password = (row.get("password") or "").strip() or None
            auto_generated = password is None
            if auto_generated:
                password = _random_password()

            try:
                async with self._uow:
                    student = await self._uow.students.create(StudentCreate(
                        organization_id=organization_id,
                        batch_id=batch_id,
                        full_name=full_name,
                        email=email,
                        track=track,
                        mentor_id=effective_mentor_id,
                    ))

                async with self._auth_uow:
                    existing_user = await self._auth_uow.users.get_by_email(email)
                    if existing_user is None:
                        await self._auth_uow.users.create(UserCreate(
                            email=email,
                            hashed_password=security.hash_password(password),
                            full_name=full_name,
                            role=UserRole.STUDENT,
                            organization_id=organization_id,
                        ))

                result.imported += 1
                result.student_ids.append(student.id)
                if auto_generated:
                    result.generated_passwords.append({"email": email, "password": password})

            except Exception as exc:
                result.skipped += 1
                result.errors.append({"row": i, "email": email, "reason": str(exc)})

        return result


def _map_header_map_from_rows(rows: list[dict]) -> dict[str, str]:
    if not rows:
        return {}
    return _map_headers(list(rows[0].keys()))
