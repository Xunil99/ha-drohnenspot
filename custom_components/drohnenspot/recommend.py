"""Empfehlungs-Orchestrierung: Höhe zuerst, dann nur Top-Kandidaten zonenprüfen.

Verbindet die reine Logik (:mod:`spotfinder`) mit den I/O-Clients
(:mod:`elevation`, :mod:`dipul`). So bleibt die Last auf den öffentlichen
Diensten klein: ein paar Höhen-Batches + Zonen-Check nur für die besten
Kandidaten.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .const import ATTRIBUTION
from .spotfinder import Candidate, adaptive_spacing, build_grid, rank_candidates

_LOGGER = logging.getLogger(__name__)

_ZONE_CHECK_CONCURRENCY = 4  # schonend gegenüber DIPUL


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
) -> dict[str, Any]:
    """Beste legale, hoch gelegene Spots im Umkreis finden."""
    spacing = adaptive_spacing(radius_m)
    grid = build_grid(lat, lon, radius_m, spacing)
    await elevation.fetch_grid(grid)

    # Etwas mehr Kandidaten als nötig küren, damit nach dem Zonen-Filter
    # noch genug übrig bleibt.
    over = max(count * 4, count + 8)
    candidates = rank_candidates(grid, top_k=over, min_elevation=min_elevation)

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
    clear.sort(key=lambda c: (c.score, c.elevation), reverse=True)
    spots = clear[:count]

    return {
        "spots": [_serialize(c) for c in spots],
        "found": len(spots),
        "candidates_evaluated": len(candidates),
        "zones_checked": len(valid),
        "center": {"latitude": round(lat, 6), "longitude": round(lon, 6)},
        "radius_km": round(radius_m / 1000, 1),
        "attribution": ATTRIBUTION,
        "disclaimer": (
            "Orientierungshilfe, keine Rechtsgarantie. Vor dem Start stets "
            "Drohnenklasse, A1/A2/A3, 120 m AGL, Sichtflug (VLOS) und aktuelle "
            "NOTAM/Betriebseinschränkungen prüfen (z. B. DIPUL-Volume-Planner)."
        ),
    }
