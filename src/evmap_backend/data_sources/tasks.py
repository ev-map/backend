import logging

from celery import shared_task

from evmap_backend.data_sources.models import UpdateState
from evmap_backend.data_sources.registry import get_data_source

logger = logging.getLogger(__name__)


@shared_task
def pull_data_source(source_id: str):
    try:
        source = get_data_source(source_id)
        logger.info("Pulling data for source %s", source_id)
        source.pull_data()
        UpdateState(data_source=source_id, push=False).save()
        logger.info("Successfully pulled data for source %s", source_id)
    except Exception:
        logger.exception("Failed to pull data for source %s", source_id)
        raise
