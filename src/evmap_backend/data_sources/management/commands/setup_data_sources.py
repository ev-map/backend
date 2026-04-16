from django.core.management import BaseCommand

from evmap_backend.data_sources.registry import (
    setup_data_sources,
)


class Command(BaseCommand):
    help = "Initializes data sources"

    def handle(self, *args, **options):
        setup_data_sources()
        self.stdout.write(self.style.SUCCESS("Successfully set up data sources."))
