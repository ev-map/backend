from django.contrib.gis.forms import BaseGeometryWidget


class MapLibreWidget(BaseGeometryWidget):
    template_name = "widgets/maplibre.html"

    class Media:
        css = {"all": ("https://unpkg.com/maplibre-gl@^5.24.0/dist/maplibre-gl.css",)}
        js = (
            "https://unpkg.com/maplibre-gl@^5.24.0/dist/maplibre-gl.js",
            "widgets/maplibre.js",
        )

    def serialize(self, value):
        return value.json if value else ""
