import datetime as dt

from django.core.management import BaseCommand

from evmap_backend.data_sources.nobil.models import NobilRealtimeData
from evmap_backend.helpers.database import distinct_on


class Command(BaseCommand):
    help = "Deletes old records from Nobil realtime data"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        expire_threshold = dt.datetime.now() - dt.timedelta(days=30)

        # make sure to keep the latest value for each nobil_id & evse_uid combination
        latest = distinct_on(
            NobilRealtimeData.objects, ["nobil_id", "evse_uid"], "timestamp"
        ).values_list("pk", flat=True)
        # delete all older ones
        to_delete = NobilRealtimeData.objects.filter(
            timestamp__lt=expire_threshold
        ).exclude(pk__in=latest)
        to_delete.delete()
