import io
import tempfile
import zipfile
from collections import defaultdict

import requests
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management import BaseCommand

from evmap_backend.countries.models import Country
from evmap_backend.helpers.geo import WGS84


class Command(BaseCommand):
    help = "Import Countries"

    def handle(self, *args, **options):
        self.stdout.write("Downloading World Bank country shapefile...")
        country_data = requests.get(
            "https://datacatalogfiles.worldbank.org/ddh-published/0038272/5/DR0095371/World Bank Official Boundaries (Shapefiles)/World Bank Official Boundaries - Admin 0.zip"
        ).content

        with zipfile.ZipFile(io.BytesIO(country_data)) as z:
            with tempfile.TemporaryDirectory() as tmpdir:
                z.extractall(tmpdir)
                shp_path = next(
                    f"{tmpdir}/{name}" for name in z.namelist() if name.endswith(".shp")
                )
                ds = DataSource(shp_path, encoding="utf-8")
                layer = ds[0]

                features_by_country = defaultdict(list)
                for feature in layer:
                    features_by_country[feature.get("ISO_A2")].append(feature)

                count = 0
                for features in features_by_country.values():
                    geom = GEOSGeometry(features[0].geom.wkt, srid=WGS84)
                    for feature in features[1:]:
                        geom = geom.union(GEOSGeometry(feature.geom.wkt, srid=WGS84))

                    if geom.geom_type == "Polygon":
                        geom = MultiPolygon(geom)

                    Country.objects.update_or_create(
                        iso2=features[0].get("ISO_A2"),
                        defaults={
                            "geom": geom,
                            "iso3": features[0].get("ISO_A3"),
                            "name": features[0]
                            .get("NAM_0")
                            .encode("latin1")
                            .decode("utf-8"),
                        },
                    )
                    count += 1

                self.stdout.write(
                    self.style.SUCCESS(f"Successfully imported {count} countries.")
                )
