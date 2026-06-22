"""Tests für den DIPUL-WMS-GetFeatureInfo-Parser (text/plain)."""
from __future__ import annotations

import dipul


SAMPLE_ONE_HIT = """\
Results for FeatureType 'dipul:kontrollzonen':
--------------------------------------------
geometrie = [GEOMETRY (MultiPolygon) with 482 points]
name = CTR Frankfurt
art = Kontrollzone
--------------------------------------------
"""

SAMPLE_MIXED = SAMPLE_ONE_HIT + """
Results for FeatureType 'dipul:naturschutzgebiete':
--------------------------------------------
--------------------------------------------
"""

SAMPLE_MULTI = """\
Results for FeatureType 'dipul:wohngrundstuecke':
--------------------------------------------
geometrie = [GEOMETRY (Polygon)]
--------------------------------------------

Results for FeatureType 'dipul:naturschutzgebiete':
--------------------------------------------
geometrie = [GEOMETRY (MultiPolygon)]
name = NSG Beispiel
--------------------------------------------
"""

SAMPLE_EMPTY = ""
SAMPLE_NO_FEATURES = "no features were found\n"

# Reales Antwortformat des Live-Dienstes (Flughafen Frankfurt), verifiziert
# am 2026-06-22. Beachte das echte Präfix 'de.dfs.dipul:' und 'geom ='.
SAMPLE_REAL_FRANKFURT = """\
Results for FeatureType 'de.dfs.dipul:kontrollzonen':
--------------------------------------------
geom = [GEOMETRY (Polygon) with 111 points]
legal_ref = § 21h, Abs. 3 (9.) LuftVO
name = FRANKFURT (CTR)
type_code = KONTROLLZONE
--------------------------------------------
Results for FeatureType 'de.dfs.dipul:flughaefen':
--------------------------------------------
geom = [GEOMETRY (Polygon) with 190 points]
name = FRANKFURT MAIN
type_code = FLUGHAFEN
--------------------------------------------
"""


def test_parse_single_hit():
    assert dipul.parse_getfeatureinfo_text(SAMPLE_ONE_HIT) == {"kontrollzonen"}


def test_parse_ignores_empty_layer_section():
    # naturschutzgebiete-Sektion ist leer -> kein Treffer
    assert dipul.parse_getfeatureinfo_text(SAMPLE_MIXED) == {"kontrollzonen"}


def test_parse_multiple_hits():
    assert dipul.parse_getfeatureinfo_text(SAMPLE_MULTI) == {
        "wohngrundstuecke",
        "naturschutzgebiete",
    }


def test_parse_empty_response():
    assert dipul.parse_getfeatureinfo_text(SAMPLE_EMPTY) == set()


def test_parse_no_features_message():
    assert dipul.parse_getfeatureinfo_text(SAMPLE_NO_FEATURES) == set()


def test_parse_strips_workspace_prefix():
    text = "Results for FeatureType 'dipul:flughaefen':\n--\nname = EDDF\n--\n"
    assert dipul.parse_getfeatureinfo_text(text) == {"flughaefen"}


def test_parse_real_live_format():
    # Echtes 'de.dfs.dipul:'-Präfix muss korrekt auf den Layernamen reduziert werden.
    assert dipul.parse_getfeatureinfo_text(SAMPLE_REAL_FRANKFURT) == {
        "kontrollzonen",
        "flughaefen",
    }


# --- summarize_restrictions ------------------------------------------------

def test_summarize_maps_to_german_labels():
    labels = dipul.summarize_restrictions({"kontrollzonen", "naturschutzgebiete"})
    assert "Kontrollzone" in labels
    assert any("Naturschutz" in s for s in labels)


def test_summarize_unknown_layer_falls_back_to_name():
    labels = dipul.summarize_restrictions({"irgendwas_neues"})
    assert labels == ["irgendwas_neues"]


def test_summarize_sorted_and_deduped():
    labels = dipul.summarize_restrictions({"kontrollzonen", "kontrollzonen"})
    assert labels == ["Kontrollzone"]
