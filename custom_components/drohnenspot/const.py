"""Konstanten für die Drohnenspot-Integration."""
from __future__ import annotations

DOMAIN = "drohnenspot"
VERSION = "0.1.0b10"

# Konfigurations-Schlüssel
CONF_RADIUS_KM = "radius_km"
CONF_SPOT_COUNT = "spot_count"
CONF_MIN_ELEVATION = "min_elevation"
CONF_ELEVATION_DATASET = "elevation_dataset"
CONF_EXCLUDE_FOREST = "exclude_forest"
CONF_REQUIRE_ROAD_ACCESS = "require_road_access"
CONF_MAX_ROAD_DISTANCE_M = "max_road_distance_m"
CONF_POI_BONUS = "poi_bonus"
CONF_POI_BONUS_RADIUS_M = "poi_bonus_radius_m"
CONF_POI_CATEGORIES = "poi_categories"

# Verfügbare Sehenswertes-Kategorien (Schlüssel = Kategorie, Wert = Label).
POI_CATEGORY_OPTIONS = {
    "viewpoint": "Aussichtspunkte",
    "historic": "Historische Orte",
    "lostplace": "Lost Places",
    "peak": "Gipfel",
    "tower": "Aussichtstürme",
}

# Vorgaben
DEFAULT_RADIUS_KM = 10
DEFAULT_SPOT_COUNT = 8
DEFAULT_MIN_ELEVATION = 0
DEFAULT_ELEVATION_DATASET = "eudem25m"
DEFAULT_EXCLUDE_FOREST = True
DEFAULT_REQUIRE_ROAD_ACCESS = True
DEFAULT_MAX_ROAD_DISTANCE_M = 200
DEFAULT_POI_BONUS = True
DEFAULT_POI_BONUS_RADIUS_M = 500
DEFAULT_POI_CATEGORIES = list(POI_CATEGORY_OPTIONS)
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
SERVICE_GET_POIS = "get_pois"
