from django.core.management import BaseCommand

from evmap_backend.data_sources.goingelectric.matching import match_ge_locations


class Command(BaseCommand):
    help = "Match GoingElectric charge locations to ChargingSite records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-distance",
            type=float,
            default=None,
            help="Maximum distance in meters for candidate search",
        )
        parser.add_argument(
            "--min-confidence",
            type=float,
            default=None,
            help="Minimum confidence score for a match to be accepted",
        )

    def handle(self, *args, **options):
        kwargs = {
            k: v
            for k, v in {
                "max_distance_m": options["max_distance"],
                "min_confidence": options["min_confidence"],
            }.items()
            if v is not None
        }

        self.stdout.write(self.style.SUCCESS("Starting GoingElectric matching..."))
        match_ge_locations(**kwargs)
        self.stdout.write(self.style.SUCCESS("Matching complete."))
