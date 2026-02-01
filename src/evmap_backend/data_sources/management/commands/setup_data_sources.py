from django.core.management import BaseCommand

from evmap_backend.data_sources import UpdateMethod
from evmap_backend.data_sources.models import UpdateState
from evmap_backend.data_sources.registry import (
    get_data_source,
    list_available_sources,
    setup_data_sources,
)


class Command(BaseCommand):
    help = "Initializes data sources"

    def handle(self, *args, **options):
        setup_data_sources()
        self.stdout.write(self.style.SUCCESS(f"Successfully set up data sources."))
