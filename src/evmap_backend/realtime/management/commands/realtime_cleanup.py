import datetime as dt

from django.core.management import BaseCommand
from django.utils import timezone

from evmap_backend.helpers.database import distinct_on
from evmap_backend.realtime.models import RealtimeStatus


class Command(BaseCommand):
    help = "Deletes old records from realtime data"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        expire_threshold = timezone.now() - dt.timedelta(days=30)

        # make sure to keep the latest status for each chargepoint
        latest = distinct_on(
            RealtimeStatus.objects, ["chargepoint"], "timestamp"
        ).values_list("pk", flat=True)
        # delete all older ones, if older than the threshold
        deleted, _ = (
            RealtimeStatus.objects.filter(timestamp__lt=expire_threshold)
            .exclude(pk__in=latest)
            .delete()
        )
        print(f"deleted {deleted} old records")
