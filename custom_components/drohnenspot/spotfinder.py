"""Reine Spot-Such-Logik für ha-drohnenspot.

Bewusst frei von Home-Assistant- und I/O-Abhängigkeiten, damit die Logik
isoliert testbar ist. Ablauf der Empfehlung (Ansatz A, "schlank"):

1. Über den Suchradius wird ein Punktraster gelegt (``build_grid``).
2. Die Höhen werden extern (OpenTopoData) gefüllt.
3. ``rank_candidates`` findet lokale Gipfel, bewertet sie nach Höhe und
   Prominenz und liefert die Top-N — *ohne* externe Aufrufe.
4. Erst diese Top-N werden per DIPUL ``GetFeatureInfo`` auf Verbotszonen
   geprüft (siehe :mod:`dipul`).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

EARTH_RADIUS_M = 6_371_000.0
_DEG_LAT_M = 111_195.0  # Meter pro Grad Breite (Mittelwert)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Großkreis-Distanz zweier Koordinaten in Metern."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def adaptive_spacing(
    radius_m: float, max_points: int = 400, min_spacing: float = 200.0
) -> float:
    """Rasterabstand so wählen, dass grob ``max_points`` Punkte entstehen.

    Hält die Anzahl externer Höhen-Abrufe und damit die Last auf den
    öffentlichen Diensten in Schach. Ein Mindestabstand verhindert bei
    kleinen Radien ein unnötig feines (und langsames) Raster.
    """
    area = math.pi * radius_m * radius_m
    spacing = math.sqrt(area / max(1, max_points))
    return max(min_spacing, spacing)


@dataclass
class GridCell:
    """Ein Rasterpunkt mit (optional) bekannter Höhe."""

    i: int
    j: int
    lat: float
    lon: float
    elevation: float | None = None


@dataclass
class Grid:
    """Ein Punktraster, indiziert über ganzzahlige (i, j)-Koordinaten."""

    center_lat: float
    center_lon: float
    spacing_m: float
    cells: dict[tuple[int, int], GridCell] = field(default_factory=dict)

    _NEIGHBOR_OFFSETS = (
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1), (0, 1),
        (1, -1), (1, 0), (1, 1),
    )

    def neighbors8(self, i: int, j: int) -> list[GridCell]:
        """Die bis zu acht direkt benachbarten, existierenden Zellen."""
        out = []
        for di, dj in self._NEIGHBOR_OFFSETS:
            cell = self.cells.get((i + di, j + dj))
            if cell is not None:
                out.append(cell)
        return out

    @classmethod
    def from_matrix(
        cls,
        matrix: list[list[float | None]],
        center_lat: float,
        center_lon: float,
        spacing_m: float,
    ) -> "Grid":
        """Grid aus einer Höhenmatrix bauen (vor allem für Tests).

        Zeile = i (Nord→Süd), Spalte = j (West→Ost).
        """
        grid = cls(center_lat=center_lat, center_lon=center_lon, spacing_m=spacing_m)
        dlat = spacing_m / _DEG_LAT_M
        dlon = spacing_m / (_DEG_LAT_M * max(0.01, math.cos(math.radians(center_lat))))
        for i, row in enumerate(matrix):
            for j, value in enumerate(row):
                lat = center_lat - i * dlat
                lon = center_lon + j * dlon
                grid.cells[(i, j)] = GridCell(i=i, j=j, lat=lat, lon=lon, elevation=value)
        return grid


def build_grid(
    center_lat: float, center_lon: float, radius_m: float, spacing_m: float
) -> Grid:
    """Kreisförmiges Punktraster um das Zentrum (Mittelpunkt = Zelle (0, 0))."""
    grid = Grid(center_lat=center_lat, center_lon=center_lon, spacing_m=spacing_m)
    dlat = spacing_m / _DEG_LAT_M
    dlon = spacing_m / (_DEG_LAT_M * max(0.01, math.cos(math.radians(center_lat))))
    n = max(1, math.ceil(radius_m / spacing_m))
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            lat = center_lat + i * dlat
            lon = center_lon + j * dlon
            if haversine_m(center_lat, center_lon, lat, lon) <= radius_m + 1.0:
                grid.cells[(i, j)] = GridCell(i=i, j=j, lat=lat, lon=lon)
    return grid


@dataclass
class Candidate:
    """Ein bewerteter Spot-Kandidat."""

    lat: float
    lon: float
    elevation: float
    prominence: float
    score: float = 0.0
    # nach der Zonen-Prüfung (siehe Service-Handler) befüllt:
    restricted: bool | None = None
    restrictions: list[str] = field(default_factory=list)
    distance_from_center_m: float = 0.0


def rank_candidates(
    grid: Grid,
    top_k: int = 10,
    min_elevation: float | None = None,
    prominence_weight: float = 1.0,
) -> list[Candidate]:
    """Lokale Gipfel finden, bewerten und die besten ``top_k`` zurückgeben.

    Ein Kandidat ist ein lokaler Höhen-Gipfel (>= alle Nachbarn) mit positiver
    Prominenz gegenüber dem Nachbar-Mittel. Reine Plateaus und Hänge fallen
    damit weg. Score = Höhe + ``prominence_weight`` * Prominenz.
    """
    candidates: list[Candidate] = []
    for (i, j), cell in grid.cells.items():
        if cell.elevation is None:
            continue
        neigh = [n for n in grid.neighbors8(i, j) if n.elevation is not None]
        if not neigh:
            continue
        neigh_elev = [n.elevation for n in neigh]
        if cell.elevation < max(neigh_elev):
            continue  # kein lokaler Gipfel
        prominence = cell.elevation - (sum(neigh_elev) / len(neigh_elev))
        if prominence <= 0:
            continue  # Plateau / steigt nicht über die Umgebung
        if min_elevation is not None and cell.elevation < min_elevation:
            continue
        candidates.append(
            Candidate(
                lat=cell.lat,
                lon=cell.lon,
                elevation=cell.elevation,
                prominence=prominence,
                score=cell.elevation + prominence_weight * prominence,
                distance_from_center_m=haversine_m(
                    grid.center_lat, grid.center_lon, cell.lat, cell.lon
                ),
            )
        )
    # Nach Prominenz ordnen (wie stark der Punkt herausragt -> freie Rundumsicht),
    # bei Gleichstand nach Höhe.
    candidates.sort(key=lambda c: (c.prominence, c.elevation), reverse=True)
    return candidates[:top_k]
