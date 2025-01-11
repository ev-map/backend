from django.contrib import admin

from evmap_backend.data_sources.openstreetmap.models import OsmNode


# Register your models here.
class OsmNodeAdmin(admin.ModelAdmin):
    pass


admin.site.register(OsmNode, OsmNodeAdmin)
