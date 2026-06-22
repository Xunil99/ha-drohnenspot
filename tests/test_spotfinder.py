"""Tests für die reine Spot-Such-Logik (kein I/O, kein Home Assistant)."""
from __future__ import annotations

import math

import pytest

import spotfinder as sf


# --- haversine_m -----------------------------------------------------------

def test_haversine_zero():
    assert sf.haversine_m(52.0, 13.0, 52.0, 13.0) == pytest.approx(0.0, abs=1e-6)


def test_haversine_one_hundredth_degree_lat():
    # 0.01° Breite ~ 1111.95 m
    d = sf.haversine_m(52.0, 13.0, 52.01, 13.0)
    assert d == pytest.approx(1111.95, rel=0.01)


def test_haversine_symmetric():
    a = sf.haversine_m(48.1, 11.5, 48.2, 11.7)
    b = sf.haversine_m(48.2, 11.7, 48.1, 11.5)
    assert a == pytest.approx(b)


# --- adaptive_spacing ------------------------------------------------------

def test_adaptive_spacing_large_radius():
    # 10 km Radius, max 400 Punkte -> ~886 m
    s = sf.adaptive_spacing(10_000, max_points=400)
    assert 800 < s < 950


def test_adaptive_spacing_respects_minimum():
    # kleiner Radius -> Mindestabstand greift
    assert sf.adaptive_spacing(1_000, max_points=400, min_spacing=200.0) == 200.0


def test_adaptive_spacing_monotonic():
    assert sf.adaptive_spacing(20_000) > sf.adaptive_spacing(10_000)


# --- build_grid ------------------------------------------------------------

def test_build_grid_points_within_radius():
    grid = sf.build_grid(52.0, 13.0, 1_000.0, 200.0)
    cells = list(grid.cells.values())
    assert cells, "Grid darf nicht leer sein"
    for c in cells:
        d = sf.haversine_m(52.0, 13.0, c.lat, c.lon)
        assert d <= 1_000.0 + 1.0  # kleine numerische Toleranz


def test_build_grid_includes_center():
    grid = sf.build_grid(52.0, 13.0, 1_000.0, 200.0)
    assert (0, 0) in grid.cells
    center = grid.cells[(0, 0)]
    assert center.lat == pytest.approx(52.0)
    assert center.lon == pytest.approx(13.0)


def test_build_grid_count_plausible():
    grid = sf.build_grid(52.0, 13.0, 1_000.0, 200.0)
    # Kreisfläche / Zellfläche ~ pi*1e6 / 4e4 ~ 78
    assert 50 < len(grid.cells) < 130


# --- rank_candidates -------------------------------------------------------

@pytest.fixture
def two_peak_grid():
    # Zwei klar getrennte Gipfel: A=300 bei (1,1), B=250 bei (1,5)
    matrix = [
        [100, 100, 100, 100, 100, 100, 100],
        [100, 300, 100, 100, 100, 250, 100],
        [100, 100, 100, 100, 100, 100, 100],
    ]
    return sf.Grid.from_matrix(matrix, center_lat=52.0, center_lon=13.0, spacing_m=200.0)


def test_rank_finds_both_peaks_sorted(two_peak_grid):
    cands = sf.rank_candidates(two_peak_grid, top_k=10)
    assert len(cands) == 2
    assert cands[0].elevation == 300
    assert cands[1].elevation == 250


def test_rank_top_k_limits(two_peak_grid):
    cands = sf.rank_candidates(two_peak_grid, top_k=1)
    assert len(cands) == 1
    assert cands[0].elevation == 300


def test_rank_min_elevation_filters(two_peak_grid):
    cands = sf.rank_candidates(two_peak_grid, top_k=10, min_elevation=260)
    assert len(cands) == 1
    assert cands[0].elevation == 300


def test_rank_prominence_computed(two_peak_grid):
    cands = sf.rank_candidates(two_peak_grid, top_k=10)
    peak_a = cands[0]
    # Gipfel A=300, alle Nachbarn 100 -> Prominenz 200
    assert peak_a.prominence == pytest.approx(200.0)


def test_rank_ignores_cells_without_elevation():
    matrix = [
        [None, 100, None],
        [100, 300, 100],
        [None, 100, None],
    ]
    grid = sf.Grid.from_matrix(matrix, center_lat=52.0, center_lon=13.0, spacing_m=200.0)
    cands = sf.rank_candidates(grid, top_k=10)
    assert len(cands) == 1
    assert cands[0].elevation == 300


def test_rank_plateau_not_a_peak():
    # Reines Plateau hat keinen lokalen Gipfel -> keine Kandidaten
    matrix = [[100, 100, 100], [100, 100, 100], [100, 100, 100]]
    grid = sf.Grid.from_matrix(matrix, center_lat=52.0, center_lon=13.0, spacing_m=200.0)
    cands = sf.rank_candidates(grid, top_k=10)
    assert cands == []
