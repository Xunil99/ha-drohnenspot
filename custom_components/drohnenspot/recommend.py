"""Empfehlungs-Orchestrierung: Höhe zuerst, dann nur Top-Kandidaten zonenprüfen.

Verbindet die reine Logik (:mod:`spotfinder`) mit den I/O-Clients
(:mod:`elevation`, :mod:`dipul`). So bleibt die Last auf den öffentlichen
Diensten klein: ein paar Höhen-Batches + Zonen-Check nur für die besten
Kandidaten.
"""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

from .const import ATTRIBUTION
from .forest import (
    distance_to_polygons_m,
    near_road,
    nearest_poi,
    nearest_road_distance_m,
    point_in_forest,
)
from .spotfinder import Candidate, adaptive_spacing, build_grid, rank_candidates

_LOGGER = logging.getLogger(__name__)

_ZONE_CHECK_CONCURRENCY = 4  # schonend gegenüber DIPUL
_CLEARANCE_MARGIN_M = 2000.0  # OSM-Bbox-Erweiterung für den Freiraum


def _bbox(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """Bounding-Box (süd, west, nord, ost) um den Mittelpunkt."""
    dlat = radius_m / 111_195.0
    dlon = radius_m / (111_195.0 * max(0.01, math.cos(math.radians(lat))))
    return (lat - dlat, lon - dlon, lat + dlat, lon + dlon)


def _serialize(candidate: Candidate) -> dict[str, Any]:
    return {
        "latitude": round(candidate.lat, 6),
        "longitude": round(candidate.lon, 6),
        "elevation_m": round(candidate.elevation, 1),
        "prominence_m": round(candidate.prominence, 1),
        "distance_km": round(candidate.distance_from_center_m / 1000, 2),
        "score": round(candidate.score, 1),
        "restrictions": candidate.restrictions,
    }


async def async_find_spots(
    dipul: Any,
    elevation: Any,
    lat: float,
    lon: float,
    radius_m: float,
    count: int,
    min_elevation: float | None = None,
    restriction_layers: list[str] | None = None,
    forest: Any = None,
    exclude_forest: bool = True,
    require_road_access: bool = True,
    max_road_distance_m: float = 200.0,
    poi_bonus: bool = True,
    poi_bonus_radius_m: float = 500.0,
    poi_categories: list[str] | None = None,
    min_clearance_m: float = 0.0,
) -> dict[str, Any]:
    """Beste legale, hoch gelegene Spots im Umkreis finden."""
    spacing = adaptive_spacing(radius_m)
    grid = build_grid(lat, lon, radius_m, spacing)
    await elevation.fetch_grid(grid)

    # Etwas mehr Kandidaten als nötig küren, damit nach den Filtern
    # noch genug übrig bleibt.
    over = max(count * 4, count + 8)
    candidates = rank_candidates(grid, top_k=over, min_elevation=min_elevation)

    # Wald, Wege UND Sehenswertes in EINER Overpass-Abfrage holen (best-effort).
    osm: dict[str, list] = {"forest": [], "roads": [], "pois": [], "avoid": []}
    if forest is not None and (
        exclude_forest or require_road_access or poi_bonus or min_clearance_m
    ):
        # Bbox erweitern, damit Wohngebiete/Naturschutz knapp außerhalb mitzählen.
        osm = await forest.fetch_osm(
            _bbox(lat, lon, radius_m + _CLEARANCE_MARGIN_M), poi_categories
        )
    roads = osm["roads"]
    avoid = osm.get("avoid", [])

    # Wald-Spots vorab lokal aussortieren (spart spätere DIPUL-Abfragen).
    forest_excluded = 0
    if exclude_forest and osm["forest"]:
        before = len(candidates)
        candidates = [
            c for c in candidates if not point_in_forest(c.lat, c.lon, osm["forest"])
        ]
        forest_excluded = before - len(candidates)

    # Schlecht erreichbare Spots (zu weit von Straße/Weg) aussortieren.
    road_excluded = 0
    if require_road_access and roads:
        before = len(candidates)
        candidates = [
            c for c in candidates if near_road(c.lat, c.lon, roads, max_road_distance_m)
        ]
        road_excluded = before - len(candidates)

    sem = asyncio.Semaphore(_ZONE_CHECK_CONCURRENCY)

    async def _check(candidate: Candidate) -> Candidate:
        async with sem:
            hits = await dipul.query_point(candidate.lat, candidate.lon, restriction_layers)
        from .dipul import summarize_restrictions

        candidate.restrictions = summarize_restrictions(hits)
        candidate.restricted = bool(hits)
        return candidate

    checked = await asyncio.gather(
        *(_check(c) for c in candidates), return_exceptions=True
    )
    valid = [c for c in checked if isinstance(c, Candidate)]
    failures = len(checked) - len(valid)
    if failures:
        _LOGGER.warning("%s Zonen-Prüfungen fehlgeschlagen", failures)

    clear = [c for c in valid if not c.restricted]

    # Freiraum-Filter: nur Spots mit genug Abstand zu Wohngebiet/Naturschutz.
    if min_clearance_m and avoid:
        clear = [
            c
            for c in clear
            if distance_to_polygons_m(c.lat, c.lon, avoid) >= min_clearance_m
        ]

    # Sehenswertes-POI je Kandidat — nur fliegbare POIs (nicht in Wohn-/Schutzzone).
    pois = osm["pois"] if poi_bonus else []
    if pois and avoid:
        pois = [p for p in pois if not point_in_forest(p["lat"], p["lon"], avoid)]
    enriched = []
    for c in clear:
        poi, dist = nearest_poi(c.lat, c.lon, pois) if pois else (None, float("inf"))
        enriched.append((c, poi, dist, dist <= poi_bonus_radius_m))

    # Starke Bevorzugung: Spots nahe Sehenswertem zuerst, dann nach Prominenz,
    # dann nach Höhe.
    enriched.sort(
        key=lambda t: (1 if t[3] else 0, t[0].prominence, t[0].elevation),
        reverse=True,
    )
    top = enriched[:count]

    spots_out = []
    for c, poi, dist, near in top:
        item = _serialize(c)
        if roads:
            d = nearest_road_distance_m(c.lat, c.lon, roads)
            item["road_distance_m"] = round(d) if d != float("inf") else None
        else:
            item["road_distance_m"] = None
        if avoid:
            cl = distance_to_polygons_m(c.lat, c.lon, avoid)
            item["clearance_m"] = round(cl) if cl != float("inf") else None
        else:
            item["clearance_m"] = None
        if poi is not None and dist != float("inf"):
            item["poi"] = {
                "kind": poi["kind"],
                "name": poi.get("name", ""),
                "subtype": poi.get("subtype"),
                "wiki": poi.get("wiki"),
                "latitude": round(poi["lat"], 6),
                "longitude": round(poi["lon"], 6),
                "distance_m": round(dist),
            }
            item["near_poi"] = bool(near)
        else:
            item["poi"] = None
            item["near_poi"] = False
        spots_out.append(item)

    return {
        "spots": spots_out,
        "found": len(spots_out),
        "candidates_evaluated": len(candidates),
        "zones_checked": len(valid),
        "forest_excluded": forest_excluded,
        "road_excluded": road_excluded,
        "center": {"latitude": round(lat, 6), "longitude": round(lon, 6)},
        "radius_km": round(radius_m / 1000, 1),
        "attribution": ATTRIBUTION,
        "disclaimer": (
            "Orientierungshilfe, keine Rechtsgarantie. Vor dem Start stets "
            "Drohnenklasse, A1/A2/A3, 120 m AGL, Sichtflug (VLOS) und aktuelle "
            "NOTAM/Betriebseinschränkungen prüfen (z. B. DIPUL-Volume-Planner)."
        ),
    }
