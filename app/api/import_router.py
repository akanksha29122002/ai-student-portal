"""Student bulk-import API endpoints."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.dependencies import get_async_service, get_auth_service, get_current_user
from app.application.async_daily_loop_service import AsyncDailyLoopService
from app.domain.enums import Track, UserRole
from app.schemas.auth import CurrentUser
from app.services.import_service import StudentImportService
from app.shared.exceptions import UnauthorizedException

router = APIRouter(prefix="/import", tags=["import"])

_CurrentUser = Annotated[CurrentUser, Depends(get_current_user)]


@router.post(
    "/batches/{batch_id}/students",
    status_code=status.HTTP_201_CREATED,
    summary="Bulk-import students from CSV, XLSX, or JSON",
)
async def import_students(
    batch_id: UUID,
    current_user: _CurrentUser,
    file: UploadFile = File(..., description="CSV / XLSX / JSON student roster"),
    organization_id: UUID = Form(...),
    default_track: Track = Form(default=Track.TRACK_A),
    mentor_id: UUID | None = Form(default=None),
    service: AsyncDailyLoopService = Depends(get_async_service),
    auth_service=Depends(get_auth_service),
):
    """Upload a student roster file and create Student + User records.

    Required columns (flexible names): email, full_name / name
    Optional columns: track, mentor_id, password, github_username

    Returns summary with imported count, skipped rows, and errors.
    Auto-generated passwords are returned in `generated_passwords` (store securely).
    """
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER, UserRole.MENTOR
    ):
        raise UnauthorizedException("Insufficient permissions to import students")

    content = await file.read()
    if not content:
        raise ValueError("Uploaded file is empty")

    import_svc = StudentImportService(uow=service.uow, auth_uow=auth_service._uow)
    result = await import_svc.import_file(
        filename=file.filename or "upload",
        content=content,
        organization_id=organization_id,
        batch_id=batch_id,
        default_track=default_track,
        mentor_id=mentor_id,
    )

    return {
        "imported": result.imported,
        "skipped": result.skipped,
        "errors": result.errors,
        "student_ids": [str(sid) for sid in result.student_ids],
        "generated_passwords": result.generated_passwords,
    }
