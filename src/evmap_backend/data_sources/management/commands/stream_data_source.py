from django.core.management import BaseCommand

from evmap_backend.data_sources import UpdateMethod
from evmap_backend.data_sources.models import UpdateState
from evmap_backend.data_sources.registry import get_data_source, list_available_sources


class Command(BaseCommand):
    help = "Stream data from a specified data source"

    def add_arguments(self, parser):
        parser.add_argument(
            "source_id",
            help=f"ID of the data source to stream. Available sources: {', '.join(list_available_sources())}",
        )

    def handle(self, *args, **options):
        source_id = options["source_id"]

        try:
            data_source = get_data_source(source_id)
            if UpdateMethod.STREAMING not in data_source.supported_update_methods:
                raise ValueError(
                    f"Data source {source_id} does not support streaming updates"
                )

            self.stdout.write(
                self.style.SUCCESS(f"Starting data streaming for source: {source_id}")
            )

            data_source.stream_data()

        except ValueError as e:
            self.stdout.write(self.style.ERROR(str(e)))
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error streaming data from {source_id}: {str(e)}")
            )
            raise
