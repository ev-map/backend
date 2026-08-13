import datetime as dt

from django.core.management import BaseCommand
from django.utils import timezone

from evmap_backend.realtime.models import PreviousStatus


class Command(BaseCommand):
    help = "Deletes old records from realtime data"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        expire_threshold = timezone.now() - dt.timedelta(days=30)

        deleted, _ = PreviousStatus.objects.filter(
            timestamp__lt=expire_threshold
        ).delete()
        print(f"deleted {deleted} old records")
