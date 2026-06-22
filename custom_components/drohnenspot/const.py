"""Konstanten für die Drohnenspot-Integration."""
from __future__ import annotations

DOMAIN = "drohnenspot"
VERSION = "0.1.0b1"

# Konfigurations-Schlüssel
CONF_RADIUS_KM = "radius_km"
CONF_SPOT_COUNT = "spot_count"
CONF_MIN_ELEVATION = "min_elevation"
CONF_ELEVATION_DATASET = "elevation_dataset"

# Vorgaben
DEFAULT_RADIUS_KM = 10
DEFAULT_SPOT_COUNT = 8
DEFAULT_MIN_ELEVATION = 0
DEFAULT_ELEVATION_DATASET = "eudem25m"
UPDATE_INTERVAL_HOURS = 6

# Frontend
CARD_URL = "/drohnenspot/drohnenspot-card.js"

# Pflicht-Attribution (CC BY 4.0 / CC-BY-SA)
ATTRIBUTION = (
    "Geozonen © DFS / GeoBasis-DE / BKG (CC BY 4.0) · "
    "Höhen © OpenTopoData/EU-DEM · Karte © OpenTopoMap (CC-BY-SA)"
)

SERVICE_FIND_SPOTS = "find_spots"
SERVICE_QUERY_POINT = "query_point"
