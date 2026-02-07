"""Messaging infrastructure for GraphCrawler.

Contains Celery tasks for distributed crawling:
- celery_unified: Main Celery app with crawl_page and crawl_batch tasks
- celery_job_task: Kubernetes-optimized crawl_job task for RemoteControl
"""

from graph_crawler.infrastructure.messaging.celery_unified import (
    celery,
    crawl_batch_task,
    crawl_page_task,
    get_driver_batch_size_task,
    health_check_task,
)

# Import crawl_job_task for K8s remote control
try:
    from graph_crawler.infrastructure.messaging.celery_job_task import crawl_job_task
except ImportError:
    # Dependencies not available
    crawl_job_task = None

__all__ = [
    "celery",
    "crawl_page_task",
    "crawl_batch_task",
    "health_check_task",
    "get_driver_batch_size_task",
    "crawl_job_task",
]
