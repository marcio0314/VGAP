# VGAP Celery Tasks Package
# Import all task modules to enable Celery autodiscovery

from vgap.tasks.maintenance import (
    prune_docker_resources,
    scan_docker_usage,
)

__all__ = [
    "prune_docker_resources",
    "scan_docker_usage",
]
