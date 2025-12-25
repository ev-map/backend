from django.contrib import admin

from evmap_backend.apikeys.models import ApiKey


# Register your models here.
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("description", "truncated_key", "created_at", "active")

    def has_delete_permission(self, request, obj=None):
        # API keys shall not be deleted
        return False


admin.site.register(ApiKey, ApiKeyAdmin)
