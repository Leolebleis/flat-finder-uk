// map.js -- Leaflet map with colour-coded listing pins
(function () {
    "use strict";

    // --- Map setup ---
    var map = L.map("map").setView([51.51, -0.13], 13);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    // --- Zone overlays ---
    var zoneLayer = L.layerGroup().addTo(map);
    var zonesVisible = true;

    fetch("/flat/api/zones")
        .then(function (resp) {
            if (!resp.ok) throw new Error("Failed to fetch zones");
            return resp.json();
        })
        .then(function (zones) {
            zones.forEach(function (zone) {
                var geojson = JSON.parse(zone.geometry);
                var color = zone.color ? zone.color.color : "#0f766e";
                var layer = L.geoJSON(geojson, {
                    style: {
                        color: color,
                        weight: 2,
                        fillColor: color,
                        fillOpacity: 0.12,
                    },
                });
                layer.bindTooltip(zone.name, {
                    permanent: true,
                    direction: "center",
                    className: "zone-label",
                });
                zoneLayer.addLayer(layer);
            });
        })
        .catch(function (err) {
            console.error("Error loading zones:", err);
        });

    window.toggleZones = function () {
        zonesVisible = !zonesVisible;
        if (zonesVisible) {
            map.addLayer(zoneLayer);
            document.getElementById("filter-zones").classList.add("active");
        } else {
            map.removeLayer(zoneLayer);
            document.getElementById("filter-zones").classList.remove("active");
        }
    };

    // --- Listing markers ---
    var listingMarkers = [];
    var currentFilter = "all";

    function getMarkerColour(listing) {
        if (listing.favourite) return "#f5c542"; // gold
        if (listing.seen) return "#999";          // grey
        return "#e74c3c";                          // red
    }

    function formatPrice(price) {
        if (price == null) return "N/A";
        return "\u00a3" + price.toLocaleString() + " pcm";
    }

    function esc(str) {
        var div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function buildPopup(listing) {
        var detailUrl = "/flat/listing/" + encodeURIComponent(listing.id);
        var lines = [];
        if (listing.image_url) {
            lines.push('<img src="' + esc(listing.image_url) + '" style="width:220px;height:140px;object-fit:cover;border-radius:4px;margin-bottom:6px;" alt="">');
        }
        lines.push("<strong>" + formatPrice(listing.price_pcm) + "</strong>");
        if (listing.address) {
            lines.push(esc(listing.address));
        }
        if (listing.bedrooms != null) {
            lines.push(listing.bedrooms + " bed" + (listing.bedrooms !== 1 ? "s" : ""));
        }
        lines.push(
            '<a href="' + detailUrl + '">View detail</a>' +
            ' &middot; <a href="' + esc(listing.url) + '" target="_blank" rel="noopener">Source</a>'
        );
        return lines.join("<br>");
    }

    function shouldShow(listing) {
        if (currentFilter === "unseen") return !listing.seen;
        if (currentFilter === "favourites") return listing.favourite;
        return true; // "all"
    }

    function applyFilter() {
        listingMarkers.forEach(function (entry) {
            if (shouldShow(entry.listing)) {
                if (!map.hasLayer(entry.marker)) {
                    entry.marker.addTo(map);
                }
            } else {
                if (map.hasLayer(entry.marker)) {
                    map.removeLayer(entry.marker);
                }
            }
        });

        // Update active button styling
        document.querySelectorAll(".map-filters button").forEach(function (btn) {
            btn.classList.remove("active");
        });
        var activeBtn = document.getElementById("filter-" + currentFilter);
        if (activeBtn) activeBtn.classList.add("active");
    }

    // Expose filter setter globally for onclick handlers
    window.setFilter = function (filter) {
        currentFilter = filter;
        applyFilter();
    };

    // --- Fetch listings and render ---
    fetch("/flat/api/listings")
        .then(function (resp) {
            if (!resp.ok) throw new Error("Failed to fetch listings: " + resp.status);
            return resp.json();
        })
        .then(function (listings) {
            listings.forEach(function (listing) {
                if (listing.latitude == null || listing.longitude == null) return;

                var colour = getMarkerColour(listing);
                var marker = L.circleMarker([listing.latitude, listing.longitude], {
                    radius: 8,
                    fillColor: colour,
                    color: "#333",
                    weight: 1,
                    fillOpacity: 0.85,
                });

                marker.bindPopup(buildPopup(listing));
                listingMarkers.push({ marker: marker, listing: listing });
            });

            applyFilter();
        })
        .catch(function (err) {
            console.error("Error loading listings:", err);
        });
})();
