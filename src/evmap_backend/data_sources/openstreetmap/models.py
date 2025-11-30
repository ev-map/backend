from django.contrib.gis.db import models
from solo.models import SingletonModel


class OsmNode(models.Model):
    id = models.BigIntegerField(primary_key=True)
    location = models.PointField()
    timestamp = models.DateTimeField()
    version = models.IntegerField()
    user = models.CharField(max_length=255)
    uid = models.BigIntegerField()
    tags = models.JSONField()


class OsmUpdateState(SingletonModel):
    last_update = models.DateTimeField(null=True)
