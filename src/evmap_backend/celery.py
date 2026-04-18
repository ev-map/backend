import datetime
import logging
import os

from celery import Celery
from celery.schedules import schedule
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "evmap_backend.settings")

logger = logging.getLogger(__name__)

app = Celery("evmap_backend")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.on_after_finalize.connect
def setup_periodic_tasks(sender: Celery, **kwargs):
    from evmap_backend.data_sources.models import UpdateState
    from evmap_backend.data_sources.registry import DATA_SOURCE_CLASSES

    update_states = {}
    try:
        update_states = {
            s.data_source: s.last_update for s in UpdateState.objects.all()
        }
    except Exception:
        logger.debug("Could not read UpdateState table, skipping beat schedule seeding")

    count = 0
    for cls in DATA_SOURCE_CLASSES:
        interval = cls.sync_interval
        if interval is None:
            continue

        last_update = update_states.get(cls.id)
        entry = {
            "task": "evmap_backend.data_sources.tasks.pull_data_source",
            "schedule": schedule(run_every=interval),
            "args": (cls.id,),
            "last_run_at": last_update
            if last_update is not None
            else datetime.datetime.min,
        }

        sender.conf.beat_schedule[f"pull-{cls.id}"] = entry
        count += 1

    logger.info(f"Registered {count} periodic pull tasks")
