import gzip
import logging
from datetime import timedelta

from django.utils import timezone
from ninja import NinjaAPI

from evmap_backend.data_sources import DataSource, UpdateMethod
from evmap_backend.data_sources.models import UpdateState
from evmap_backend.data_sources.registry import get_data_source

api = NinjaAPI(urls_namespace="data_sources")


@api.post("/push/{data_source}")
def push(request, data_source: str):
    """
    HTTP push endpoint for data updates
    """
    data_source: DataSource = get_data_source(data_source)
    if UpdateMethod.HTTP_PUSH not in data_source.supported_update_methods:
        raise ValueError("Data source does not support push")

    data_source.verify_push(request)

    logging.info(f"Processing push for {data_source.id}...")

    body = request.body
    if request.headers.get("Content-Encoding") == "gzip":
        body = gzip.decompress(body)

    data_source.process_push(body)

    update_state, created = UpdateState.objects.get_or_create(
        data_source=data_source.id,
        defaults=dict(last_update=timezone.now(), push=True),
    )
    if timezone.now() - update_state.last_update > timedelta(minutes=1):
        update_state.last_update = timezone.now()
        update_state.push = True
        update_state.save()
    logging.info(f"Successfully processed push for {data_source.id}")

    return 200, ""


@api.api_operation(["HEAD"], "/push/{data_source}")
def push_head(request, data_source: str):
    """
    required by Mobilithek to verify push endpoint
    """
    data_source: DataSource = get_data_source(data_source)
    if UpdateMethod.HTTP_PUSH not in data_source.supported_update_methods:
        raise ValueError("Data source does not support push")

    data_source.verify_push(request)

    return 200, ""
