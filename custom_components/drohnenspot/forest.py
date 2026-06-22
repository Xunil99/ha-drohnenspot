"""Wald-Erkennung über OpenStreetMap (Overpass).

Eine Overpass-Abfrage pro Suche holt die Waldflächen (``landuse=forest`` /
``natural=wood``) in der Such-Bounding-Box; danach wird rein lokal per
Punkt-in-Polygon geprüft, ob ein Kandidat im Wald liegt. So nur ein externer
Aufruf, keine schweren Geo-Abhängigkeiten, und die Kernlogik ist testbar.

Best-effort: Fällt Overpass aus, wird einfach nicht gefiltert.
``aiohttp`` wird nicht importiert (Session kommt von Home Assistant).
"""
from __future__ import annotations

import logging
from typing import Any, Iterable

_LOGGER = logging.getLogger(__name__)

DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

Ring = list  # list[tuple[float, float]] — (lat, lon)


def point_in_ring(lat: float, lon: float, ring: Iterable[tuple[float, float]]) -> bool:
    """Ray-Casting: Liegt (lat, lon) im Polygon ``ring`` [(lat, lon), …]?"""
    pts = list(ring)
    n = len(pts)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        yi, xi = pts[i][0], pts[i][1]
        yj, xj = pts[j][0], pts[j][1]
        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


def point_in_forest(
    lat: float, lon: float, polygons: Iterable[Iterable[tuple[float, float]]]
) -> bool:
    """Liegt der Punkt in mindestens einem der Wald-Polygone?"""
    for ring in polygons:
        if point_in_ring(lat, lon, ring):
            return True
    return False


def build_overpass_query(bbox: tuple[float, float, float, float]) -> str:
    """Overpass-QL für Waldflächen in bbox = (süd, west, nord, ost)."""
    s, w, n, e = bbox
    b = f"{s},{w},{n},{e}"
    return (
        "[out:json][timeout:25];"
        "("
        f'way["landuse"="forest"]({b});'
        f'way["natural"="wood"]({b});'
        f'relation["landuse"="forest"]({b});'
        f'relation["natural"="wood"]({b});'
        ");"
        "out geom;"
    )


def parse_overpass_forest(data: dict[str, Any]) -> list[list[tuple[float, float]]]:
    """Overpass-JSON in eine Liste von Polygonen [(lat, lon), …] wandeln.

    Ways direkt; bei Relationen nur die Außenringe (``outer``) — Innenringe
    (Lichtungen) werden bewusst ausgelassen.
    """
    polys: list[list[tuple[float, float]]] = []
    for el in (data or {}).get("elements", []):
        geom = el.get("geometry")
        if geom:
            ring = [(p["lat"], p["lon"]) for p in geom if "lat" in p and "lon" in p]
            if len(ring) >= 3:
                polys.append(ring)
        for member in el.get("members", []) or []:
            if member.get("role") not in ("outer", "", None):
                continue
            mgeom = member.get("geometry")
            if not mgeom:
                continue
            ring = [(p["lat"], p["lon"]) for p in mgeom if "lat" in p and "lon" in p]
            if len(ring) >= 3:
                polys.append(ring)
    return polys


class ForestClient:
    """Best-effort Overpass-Client für Waldflächen."""

    def __init__(self, session: Any, url: str = DEFAULT_OVERPASS_URL) -> None:
        self._session = session
        self._url = url

    async def fetch_polygons(
        self, bbox: tuple[float, float, float, float]
    ) -> list[list[tuple[float, float]]]:
        """Waldflächen in bbox holen. Bei Fehler/Timeout: leere Liste."""
        query = build_overpass_query(bbox)
        try:
            async with self._session.post(
                self._url, data=query, timeout=35
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except Exception as err:  # noqa: BLE001 — best-effort
            _LOGGER.warning("Overpass/Wald-Abfrage fehlgeschlagen: %s", err)
            return []
        return parse_overpass_forest(data)
