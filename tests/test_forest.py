"""Tests für Wald-Erkennung (reine Punkt-in-Polygon-Logik + Overpass-Parser)."""
from __future__ import annotations

import forest

# Quadrat in (lat, lon): lat 50..51, lon 6..7
SQUARE = [(50.0, 6.0), (50.0, 7.0), (51.0, 7.0), (51.0, 6.0), (50.0, 6.0)]


# --- point_in_ring ---------------------------------------------------------

def test_point_in_ring_inside():
    assert forest.point_in_ring(50.5, 6.5, SQUARE) is True


def test_point_in_ring_outside_east():
    assert forest.point_in_ring(50.5, 8.0, SQUARE) is False


def test_point_in_ring_outside_north():
    assert forest.point_in_ring(52.0, 6.5, SQUARE) is False


def test_point_in_ring_degenerate():
    assert forest.point_in_ring(50.5, 6.5, [(50.0, 6.0), (50.0, 7.0)]) is False


# --- point_in_forest -------------------------------------------------------

def test_point_in_forest_any():
    other = [(48.0, 10.0), (48.0, 11.0), (49.0, 11.0), (49.0, 10.0)]
    assert forest.point_in_forest(50.5, 6.5, [other, SQUARE]) is True


def test_point_in_forest_none():
    assert forest.point_in_forest(40.0, 0.0, [SQUARE]) is False


def test_point_in_forest_empty():
    assert forest.point_in_forest(50.5, 6.5, []) is False


# --- parse_overpass_forest -------------------------------------------------

WAY_SAMPLE = {
    "elements": [
        {
            "type": "way",
            "id": 1,
            "geometry": [
                {"lat": 50.0, "lon": 6.0},
                {"lat": 50.0, "lon": 7.0},
                {"lat": 51.0, "lon": 7.0},
                {"lat": 51.0, "lon": 6.0},
                {"lat": 50.0, "lon": 6.0},
            ],
        }
    ]
}

REL_SAMPLE = {
    "elements": [
        {
            "type": "relation",
            "id": 2,
            "members": [
                {
                    "type": "way",
                    "role": "outer",
                    "geometry": [
                        {"lat": 50.0, "lon": 6.0},
                        {"lat": 50.0, "lon": 7.0},
                        {"lat": 51.0, "lon": 7.0},
                        {"lat": 51.0, "lon": 6.0},
                        {"lat": 50.0, "lon": 6.0},
                    ],
                },
                {
                    "type": "way",
                    "role": "inner",
                    "geometry": [
                        {"lat": 50.4, "lon": 6.4},
                        {"lat": 50.4, "lon": 6.6},
                        {"lat": 50.6, "lon": 6.6},
                        {"lat": 50.6, "lon": 6.4},
                        {"lat": 50.4, "lon": 6.4},
                    ],
                },
            ],
        }
    ]
}


def test_parse_way_geometry():
    polys = forest.parse_overpass_forest(WAY_SAMPLE)
    assert len(polys) == 1
    assert (50.0, 6.0) in polys[0]


def test_parse_relation_outer_only():
    # Nur Außenring (outer) zählt; Innenring (Lichtung) wird übersprungen.
    polys = forest.parse_overpass_forest(REL_SAMPLE)
    assert len(polys) == 1


def test_parse_empty():
    assert forest.parse_overpass_forest({"elements": []}) == []
    assert forest.parse_overpass_forest({}) == []


def test_parse_then_contains():
    polys = forest.parse_overpass_forest(WAY_SAMPLE)
    assert forest.point_in_forest(50.5, 6.5, polys) is True
    assert forest.point_in_forest(55.0, 6.5, polys) is False
