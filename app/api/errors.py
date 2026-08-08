from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.shared.exceptions import ProjectDefenseException


def problem_details(status_code: int, title: str, detail: str, instance: str, code: str | None = None) -> dict:
    payload = {
        "type": f"https://project-defense.ai/problems/{code or title.lower().replace(' ', '-')}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
    }
    if code:
        payload["code"] = code
    return payload


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProjectDefenseException)
    async def project_defense_exception_handler(request: Request, exc: ProjectDefenseException):
        return JSONResponse(
            status_code=int(exc.status_code),
            content=problem_details(int(exc.status_code), exc.title, exc.detail, str(request.url.path), exc.code),
            media_type="application/problem+json",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=problem_details(422, "Validation Error", str(exc.errors()), str(request.url.path), "request_validation_failed"),
            media_type="application/problem+json",
        )

