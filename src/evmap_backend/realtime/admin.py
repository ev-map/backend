from django.contrib import admin

from evmap_backend.realtime.models import RealtimeStatus


class RealtimeStatusAdmin(admin.ModelAdmin):
    readonly_fields = ["chargepoint", "status", "timestamp", "data_source"]
    list_display = [
        "chargepoint__evseid",
        "chargepoint__site__name",
        "status",
        "timestamp",
        "data_source",
    ]
    list_filter = ["status", "timestamp", "data_source"]


# Register your models here.
admin.site.register(RealtimeStatus, RealtimeStatusAdmin)
