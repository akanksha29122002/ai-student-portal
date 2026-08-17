"""Celery application instance.

Import this module to get the configured Celery app:

    from app.workers.celery_app import celery_app

Celery is optional at import time; ``celery_app`` is ``None`` when the
``celery`` package is not installed.
"""
try:
    from celery import Celery as _Celery
    _CELERY_AVAILABLE = True
except ImportError:
    _Celery = None  # type: ignore[assignment,misc]
    _CELERY_AVAILABLE = False


def _build() -> "_Celery | None":  # type: ignore[name-defined]
    if not _CELERY_AVAILABLE:
        return None
    from app.core.config import settings

    redis_url = (getattr(settings, "redis_url", "") or "").strip()
    if not redis_url:
        return None

    app = _Celery("project_defense")
    app.conf.update(
        broker_url=redis_url,
        result_backend=redis_url,
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
    )
    return app


celery_app = _build()
