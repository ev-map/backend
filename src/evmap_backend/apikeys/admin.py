from django.contrib import admin

from evmap_backend.apikeys.models import ApiKey


# Register your models here.
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("description", "truncated_key", "created_at", "active")


admin.site.register(ApiKey, ApiKeyAdmin)
