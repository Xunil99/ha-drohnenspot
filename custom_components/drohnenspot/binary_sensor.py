"""Binärsensor: liegt der Heimat-Standort in einer Verbotszone?"""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
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
    async_add_entities([DrohnenspotRestrictedBinarySensor(coordinator, entry)])


class DrohnenspotRestrictedBinarySensor(DrohnenspotEntity, BinarySensorEntity):
    """An, wenn die Heimat in mindestens einer Verbots-/Genehmigungszone liegt."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_icon = "mdi:airplane-alert"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "restricted")
        self._attr_name = "Heimat in Verbotszone"

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.data or {}).get("home", {}).get("restricted"))

    @property
    def extra_state_attributes(self) -> dict:
        home = (self.coordinator.data or {}).get("home", {})
        return {
            "restrictions": home.get("restrictions", []),
            "attribution": ATTRIBUTION,
        }
