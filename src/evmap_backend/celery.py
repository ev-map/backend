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

        sched = schedule(run_every=interval)
        last_update = update_states.get(cls.id)
        sched.last_run_at = (
            last_update if last_update is not None else datetime.datetime(1970, 1, 1)
        )

        sender.add_periodic_task(
            sched,
            sender.signature(
                "evmap_backend.data_sources.tasks.pull_data_source",
                args=(cls.id,),
            ),
            name=f"pull-{cls.id}",
        )
        count += 1

    logger.info(f"Registered {count} periodic pull tasks")
