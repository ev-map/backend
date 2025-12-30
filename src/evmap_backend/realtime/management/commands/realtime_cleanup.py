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

        # make sure to keep the latest value for each nobil_id & evse_uid combination
        latest = distinct_on(
            RealtimeStatus.objects, ["chargepoint"], "timestamp"
        ).values_list("pk", flat=True)
        # delete all older ones
        to_delete = RealtimeStatus.objects.filter(
            timestamp__lt=expire_threshold
        ).exclude(pk__in=latest)
        print(f"deleting {to_delete.count()} old records")
        to_delete.delete()
