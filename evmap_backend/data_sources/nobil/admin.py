from django.contrib import admin
from solo.admin import SingletonModelAdmin

from evmap_backend.data_sources.nobil.models import (
    NobilChargerStation,
    NobilConnector,
    NobilUpdateState,
)


class NobilConnectorInline(admin.StackedInline):
    model = NobilConnector


class NobilChargerStationAdmin(admin.ModelAdmin):
    list_display = ["id", "land_code", "name", "operator"]
    list_filter = ["real_time_information"]
    inlines = [NobilConnectorInline]


class NobilConnectorAdmin(admin.ModelAdmin):
    list_display = ["evse_id", "connector", "charging_capacity"]
    list_filter = [("evse_id", admin.EmptyFieldListFilter), "connector"]


# Register your models here.
admin.site.register(NobilChargerStation, NobilChargerStationAdmin)
admin.site.register(NobilConnector, NobilConnectorAdmin)
admin.site.register(NobilUpdateState, SingletonModelAdmin)
