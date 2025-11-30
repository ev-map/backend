from django.contrib import admin
from solo.admin import SingletonModelAdmin

from evmap_backend.data_sources.openstreetmap.models import OsmNode, OsmUpdateState


# Register your models here.
class OsmNodeAdmin(admin.ModelAdmin):
    pass


admin.site.register(OsmNode, OsmNodeAdmin)
admin.site.register(OsmUpdateState, SingletonModelAdmin)
