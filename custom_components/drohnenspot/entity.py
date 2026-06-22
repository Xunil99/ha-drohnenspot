"""Gemeinsame Entity-Basis (Gerätezuordnung)."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VERSION
from .coordinator import DrohnenspotCoordinator


class DrohnenspotEntity(CoordinatorEntity[DrohnenspotCoordinator]):
    """Basisklasse: bindet alle Entities an ein gemeinsames Gerät."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: DrohnenspotCoordinator, entry: ConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Drohnenspot",
            manufacturer="ha-drohnenspot",
            model="DIPUL · BKG · OpenTopoData",
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
        )
