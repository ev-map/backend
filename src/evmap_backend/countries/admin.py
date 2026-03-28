from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from evmap_backend.countries.models import Country


class CountryAdmin(GISModelAdmin):
    list_display = ["name", "iso2", "iso3"]
    search_fields = ["name", "iso2", "iso3"]


admin.site.register(Country, CountryAdmin)
