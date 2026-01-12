"""
VGAP Celery Worker Configuration
"""

from celery import Celery

from vgap.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "vgap",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
)

# Configure
celery_app.conf.update(
    task_serializer=settings.celery.task_serializer,
    result_serializer=settings.celery.result_serializer,
    accept_content=settings.celery.accept_content,
    timezone=settings.celery.timezone,
    enable_utc=settings.celery.enable_utc,
    task_track_started=settings.celery.task_track_started,
    task_time_limit=settings.celery.task_time_limit,
    worker_prefetch_multiplier=settings.celery.worker_prefetch_multiplier,
    worker_concurrency=settings.celery.worker_concurrency,
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["vgap.services", "vgap.tasks"])


def main():
    """Entry point for worker."""
    celery_app.start()


if __name__ == "__main__":
    main()
