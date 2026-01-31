import sys
from asyncio import get_running_loop

from asgiref.sync import sync_to_async
from django.apps import AppConfig

background_tasks = set()


def is_async_context():
    try:
        get_running_loop()
        return True
    except RuntimeError:
        return False


class DataSourcesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "evmap_backend.data_sources"

    def ready(self):
        if (
            "makemigrations" in sys.argv
            or "migrate" in sys.argv
            or "pytest" in sys.argv[0]
        ):
            return

        from evmap_backend.data_sources.registry import init_data_sources

        if is_async_context():
            loop = get_running_loop()
            task = loop.create_task(sync_to_async(init_data_sources)())
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)
        else:
            init_data_sources()
