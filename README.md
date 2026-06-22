# Drohnenspot (DE) — Home-Assistant-Integration

[![Validate](https://github.com/Xunil99/ha-drohnenspot/actions/workflows/validate.yml/badge.svg)](https://github.com/Xunil99/ha-drohnenspot/actions/workflows/validate.yml)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

Eine **Höhen-/Reliefkarte mit den offiziellen Drohnen-Flugverbotszonen** direkt
im Home-Assistant-Dashboard — plus eine Empfehlung für **hoch gelegene,
zonenfreie, gut erreichbare Spots** in der Umgebung, bevorzugt nahe an etwas
Sehenswertem. So findest du schnell einen Platz mit guter Aussicht und
Bewegungsfreiheit, ohne in eine Verbotszone zu geraten.

> ⚠️ **Orientierungshilfe, keine Rechtsgarantie.** Die Zonen stammen aus der
> offiziellen DIPUL-Quelle der DFS, aber ob ein Flug erlaubt ist, hängt
> zusätzlich von Drohnenklasse, Betriebskategorie (A1/A2/A3), max. 120 m über
> Grund (AGL), Sichtflug (VLOS), Registrierung und aktuellen NOTAM ab. Vor dem
> Start immer selbst prüfen (z. B. im
> [DIPUL-Kartentool](https://maps.dipul.de)).

> 🧪 **Beta (v0.1.0b8).** Funktioniert, ist aber noch nicht in jeder
> HA-Konstellation erprobt. Rückmeldungen willkommen!

---

## Funktionen

- 🗺️ **Lovelace-Karte** `drohnenspot-card` (registriert sich automatisch):
  Relief-Basis (Esri World Topo, frei tauschbar) mit ein-/ausschaltbaren Ebenen
  - **Flugverbotszonen (DIPUL)** — offizielles Zonen-Overlay
  - **Temporäre Sperrungen (NOTAM)** — eigener Layer; aktive temporäre
    Sperrung wird beim Tippen rot ⛔ hervorgehoben
  - **Naturschutzgebiete** — eigener Layer
  - **Sehenswertes** — Aussichtspunkte 👀, historische Orte 🏰 (nur markante
    Bauwerke), Lost Places 🏚️, Gipfel ⛰️, Aussichtstürme 🗼 (lädt on-demand,
    mit **Wikipedia-Link** im Popup; Kategorien in den Optionen filterbar)
- 👆 **Tippen auf die Karte** zeigt Zonen + Geländehöhe an der Stelle.
- 🔎 **Spot-Empfehlung** mit Filter-Stack: **legal** (DIPUL-Zonen) · **kein
  Wald** · **erreichbar** (nahe Straße/Feldweg) · optional **Mindesthöhe** ·
  sortiert nach **Prominenz** · **starker Bonus** für Nähe zu Sehenswertem.
- 📟 **Entities**: `binary_sensor` *Heimat in Verbotszone?* · `sensor` *Höhe
  Heimat* · `sensor` *Bester Spot in der Nähe* (Koordinaten als Attribute).
- ⚙️ **Services** (alle mit Service-Antwort): `drohnenspot.find_spots`,
  `drohnenspot.query_point`, `drohnenspot.get_pois`.

## Wie es funktioniert

Ansatz „Höhe zuerst, dann gezielt prüfen" — schonend für die öffentlichen Dienste:

1. Über den Suchradius wird ein Punktraster gelegt; die Höhen kommen gebündelt
   von OpenTopoData (EU-DEM).
2. Lokale Gipfel werden nach **Prominenz** bewertet (rein lokal).
3. **Eine** OpenStreetMap-(Overpass-)Abfrage holt Wald, Wege und Sehenswertes.
   Lokal wird gefiltert: Wald raus, nur erreichbare behalten, Bonus für Nähe zu
   Sehenswertem.
4. Nur die besten Kandidaten werden per DIPUL-`GetFeatureInfo` auf Verbotszonen
   geprüft.

Alles **best-effort**: Antwortet OpenStreetMap/Overpass nicht, wird der jeweilige
Filter einfach übersprungen — die Suche läuft weiter.

## Installation (HACS)

1. HACS → ⋮ → **Benutzerdefiniertes Repository**
2. URL `https://github.com/Xunil99/ha-drohnenspot`, Kategorie **Integration**
3. „Drohnenspot (DE)" installieren (Beta-Versionen ggf. in HACS aktivieren),
   Home Assistant **neu starten**.
4. *Einstellungen → Geräte & Dienste → Integration hinzufügen → „Drohnenspot"*.

Voraussetzung: Home Assistant **2024.7** oder neuer. Keine zusätzlichen
Python-Abhängigkeiten.

## Optionen

Unter *Einstellungen → Geräte & Dienste → Drohnenspot → Konfigurieren*:

| Option | Vorgabe | Bedeutung |
|--------|---------|-----------|
| Suchradius (km) | 10 | Umkreis der Spot-Suche |
| Anzahl Spots | 8 | Wie viele Spots empfohlen werden |
| Mindesthöhe (m) | 0 | Nur Spots oberhalb dieser Geländehöhe |
| Wald-Spots ausschließen | an | Spots im Wald entfernen (OSM) |
| Nur erreichbare Spots | an | Nur Spots nahe Straße/Feldweg (OSM) |
| Max. Abstand zur Straße/Weg (m) | 200 | Grenze für „erreichbar" |
| Bonus für Sehenswertes | an | Spots nahe Aussicht/Burg/Gipfel bevorzugen |
| Bonus-Radius (m) | 500 | Bis hierhin gilt ein Spot als „nahe Sehenswertem" |
| Sehenswertes-Kategorien | alle | Welche Arten gezeigt/bewertet werden (Aussichtspunkte, Historische Orte, Lost Places, Gipfel, Aussichtstürme) |

## Karte einrichten

Die Card-Ressource wird automatisch geladen. Karte hinzufügen (manuelles YAML):

```yaml
type: custom:drohnenspot-card
title: Drohnenspot
# optional:
latitude: 48.72
longitude: 12.45
zoom: 11
radius_km: 12
count: 8
height: 480
# Basiskarte tauschen (optional), Standard ist Esri World Topo:
# tile_url: https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png
# tile_subdomains: abc
# tile_attribution: © OpenTopoMap (CC-BY-SA)
```

Die Ebenen (Flugverbotszonen, Naturschutzgebiete, Sehenswertes) schaltest du
oben rechts auf der Karte ein/aus.

## Services

### `drohnenspot.find_spots`

| Feld | Vorgabe | Bedeutung |
|------|---------|-----------|
| `latitude` / `longitude` | Heimat | Mittelpunkt der Suche |
| `radius_km` | 10 | Suchradius (1–50) |
| `count` | 8 | Anzahl Spots (1–30) |
| `min_elevation` | – | Nur Spots oberhalb dieser Höhe (m) |
| `exclude_forest` | an | Wald-Spots ausschließen |
| `require_road_access` | an | Nur Spots nahe Straße/Weg |
| `max_road_distance_m` | 200 | Grenze für „erreichbar" |
| `poi_bonus` | an | Bonus für Nähe zu Sehenswertem |
| `poi_bonus_radius_m` | 500 | Bonus-Radius |

Antwort: `spots[]` mit Koordinaten, Höhe, Prominenz, Abstand, Weg-Distanz und
(falls nah) `poi` (Art, Name, Untertyp, Wikipedia-Link, Distanz).

### `drohnenspot.query_point`

`latitude` + `longitude` → `restricted`, `features[]` (Zonen) und `elevation_m`.

### `drohnenspot.get_pois`

`latitude` + `longitude` + `radius_km` → `pois[]` (Aussichtspunkte, historische
Orte, Gipfel, Türme) mit Art, Name, Untertyp und Wikipedia-Link. Wird von der
Karten-Ebene „Sehenswertes" genutzt.

## Daten & Lizenz

- **Geozonen**: © DFS / GeoBasis-DE / BKG — DIPUL-WMS, **CC BY 4.0**.
- **Höhen**: © OpenTopoData / EU-DEM (Copernicus).
- **Wald, Wege, Sehenswertes**: © OpenStreetMap-Mitwirkende (**ODbL**).
- **Basiskarte**: © Esri (World Topo Map) — frei wählbar über `tile_url`.
- **Code**: [MIT](LICENSE).

## Bekannte Grenzen (Beta)

- Die Karte lädt Leaflet von einem CDN (Internet nötig).
- „Schön/historisch" wird über OSM-Tags angenähert — gute, aber nicht
  lückenlose Abdeckung.
- Höhen über die öffentliche OpenTopoData-API; OSM über die öffentliche
  Overpass-API (Limits gelten, Endpunkte konfigurierbar/selbst hostbar).
- Ein echter **Viewshed** („wie weit sieht man") ist noch nicht enthalten.

## Roadmap

- [x] Wald-Spots ausschließen (OSM)
- [x] Erreichbarkeit (Nähe Straße/Feldweg)
- [x] Bonus für Sehenswertes + Wikipedia-Links
- [x] Sortierung nach Prominenz
- [ ] Echter Viewshed/Sichtbarkeit als Aussichts-Maß
- [ ] Optional BKG-DGM als Höhenquelle
- [ ] Konfigurierbare Zonen-Auswahl in der Card
- [ ] Leaflet bündeln (ohne CDN)

---

## English (short)

A Home Assistant integration showing an **elevation/relief map with Germany's
official drone no-fly zones** (DIPUL by DFS) and recommending **high,
restriction-free, reachable spots** nearby — preferably close to something
scenic. Filters: legal (DIPUL zones), no forest, road/track access, minimum
elevation, sorted by prominence, strong bonus for nearby points of interest
(viewpoints, historic places, peaks, towers — with Wikipedia links).

Decision-support only — **not** a legal guarantee; always re-check drone class,
A1/A2/A3, 120 m AGL, VLOS and current NOTAM before flying. Install via HACS as a
custom *integration* repository; the Lovelace card registers itself
automatically. Map layers (no-fly zones, nature reserves, points of interest)
toggle in the top-right. Data © DFS / GeoBasis-DE / BKG (CC BY 4.0),
OpenTopoData/EU-DEM and © OpenStreetMap contributors (ODbL). Code under MIT.
