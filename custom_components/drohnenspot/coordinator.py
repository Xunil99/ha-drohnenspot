"""DataUpdateCoordinator: prüft periodisch den Heimat-Standort.

Günstige, zuverlässige Abfrage (Heimat in Zone? + Höhe) im 6-Stunden-Takt,
plus ein bester Spot pro Aktualisierung (in einen try/except gekapselt,
damit ein fehlgeschlagener Suchlauf die Sensoren nicht lahmlegt).
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_MIN_ELEVATION,
    CONF_RADIUS_KM,
    CONF_SPOT_COUNT,
    DEFAULT_MIN_ELEVATION,
    DEFAULT_RADIUS_KM,
    DEFAULT_SPOT_COUNT,
    DOMAIN,
    UPDATE_INTERVAL_HOURS,
)
from .dipul import DipulClient, summarize_restrictions
from .elevation import ElevationClient
from .recommend import async_find_spots

_LOGGER = logging.getLogger(__name__)


class DrohnenspotCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Hält die Heimat-Lagebeurteilung und den besten Spot in der Nähe aktuell."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        dipul: DipulClient,
        elevation: ElevationClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=UPDATE_INTERVAL_HOURS),
        )
        self.entry = entry
        self.dipul = dipul
        self.elevation = elevation

    def _opt(self, key: str, default: Any) -> Any:
        return self.entry.options.get(key, self.entry.data.get(key, default))

    @property
    def latitude(self) -> float:
        return self._opt("latitude", self.hass.config.latitude)

    @property
    def longitude(self) -> float:
        return self._opt("longitude", self.hass.config.longitude)

    async def _async_update_data(self) -> dict[str, Any]:
        lat, lon = self.latitude, self.longitude
        try:
            hits = await self.dipul.query_point(lat, lon)
            elevation = await self.elevation.point(lat, lon)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Abruf fehlgeschlagen: {err}") from err

        home = {
            "restricted": bool(hits),
            "restrictions": summarize_restrictions(hits),
            "elevation": elevation,
            "latitude": lat,
            "longitude": lon,
        }

        best_spot: dict[str, Any] | None = None
        try:
            radius_km = float(self._opt(CONF_RADIUS_KM, DEFAULT_RADIUS_KM))
            min_elev = float(self._opt(CONF_MIN_ELEVATION, DEFAULT_MIN_ELEVATION))
            result = await async_find_spots(
                self.dipul,
                self.elevation,
                lat,
                lon,
                radius_km * 1000.0,
                count=1,
                min_elevation=min_elev or None,
            )
            spots = result.get("spots") or []
            if spots:
                best_spot = spots[0]
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Bester-Spot-Suche fehlgeschlagen: %s", err)

        return {"home": home, "best_spot": best_spot}
