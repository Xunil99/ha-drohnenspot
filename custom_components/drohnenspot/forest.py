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
import math
from typing import Any, Iterable

_LOGGER = logging.getLogger(__name__)

DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_DEG_M = 111_195.0
# Diese Wegtypen zählen NICHT als Zugang (kein Halten möglich).
_ROAD_SKIP = {"motorway", "trunk", "motorway_link", "trunk_link"}

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
        f'way["highway"]({b});'
        f'node["tourism"="viewpoint"]({b});'
        f'node["natural"="peak"]({b});'
        f'nwr["historic"]({b});'
        f'node["man_made"="tower"]["tower:type"="observation"]({b});'
        ");"
        "out geom;"
    )


def build_pois_query(bbox: tuple[float, float, float, float]) -> str:
    """Overpass-QL nur für Sehenswertes-POIs (für die Karten-Ebene)."""
    s, w, n, e = bbox
    b = f"{s},{w},{n},{e}"
    return (
        "[out:json][timeout:25];"
        "("
        f'node["tourism"="viewpoint"]({b});'
        f'node["natural"="peak"]({b});'
        f'nwr["historic"]({b});'
        f'node["man_made"="tower"]["tower:type"="observation"]({b});'
        ");"
        "out tags center;"
    )


def _is_forest(tags: dict[str, Any]) -> bool:
    return tags.get("landuse") == "forest" or tags.get("natural") == "wood"


def parse_overpass_forest(data: dict[str, Any]) -> list[list[tuple[float, float]]]:
    """Wald-Elemente der Overpass-Antwort in Polygone [(lat, lon), …] wandeln.

    Tag-bewusst (nur ``landuse=forest`` / ``natural=wood``), damit aus einer
    kombinierten Antwort (Wald + Wege) nur die Waldflächen kommen. Ways direkt;
    bei Relationen nur die Außenringe (Innenringe = Lichtungen ausgelassen).
    """
    polys: list[list[tuple[float, float]]] = []
    for el in (data or {}).get("elements", []):
        if not _is_forest(el.get("tags", {})):
            continue
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


def parse_overpass_roads(data: dict[str, Any]) -> list[list[tuple[float, float]]]:
    """Wege-Elemente (``highway=*``) in Polylinien [(lat, lon), …] wandeln.

    Autobahnen/Schnellstraßen (kein Halten) werden übersprungen.
    """
    lines: list[list[tuple[float, float]]] = []
    for el in (data or {}).get("elements", []):
        hw = el.get("tags", {}).get("highway")
        if not hw or hw in _ROAD_SKIP:
            continue
        geom = el.get("geometry")
        if not geom:
            continue
        line = [(p["lat"], p["lon"]) for p in geom if "lat" in p and "lon" in p]
        if len(line) >= 2:
            lines.append(line)
    return lines


def _to_xy(plat: float, plon: float, lat: float, lon: float) -> tuple[float, float]:
    """Lokale Meter-Koordinaten relativ zu (plat, plon) (äquirektangulär)."""
    x = (lon - plon) * _DEG_M * math.cos(math.radians(plat))
    y = (lat - plat) * _DEG_M
    return x, y


def distance_point_to_segment_m(
    plat: float, plon: float, a: tuple[float, float], b: tuple[float, float]
) -> float:
    """Abstand (m) von (plat, plon) zur Strecke a–b [(lat, lon)]."""
    ax, ay = _to_xy(plat, plon, a[0], a[1])
    bx, by = _to_xy(plat, plon, b[0], b[1])
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 == 0.0:
        return math.hypot(ax, ay)
    t = max(0.0, min(1.0, -(ax * dx + ay * dy) / seg2))
    return math.hypot(ax + t * dx, ay + t * dy)


def nearest_road_distance_m(
    lat: float, lon: float, lines: Iterable[Iterable[tuple[float, float]]]
) -> float:
    """Kürzester Abstand (m) zu irgendeiner Weg-Polylinie; ``inf`` wenn keine."""
    best = float("inf")
    for line in lines:
        pts = list(line)
        for i in range(len(pts) - 1):
            d = distance_point_to_segment_m(lat, lon, pts[i], pts[i + 1])
            if d < best:
                best = d
    return best


def near_road(
    lat: float,
    lon: float,
    lines: Iterable[Iterable[tuple[float, float]]],
    max_m: float,
) -> bool:
    """Liegt der Punkt ≤ ``max_m`` an einer Straße/einem Weg?"""
    return nearest_road_distance_m(lat, lon, lines) <= max_m


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Abstand zweier Koordinaten in Metern (äquirektangulär, für kurze Distanzen)."""
    x, y = _to_xy(lat1, lon1, lat2, lon2)
    return math.hypot(x, y)


def _poi_kind(tags: dict[str, Any]) -> str | None:
    if tags.get("tourism") == "viewpoint":
        return "viewpoint"
    if tags.get("natural") == "peak":
        return "peak"
    if tags.get("man_made") == "tower" and tags.get("tower:type") == "observation":
        return "tower"
    if tags.get("historic"):
        return "historic"
    return None


def _centroid(geom: list) -> tuple[float, float] | None:
    lats = [p["lat"] for p in geom if "lat" in p]
    lons = [p["lon"] for p in geom if "lon" in p]
    if not lats:
        return None
    return sum(lats) / len(lats), sum(lons) / len(lons)


def parse_overpass_pois(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Sehenswertes-POIs als [{lat, lon, kind, name}] aus der Antwort lesen."""
    pois: list[dict[str, Any]] = []
    for el in (data or {}).get("elements", []):
        kind = _poi_kind(el.get("tags", {}))
        if not kind:
            continue
        if el.get("type") == "node" and "lat" in el:
            lat, lon = el["lat"], el["lon"]
        elif "center" in el:
            lat, lon = el["center"]["lat"], el["center"]["lon"]
        elif el.get("geometry"):
            c = _centroid(el["geometry"])
            if c is None:
                continue
            lat, lon = c
        else:
            continue
        pois.append(
            {"lat": lat, "lon": lon, "kind": kind, "name": el["tags"].get("name", "")}
        )
    return pois


def nearest_poi(
    lat: float, lon: float, pois: Iterable[dict[str, Any]]
) -> tuple[dict[str, Any] | None, float]:
    """Nächsten POI + Abstand (m) finden; (None, inf) wenn keine."""
    best: dict[str, Any] | None = None
    best_d = float("inf")
    for p in pois:
        d = distance_m(lat, lon, p["lat"], p["lon"])
        if d < best_d:
            best_d = d
            best = p
    return best, best_d


class ForestClient:
    """Best-effort Overpass-Client für Waldflächen."""

    def __init__(self, session: Any, url: str = DEFAULT_OVERPASS_URL) -> None:
        self._session = session
        self._url = url

    async def fetch_osm(
        self, bbox: tuple[float, float, float, float]
    ) -> dict[str, list[list[tuple[float, float]]]]:
        """Wald-Polygone UND Wege-Linien in einem Aufruf holen.

        Bei Fehler/Timeout: leere Listen (best-effort, keine Filterung).
        """
        query = build_overpass_query(bbox)
        try:
            async with self._session.post(self._url, data=query, timeout=35) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except Exception as err:  # noqa: BLE001 — best-effort
            _LOGGER.warning("Overpass/OSM-Abfrage fehlgeschlagen: %s", err)
            return {"forest": [], "roads": [], "pois": []}
        return {
            "forest": parse_overpass_forest(data),
            "roads": parse_overpass_roads(data),
            "pois": parse_overpass_pois(data),
        }

    async def fetch_pois(
        self, bbox: tuple[float, float, float, float]
    ) -> list[dict[str, Any]]:
        """Nur Sehenswertes-POIs in bbox (für die Karten-Ebene). Best-effort."""
        query = build_pois_query(bbox)
        try:
            async with self._session.post(self._url, data=query, timeout=35) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Overpass/POI-Abfrage fehlgeschlagen: %s", err)
            return []
        return parse_overpass_pois(data)

    async def fetch_polygons(
        self, bbox: tuple[float, float, float, float]
    ) -> list[list[tuple[float, float]]]:
        """Nur Waldflächen (Rückwärtskompatibilität)."""
        return (await self.fetch_osm(bbox))["forest"]
