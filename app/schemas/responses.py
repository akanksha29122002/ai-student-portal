from app.schemas.base import ApiModel


class HealthResponse(ApiModel):
    status: str
    service: str

