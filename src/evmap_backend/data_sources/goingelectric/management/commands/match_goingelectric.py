from django.core.management import BaseCommand

from evmap_backend.data_sources.goingelectric.matching import match_ge_locations


class Command(BaseCommand):
    help = "Match GoingElectric charge locations to ChargingSite records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-distance",
            type=float,
            default=200.0,
            help="Maximum distance in meters for candidate search (default: 200)",
        )
        parser.add_argument(
            "--min-confidence",
            type=float,
            default=0.4,
            help="Minimum confidence score for a match to be accepted (default: 0.4)",
        )

    def handle(self, *args, **options):
        max_distance = options["max_distance"]
        min_confidence = options["min_confidence"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting GoingElectric matching (max_distance={max_distance}m, "
                f"min_confidence={min_confidence})"
            )
        )

        match_ge_locations(
            max_distance_m=max_distance,
            min_confidence=min_confidence,
        )

        self.stdout.write(self.style.SUCCESS("Matching complete."))
