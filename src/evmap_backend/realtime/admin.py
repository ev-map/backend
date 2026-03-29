from django.contrib import admin
from django.core.paginator import Paginator
from django.db import connection
from django.utils.functional import cached_property

from evmap_backend.realtime.models import RealtimeStatus


class LargeTablePaginator(Paginator):
    """
    Overrides the count method of QuerySet objects to speed up pagination.
    https://gist.github.com/noviluni/d86adfa24843c7b8ed10c183a9df2afe
    """

    @cached_property
    def count(self):
        """
        Returns an estimated number of records, across all pages.
        """
        if not self.object_list.query.where:
            with connection.cursor() as cursor:
                # Obtain estimated count (only valid with PostgreSQL)
                cursor.execute(
                    "SELECT reltuples FROM pg_class WHERE relname = %s",
                    [self.object_list.query.model._meta.db_table],
                )
                estimate = int(cursor.fetchone()[0])
                return estimate
        return super().count


class RealtimeStatusAdmin(admin.ModelAdmin):
    readonly_fields = ["chargepoint", "status", "timestamp", "data_source"]
    list_select_related = ["chargepoint", "chargepoint__site"]
    list_display = [
        "chargepoint__evseid",
        "chargepoint__site__name",
        "status",
        "timestamp",
        "data_source",
    ]
    list_filter = ["status", "timestamp", "data_source"]
    paginator = LargeTablePaginator
    show_full_result_count = False
    ordering = ["-timestamp"]


# Register your models here.
admin.site.register(RealtimeStatus, RealtimeStatusAdmin)
