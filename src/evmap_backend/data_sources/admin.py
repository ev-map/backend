from django.contrib import admin

from evmap_backend.data_sources.models import UpdateState


class UpdateStateAdmin(admin.ModelAdmin):
    readonly_fields = ["data_source", "last_update", "push"]
    list_display = ["data_source", "last_update", "push"]
    list_filter = ["push"]


# Register your models here.
admin.site.register(UpdateState, UpdateStateAdmin)
