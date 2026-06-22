"""Tests für Wald-/Wege-Erkennung (PIP, Punkt-zu-Linie, Overpass-Parser)."""
from __future__ import annotations

import math

import pytest

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
            "tags": {"landuse": "forest"},
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
            "tags": {"natural": "wood"},
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


def test_parse_forest_is_tag_aware():
    # Eine Straße (highway) darf NICHT als Waldpolygon gelten.
    road = {
        "elements": [
            {
                "type": "way",
                "id": 9,
                "tags": {"highway": "track"},
                "geometry": [{"lat": 50.0, "lon": 6.0}, {"lat": 50.0, "lon": 6.1}],
            }
        ]
    }
    assert forest.parse_overpass_forest(road) == []


# --- Wege / Abstand ---------------------------------------------------------

ROADS_SAMPLE = {
    "elements": [
        {
            "type": "way",
            "id": 10,
            "tags": {"highway": "track"},
            "geometry": [{"lat": 50.0, "lon": 6.0}, {"lat": 50.0, "lon": 6.01}],
        },
        {
            "type": "way",
            "id": 11,
            "tags": {"highway": "motorway"},
            "geometry": [{"lat": 50.0, "lon": 7.0}, {"lat": 50.0, "lon": 7.01}],
        },
        {
            "type": "way",
            "id": 12,
            "tags": {"landuse": "forest"},  # kein highway -> kein Weg
            "geometry": [{"lat": 50.0, "lon": 8.0}, {"lat": 50.0, "lon": 8.01}],
        },
    ]
}


def test_parse_roads_includes_track_skips_motorway_and_nonroad():
    lines = forest.parse_overpass_roads(ROADS_SAMPLE)
    assert len(lines) == 1  # nur der track
    assert lines[0][0] == (50.0, 6.0)


def test_distance_point_on_segment_is_zero():
    d = forest.distance_point_to_segment_m(50.0, 6.005, (50.0, 6.0), (50.0, 6.01))
    assert d == pytest.approx(0.0, abs=2.0)


def test_distance_point_north_of_segment():
    # 0.001° Breite ~ 111 m nördlich der Linie
    d = forest.distance_point_to_segment_m(50.001, 6.005, (50.0, 6.0), (50.0, 6.01))
    assert d == pytest.approx(111.0, rel=0.1)


def test_distance_beyond_endpoint_clamps():
    # Punkt östlich des Endpunkts (6.01) -> Abstand zum Endpunkt
    d = forest.distance_point_to_segment_m(50.0, 6.02, (50.0, 6.0), (50.0, 6.01))
    expected = 0.01 * 111195.0 * math.cos(math.radians(50.0))
    assert d == pytest.approx(expected, rel=0.1)


def test_nearest_road_distance_and_near():
    lines = forest.parse_overpass_roads(ROADS_SAMPLE)
    near = forest.nearest_road_distance_m(50.001, 6.005, lines)
    assert near == pytest.approx(111.0, rel=0.1)
    assert forest.near_road(50.001, 6.005, lines, 200.0) is True
    assert forest.near_road(50.001, 6.005, lines, 50.0) is False


def test_nearest_road_distance_empty_is_inf():
    assert forest.nearest_road_distance_m(50.0, 6.0, []) == float("inf")
    assert forest.near_road(50.0, 6.0, [], 200.0) is False
