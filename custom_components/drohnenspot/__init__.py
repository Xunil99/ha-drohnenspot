"""Drohnenspot (DE) — Home-Assistant-Integration.

Stellt Sensoren zur Heimat-Lage (Verbotszone? Höhe? bester Spot?) bereit,
einen ``find_spots``-Service und registriert die mitgelieferte Lovelace-Karte
automatisch als Frontend-Ressource.

Datenquellen: DIPUL (DFS) für Geozonen, OpenTopoData/EU-DEM für Höhen.
"""
from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ATTRIBUTION,
    CARD_URL,
    CONF_ELEVATION_DATASET,
    CONF_EXCLUDE_FOREST,
    CONF_MIN_ELEVATION,
    CONF_RADIUS_KM,
    DEFAULT_ELEVATION_DATASET,
    DEFAULT_EXCLUDE_FOREST,
    DEFAULT_MAX_ROAD_DISTANCE_M,
    DEFAULT_RADIUS_KM,
    DEFAULT_REQUIRE_ROAD_ACCESS,
    DEFAULT_SPOT_COUNT,
    DOMAIN,
    SERVICE_FIND_SPOTS,
    SERVICE_QUERY_POINT,
    VERSION,
)
from .coordinator import DrohnenspotCoordinator
from .dipul import (
    ALL_LAYERS,
    DEFAULT_RESTRICTION_LAYERS,
    DipulClient,
    summarize_restrictions,
)
from .elevation import ElevationClient
from .forest import ForestClient
from .recommend import async_find_spots

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

FIND_SPOTS_SCHEMA = vol.Schema(
    {
        vol.Optional("latitude"): cv.latitude,
        vol.Optional("longitude"): cv.longitude,
        vol.Optional("radius_km", default=DEFAULT_RADIUS_KM): vol.All(
            vol.Coerce(float), vol.Range(min=1, max=50)
        ),
        vol.Optional("count", default=DEFAULT_SPOT_COUNT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=30)
        ),
        vol.Optional("min_elevation"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("exclude_forest"): cv.boolean,
        vol.Optional("require_road_access"): cv.boolean,
        vol.Optional("max_road_distance_m"): vol.All(
            vol.Coerce(float), vol.Range(min=10, max=5000)
        ),
    }
)

QUERY_POINT_SCHEMA = vol.Schema(
    {
        vol.Required("latitude"): cv.latitude,
        vol.Required("longitude"): cv.longitude,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Eine Konfigurationsinstanz einrichten."""
    session = async_get_clientsession(hass)
    dataset = entry.options.get(
        CONF_ELEVATION_DATASET,
        entry.data.get(CONF_ELEVATION_DATASET, DEFAULT_ELEVATION_DATASET),
    )
    dipul = DipulClient(session)
    elevation = ElevationClient(session, dataset=dataset)
    forest = ForestClient(session)

    coordinator = DrohnenspotCoordinator(hass, entry, dipul, elevation, forest)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "dipul": dipul,
        "elevation": elevation,
        "forest": forest,
    }

    await _async_register_frontend(hass)
    _async_register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Instanz entladen."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            for service in (SERVICE_FIND_SPOTS, SERVICE_QUERY_POINT):
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Mitgelieferte Karte als statische Ressource + Dashboard-Modul anmelden."""
    if hass.data.get(f"{DOMAIN}_frontend"):
        return
    from homeassistant.components.http import StaticPathConfig

    card_path = Path(__file__).parent / "www" / "drohnenspot-card.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card_path), False)]
    )
    # Lädt das Modul auf allen Dashboards -> type: custom:drohnenspot-card nutzbar
    from homeassistant.components.frontend import add_extra_js_url

    add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}")
    hass.data[f"{DOMAIN}_frontend"] = True
    _LOGGER.debug("Drohnenspot-Karte als Frontend-Ressource registriert")


def _get_clients(hass: HomeAssistant) -> dict:
    """Die Client-Bündel der ersten eingerichteten Instanz holen."""
    entries = hass.data.get(DOMAIN, {})
    clients = next(
        (v for v in entries.values() if isinstance(v, dict) and "dipul" in v),
        None,
    )
    if clients is None:
        raise HomeAssistantError("Drohnenspot ist nicht eingerichtet.")
    return clients


def _async_register_services(hass: HomeAssistant) -> None:
    """``find_spots`` und ``query_point`` registrieren (mit Service-Antwort)."""

    async def _handle_find_spots(call: ServiceCall) -> ServiceResponse:
        clients = _get_clients(hass)
        lat = call.data.get("latitude", hass.config.latitude)
        lon = call.data.get("longitude", hass.config.longitude)
        try:
            return await async_find_spots(
                clients["dipul"],
                clients["elevation"],
                lat,
                lon,
                call.data["radius_km"] * 1000.0,
                count=call.data["count"],
                min_elevation=call.data.get("min_elevation"),
                forest=clients["forest"],
                exclude_forest=call.data.get("exclude_forest", DEFAULT_EXCLUDE_FOREST),
                require_road_access=call.data.get(
                    "require_road_access", DEFAULT_REQUIRE_ROAD_ACCESS
                ),
                max_road_distance_m=call.data.get(
                    "max_road_distance_m", DEFAULT_MAX_ROAD_DISTANCE_M
                ),
            )
        except HomeAssistantError:
            raise
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Spot-Suche fehlgeschlagen: {err}") from err

    async def _handle_query_point(call: ServiceCall) -> ServiceResponse:
        clients = _get_clients(hass)
        lat = call.data["latitude"]
        lon = call.data["longitude"]
        try:
            hits = await clients["dipul"].query_point(lat, lon, ALL_LAYERS)
            elevation = await clients["elevation"].point(lat, lon)
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Punktabfrage fehlgeschlagen: {err}") from err
        restricted = bool(hits & set(DEFAULT_RESTRICTION_LAYERS))
        return {
            "latitude": lat,
            "longitude": lon,
            "restricted": restricted,
            "features": summarize_restrictions(hits),
            "elevation_m": round(elevation, 1) if elevation is not None else None,
            "attribution": ATTRIBUTION,
        }

    if not hass.services.has_service(DOMAIN, SERVICE_FIND_SPOTS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_FIND_SPOTS,
            _handle_find_spots,
            schema=FIND_SPOTS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_QUERY_POINT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_QUERY_POINT,
            _handle_query_point,
            schema=QUERY_POINT_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
