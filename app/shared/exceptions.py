from http import HTTPStatus


class ProjectDefenseException(Exception):
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    title = "Internal Server Error"

    def __init__(self, detail: str, *, code: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code or self.__class__.__name__


class DomainException(ProjectDefenseException):
    status_code = HTTPStatus.BAD_REQUEST
    title = "Domain Rule Violation"


class ValidationException(ProjectDefenseException):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    title = "Validation Error"


class RepositoryException(ProjectDefenseException):
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    title = "Repository Error"


class InfrastructureException(ProjectDefenseException):
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    title = "Infrastructure Error"


class ConflictException(ProjectDefenseException):
    status_code = HTTPStatus.CONFLICT
    title = "Conflict"


class NotFoundException(ProjectDefenseException):
    status_code = HTTPStatus.NOT_FOUND
    title = "Not Found"


class UnauthorizedException(ProjectDefenseException):
    status_code = HTTPStatus.UNAUTHORIZED
    title = "Unauthorized"


class ForbiddenException(ProjectDefenseException):
    status_code = HTTPStatus.FORBIDDEN
    title = "Forbidden"

