"""
VGAP Celery Tasks

This module exposes all Celery tasks for autodiscovery.
Tasks must be in a 'tasks.py' file to be discovered by Celery's autodiscover_tasks().
"""

# Import and re-export all tasks from pipeline module
from vgap.services.pipeline import (
    process_run,
    process_sample_qc,
    generate_report,
)

# Declare exported tasks for explicit discovery
__all__ = [
    "process_run",
    "process_sample_qc", 
    "generate_report",
]
