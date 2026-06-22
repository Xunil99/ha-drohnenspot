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


# --- Sehenswertes (POIs) ----------------------------------------------------

POI_SAMPLE = {
    "elements": [
        {"type": "node", "id": 1, "lat": 48.90, "lon": 12.80,
         "tags": {"tourism": "viewpoint", "name": "Schöne Aussicht"}},
        {"type": "node", "id": 2, "lat": 48.95, "lon": 12.85,
         "tags": {"natural": "peak", "name": "Hügel"}},
        {"type": "way", "id": 3,
         "tags": {"historic": "castle", "name": "Burg Test"},
         "geometry": [
             {"lat": 48.80, "lon": 12.70}, {"lat": 48.80, "lon": 12.72},
             {"lat": 48.82, "lon": 12.72}, {"lat": 48.82, "lon": 12.70},
         ]},
        {"type": "node", "id": 4, "lat": 48.70, "lon": 12.60,
         "tags": {"man_made": "tower", "tower:type": "observation", "name": "Turm"}},
        {"type": "node", "id": 5, "lat": 48.60, "lon": 12.50,
         "tags": {"man_made": "tower"}},  # kein observation -> kein POI
        {"type": "way", "id": 6, "tags": {"highway": "track"},
         "geometry": [{"lat": 48.5, "lon": 12.4}, {"lat": 48.5, "lon": 12.41}]},
    ]
}


def test_parse_pois_kinds_and_filtering():
    pois = forest.parse_overpass_pois(POI_SAMPLE)
    kinds = sorted(p["kind"] for p in pois)
    assert kinds == ["historic", "peak", "tower", "viewpoint"]  # 4, ohne Nicht-POIs


def test_parse_pois_way_centroid():
    pois = forest.parse_overpass_pois(POI_SAMPLE)
    castle = next(p for p in pois if p["kind"] == "historic")
    assert castle["name"] == "Burg Test"
    assert castle["lat"] == pytest.approx(48.81, abs=0.01)
    assert castle["lon"] == pytest.approx(12.71, abs=0.01)


def test_parse_pois_empty():
    assert forest.parse_overpass_pois({"elements": []}) == []


def test_distance_m_one_thousandth_degree():
    assert forest.distance_m(48.9, 12.8, 48.901, 12.8) == pytest.approx(111.0, rel=0.1)


def test_nearest_poi_picks_closest():
    pois = forest.parse_overpass_pois(POI_SAMPLE)
    poi, dist = forest.nearest_poi(48.90, 12.80, pois)
    assert poi["kind"] == "viewpoint"
    assert dist == pytest.approx(0.0, abs=5.0)


def test_nearest_poi_empty():
    poi, dist = forest.nearest_poi(48.9, 12.8, [])
    assert poi is None
    assert dist == float("inf")


# --- Wikipedia-Link + Untertyp ---------------------------------------------

def test_wikipedia_url_direct_with_lang():
    assert (
        forest.wikipedia_url(wikipedia="de:Burg Falkenfels")
        == "https://de.wikipedia.org/wiki/Burg_Falkenfels"
    )


def test_wikipedia_url_direct_no_lang():
    assert (
        forest.wikipedia_url(wikipedia="Schloss Test")
        == "https://de.wikipedia.org/wiki/Schloss_Test"
    )


def test_wikipedia_url_english_prefix():
    assert (
        forest.wikipedia_url(wikipedia="en:Castle")
        == "https://en.wikipedia.org/wiki/Castle"
    )


def test_wikipedia_url_wikidata():
    assert forest.wikipedia_url(wikidata="Q42") == "https://www.wikidata.org/wiki/Q42"


def test_wikipedia_url_search_fallback():
    url = forest.wikipedia_url(name="Alte Burg")
    assert url.startswith("https://de.wikipedia.org/w/index.php?search=")
    assert "Alte" in url


def test_wikipedia_url_none():
    assert forest.wikipedia_url() is None


def test_parse_pois_subtype_and_search_wiki():
    pois = forest.parse_overpass_pois(POI_SAMPLE)
    castle = next(p for p in pois if p["kind"] == "historic")
    assert castle["subtype"] == "Burg/Schloss"  # historic=castle
    # kein wikipedia-Tag, aber Name -> Such-Link
    assert castle["wiki"].startswith("https://de.wikipedia.org/w/index.php?search=")


def test_parse_pois_wikipedia_direct():
    data = {
        "elements": [
            {"type": "node", "id": 7, "lat": 48.9, "lon": 12.8,
             "tags": {"historic": "ruins", "name": "Ruine X", "wikipedia": "de:Ruine X"}},
        ]
    }
    poi = forest.parse_overpass_pois(data)[0]
    assert poi["subtype"] == "Ruine"
    assert poi["wiki"] == "https://de.wikipedia.org/wiki/Ruine_X"


def test_parse_pois_viewpoint_has_no_subtype():
    pois = forest.parse_overpass_pois(POI_SAMPLE)
    vp = next(p for p in pois if p["kind"] == "viewpoint")
    assert vp["subtype"] is None
