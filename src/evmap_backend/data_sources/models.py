from django.db import models


class UpdateState(models.Model):
    data_source = models.CharField(
        max_length=255, primary_key=True, blank=False, null=False
    )
    last_update = models.DateTimeField(auto_now=True)
    push = models.BooleanField(blank=False, null=False)
