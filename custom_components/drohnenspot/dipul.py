"""DIPUL-WMS-Client (DFS Digitale Plattform Unbemannte Luftfahrt).

Die offiziellen Geozonen nach § 21h LuftVO werden ausschließlich als
OGC-WMS bereitgestellt (Raster). Eine Punktabfrage "liegt X in einer Zone?"
geht daher über ``GetFeatureInfo``. DIPUL liefert dieses nur als
``text/plain``/``text/html`` (kein JSON) — deshalb der robuste Text-Parser.

Daten: © GeoBasis-DE / BKG, DFS — CC BY 4.0.
``aiohttp`` wird absichtlich nicht importiert (die Session kommt von Home
Assistant), damit Parser und Konstanten ohne HA testbar bleiben.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

DEFAULT_WMS_URL = "https://uas-betrieb.de/geoservices/dipul/wms"

# Deutsche Klartext-Bezeichnungen aller 34 DIPUL-Layer.
LAYER_LABELS: dict[str, str] = {
    "bahnanlagen": "Bahnanlage",
    "behoerden": "Behörde",
    "binnenwasserstrassen": "Binnenwasserstraße",
    "bundesautobahnen": "Bundesautobahn",
    "bundesstrassen": "Bundesstraße",
    "diplomatische_vertretungen": "Diplomatische Vertretung",
    "ffh-gebiete": "FFH-Gebiet (Natura 2000)",
    "flugbeschraenkungsgebiete": "Flugbeschränkungsgebiet",
    "flughaefen": "Flughafen",
    "flugplaetze": "Flugplatz",
    "freibaeder": "Freibad",
    "haengegleiter": "Hängegleiter-/Gleitschirmgelände",
    "inaktive_temporaere_betriebseinschraenkungen": "Inaktive temporäre Betriebseinschränkung",
    "industrieanlagen": "Industrieanlage",
    "internationale_organisationen": "Internationale Organisation",
    "justizvollzugsanstalten": "Justizvollzugsanstalt",
    "kontrollzonen": "Kontrollzone",
    "kraftwerke": "Kraftwerk",
    "krankenhaeuser": "Krankenhaus",
    "labore": "Labor",
    "militaerische_anlagen": "Militärische Anlage",
    "modellflugplaetze": "Modellflugplatz",
    "nationalparks": "Nationalpark",
    "naturschutzgebiete": "Naturschutzgebiet",
    "polizei": "Polizei",
    "schifffahrtsanlagen": "Schifffahrtsanlage",
    "seewasserstrassen": "Seewasserstraße",
    "sicherheitsbehoerden": "Sicherheitsbehörde",
    "stromleitungen": "Stromleitung",
    "temporaere_betriebseinschraenkungen": "Temporäre Betriebseinschränkung (NfZ)",
    "umspannwerke": "Umspannwerk",
    "vogelschutzgebiete": "Vogelschutzgebiet",
    "windkraftanlagen": "Windkraftanlage",
    "wohngrundstuecke": "Wohngrundstück",
}

ALL_LAYERS: tuple[str, ...] = tuple(LAYER_LABELS.keys())

# Standard-Auswahl für die "ist hier geflogen erlaubt?"-Prüfung: flächenhafte
# Verbots-/Genehmigungszonen. Bewusst konservativ. (Konfigurierbar in v2.)
DEFAULT_RESTRICTION_LAYERS: tuple[str, ...] = (
    "flugbeschraenkungsgebiete",
    "kontrollzonen",
    "flughaefen",
    "flugplaetze",
    "militaerische_anlagen",
    "temporaere_betriebseinschraenkungen",
    "naturschutzgebiete",
    "nationalparks",
    "vogelschutzgebiete",
    "ffh-gebiete",
    "wohngrundstuecke",
    "justizvollzugsanstalten",
    "krankenhaeuser",
    "kraftwerke",
    "umspannwerke",
    "industrieanlagen",
    "behoerden",
    "polizei",
    "sicherheitsbehoerden",
    "diplomatische_vertretungen",
    "internationale_organisationen",
    "labore",
)

_HEADER_RE = re.compile(r"Results for FeatureType '([^']+)':")


def _normalize(layer: str) -> str:
    """``dipul:kontrollzonen`` -> ``kontrollzonen``."""
    return layer.split(":", 1)[-1]


def parse_getfeatureinfo_text(text: str) -> set[str]:
    """GeoServer-``text/plain``-Antwort parsen.

    Liefert die Menge der Layer (ohne ``dipul:``-Präfix), für die am
    abgefragten Punkt mindestens ein Feature vorliegt. Robust gegenüber
    beiden GeoServer-Varianten (leere Sektionen vs. weggelassene Sektionen).
    """
    hits: set[str] = set()
    matches = list(_HEADER_RE.finditer(text))
    for idx, m in enumerate(matches):
        layer = _normalize(m.group(1))
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[start:end]
        for line in block.splitlines():
            s = line.strip()
            if not s or set(s) <= {"-"}:
                continue  # Leer- oder Trennzeile
            if "=" in s:
                hits.add(layer)
                break
    return hits


def summarize_restrictions(layers: Iterable[str]) -> list[str]:
    """Layer-Maschinennamen in sortierte, deutsche Klartext-Labels wandeln."""
    labels = {LAYER_LABELS.get(layer, layer) for layer in layers}
    return sorted(labels)


class DipulClient:
    """Dünner Client für DIPUL-``GetFeatureInfo``-Punktabfragen."""

    def __init__(self, session: Any, base_url: str = DEFAULT_WMS_URL) -> None:
        self._session = session
        self._base = base_url

    async def query_point(
        self, lat: float, lon: float, layers: Iterable[str] | None = None
    ) -> set[str]:
        """Welche der ``layers`` enthalten den Punkt (lat, lon)?"""
        layer_list = list(layers) if layers is not None else list(DEFAULT_RESTRICTION_LAYERS)
        layer_param = ",".join(f"dipul:{name}" for name in layer_list)
        d = 0.0005  # ~50 m halbe Box-Breite
        params = {
            "service": "WMS",
            "version": "1.3.0",
            "request": "GetFeatureInfo",
            "layers": layer_param,
            "query_layers": layer_param,
            # CRS:84 = WGS84 in Reihenfolge lon,lat -> keine Achsen-Verwirrung
            "crs": "CRS:84",
            "bbox": f"{lon - d},{lat - d},{lon + d},{lat + d}",
            "width": "101",
            "height": "101",
            "i": "50",
            "j": "50",
            "info_format": "text/plain",
            "feature_count": "50",
            "format": "image/png",
        }
        async with self._session.get(self._base, params=params, timeout=25) as resp:
            resp.raise_for_status()
            text = await resp.text()
        return parse_getfeatureinfo_text(text)
