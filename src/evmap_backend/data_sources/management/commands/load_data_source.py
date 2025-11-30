from django.core.management import BaseCommand

from evmap_backend.data_sources.registry import get_data_source, list_available_sources


class Command(BaseCommand):
    help = "Load data from a specified data source"

    def add_arguments(self, parser):
        parser.add_argument(
            "source_id",
            help=f"ID of the data source to load. Available sources: {', '.join(list_available_sources())}",
        )

    def handle(self, *args, **options):
        source_id = options["source_id"]

        try:
            data_source = get_data_source(source_id)
            self.stdout.write(
                self.style.SUCCESS(f"Starting data load for source: {source_id}")
            )

            data_source.load_data()

            self.stdout.write(
                self.style.SUCCESS(f"Successfully loaded data from source: {source_id}")
            )

        except ValueError as e:
            self.stdout.write(self.style.ERROR(str(e)))
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error loading data from {source_id}: {str(e)}")
            )
            raise
