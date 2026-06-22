"""Höhendaten-Client (OpenTopoData, Standard-Datensatz EU-DEM).

Liefert Punkt- und Raster-Höhen über die öffentliche OpenTopoData-API.
Bewusst ohne schwere Abhängigkeiten (kein numpy/rasterio) — genau das macht
Ansatz A "schlank". Endpoint und Datensatz sind konfigurierbar (Self-Hosting
oder Wechsel auf BKG-DGM in v2 möglich).

Öffentliche API-Limits werden respektiert: max. 100 Punkte/Anfrage und
≤ 1 Anfrage/Sekunde (Drosselung zwischen den Batches).
``aiohttp`` wird nicht importiert; die Session kommt von Home Assistant.
"""
from __future__ import annotations

import asyncio
from typing import Any

DEFAULT_BASE_URL = "https://api.opentopodata.org/v1"
DEFAULT_DATASET = "eudem25m"
MAX_LOCATIONS_PER_REQUEST = 100
_THROTTLE_SECONDS = 1.1  # öffentliches Limit: 1 Anfrage/Sekunde


class ElevationClient:
    """Dünner OpenTopoData-Client mit Batching, Drosselung und Cache."""

    def __init__(
        self,
        session: Any,
        base_url: str = DEFAULT_BASE_URL,
        dataset: str = DEFAULT_DATASET,
    ) -> None:
        self._session = session
        self._base = base_url.rstrip("/")
        self._dataset = dataset
        self._cache: dict[tuple[float, float], float | None] = {}

    @staticmethod
    def _key(lat: float, lon: float) -> tuple[float, float]:
        return (round(lat, 4), round(lon, 4))

    async def fetch(self, coords: list[tuple[float, float]]) -> list[float | None]:
        """Höhen für viele Koordinaten holen (Reihenfolge bleibt erhalten)."""
        result: list[float | None] = [None] * len(coords)
        # nur noch nicht gecachte Punkte abfragen
        missing_idx = [i for i, c in enumerate(coords) if self._key(*c) not in self._cache]
        for i, c in enumerate(coords):
            cached = self._cache.get(self._key(*c))
            if cached is not None:
                result[i] = cached

        first = True
        for start in range(0, len(missing_idx), MAX_LOCATIONS_PER_REQUEST):
            batch_idx = missing_idx[start : start + MAX_LOCATIONS_PER_REQUEST]
            if not first:
                await asyncio.sleep(_THROTTLE_SECONDS)
            first = False
            locs = "|".join(f"{coords[i][0]:.6f},{coords[i][1]:.6f}" for i in batch_idx)
            url = f"{self._base}/{self._dataset}"
            async with self._session.get(
                url, params={"locations": locs}, timeout=30
            ) as resp:
                resp.raise_for_status()
                payload = await resp.json()
            results = payload.get("results") or []
            for i, item in zip(batch_idx, results):
                elev = item.get("elevation")
                value = float(elev) if elev is not None else None
                result[i] = value
                self._cache[self._key(*coords[i])] = value
        return result

    async def fetch_grid(self, grid: Any) -> None:
        """Alle Zellen eines :class:`spotfinder.Grid` mit Höhen befüllen."""
        cells = list(grid.cells.values())
        coords = [(c.lat, c.lon) for c in cells]
        elevations = await self.fetch(coords)
        for cell, elevation in zip(cells, elevations):
            cell.elevation = elevation

    async def point(self, lat: float, lon: float) -> float | None:
        """Höhe eines einzelnen Punktes."""
        return (await self.fetch([(lat, lon)]))[0]
