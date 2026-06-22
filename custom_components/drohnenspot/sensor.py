"""Sensoren: Höhe am Heimat-Standort und bester Spot in der Nähe."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTRIBUTION, DOMAIN
from .entity import DrohnenspotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [
            HomeElevationSensor(coordinator, entry),
            BestSpotSensor(coordinator, entry),
        ]
    )


class HomeElevationSensor(DrohnenspotEntity, SensorEntity):
    """Geländehöhe am Heimat-Standort."""

    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:image-filter-hdr"
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "home_elevation")
        self._attr_name = "Höhe Heimat"

    @property
    def native_value(self) -> float | None:
        return (self.coordinator.data or {}).get("home", {}).get("elevation")


class BestSpotSensor(DrohnenspotEntity, SensorEntity):
    """Höhe des aktuell besten legalen Spots in der Nähe (alle 6 h aktualisiert)."""

    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_icon = "mdi:map-marker-star"
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "best_spot")
        self._attr_name = "Bester Spot in der Nähe"

    @property
    def native_value(self) -> float | None:
        spot = (self.coordinator.data or {}).get("best_spot")
        return spot.get("elevation_m") if spot else None

    @property
    def extra_state_attributes(self) -> dict:
        spot = (self.coordinator.data or {}).get("best_spot")
        if not spot:
            return {"attribution": ATTRIBUTION}
        return {
            "latitude": spot.get("latitude"),
            "longitude": spot.get("longitude"),
            "distance_km": spot.get("distance_km"),
            "prominence_m": spot.get("prominence_m"),
            "score": spot.get("score"),
            "attribution": ATTRIBUTION,
        }
