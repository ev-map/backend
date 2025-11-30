from django.contrib import admin

from evmap_backend.data_sources.monta.models import MontaTokens


class MontaTokensAdmin(admin.ModelAdmin):
    pass


admin.site.register(MontaTokens, MontaTokensAdmin)
