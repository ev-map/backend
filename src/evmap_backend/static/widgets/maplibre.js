class MapWidget {
    constructor(options) {
        this.options = options;

        this.map = this.createMap();

        this.map.on('load', async () => {
            const initial_value = JSON.parse(document.getElementById(this.options.id).value);
            switch (initial_value.type) {
                case "Point":
                    new maplibregl.Marker()
                        .setLngLat(initial_value.coordinates)
                        .addTo(this.map);
                    this.map.setCenter(initial_value.coordinates)
                    break;
                case "MultiPolygon":
                    this.map.addSource('polygon', {
                        'type': 'geojson',
                        'data': {
                            'type': 'Feature',
                            'geometry': initial_value
                        }
                    });
                    this.map.addLayer({
                        'id': 'polygon',
                        'type': 'fill',
                        'source': 'polygon',
                        'layout': {},
                        'paint': {
                            'fill-color': '#4caf50',
                            'fill-opacity': 0.8
                        }
                    });

                    // Compute bounding box of the polygon and fit the map to it
                    const bounds = new maplibregl.LngLatBounds();
                    for (const polygon of initial_value.coordinates) {
                        for (const ring of polygon) {
                            for (const coord of ring) {
                                bounds.extend(coord);
                            }
                        }
                    }
                    this.map.fitBounds(bounds, { padding: 20, animate: false });

            }
        });
    }

    createMap() {
        return new maplibregl.Map({
            container: this.options.map_id,
            style: 'https://tiles.openfreemap.org/styles/bright',
            zoom: 10
        });
    }
}

function initMapWidgetInSection(section) {
    const maps = [];

    section.querySelectorAll(".dj_map_wrapper").forEach((wrapper) => {
        // Avoid initializing map widget on an empty form.
        if (wrapper.id.includes("__prefix__")) {
            return;
        }
        const textarea_id = wrapper.querySelector("textarea").id;
        const options_script = wrapper.querySelector(
            `script#${textarea_id}_mapwidget_options`,
        );
        const options = JSON.parse(options_script.textContent);
        options.id = textarea_id;
        options.map_id = wrapper.querySelector(".dj_map").id;
        maps.push(new MapWidget(options));
    });

    return maps;
}

document.addEventListener("DOMContentLoaded", () => {
    initMapWidgetInSection(document);
    document.addEventListener("formset:added", (ev) => {
        initMapWidgetInSection(ev.target);
    });
});