# Drohnenspot (DE) — Home-Assistant-Integration

[![Validate](https://github.com/Xunil99/ha-drohnenspot/actions/workflows/validate.yml/badge.svg)](https://github.com/Xunil99/ha-drohnenspot/actions/workflows/validate.yml)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

Eine **Höhen-/Reliefkarte mit den offiziellen Drohnen-Flugverbotszonen**
direkt im Home-Assistant-Dashboard — und eine Empfehlung für **hoch gelegene,
zonenfreie Spots** in der Umgebung. So findest du schnell einen Platz mit guter
Aussicht und Bewegungsfreiheit, ohne in eine Verbotszone zu geraten.

> ⚠️ **Orientierungshilfe, keine Rechtsgarantie.** Die Zonen stammen aus der
> offiziellen DIPUL-Quelle der DFS, aber ob ein Flug erlaubt ist, hängt
> zusätzlich von Drohnenklasse, Betriebskategorie (A1/A2/A3), max. 120 m über
> Grund (AGL), Sichtflug (VLOS), Registrierung und aktuellen NOTAM ab. Vor dem
> Start immer selbst prüfen (z. B. im
> [DIPUL-Kartentool](https://maps.dipul.de)).

> 🧪 **Beta (v0.1.0b1).** Funktioniert, ist aber noch nicht in jeder
> HA-Konstellation erprobt. Rückmeldungen willkommen!

---

## Funktionen

- 🗺️ **Lovelace-Karte** `drohnenspot-card`: OpenTopoMap-Relief als Basis, das
  offizielle **DIPUL-Zonen-Overlay** darüber (ein-/ausblendbar), Heimat- und
  Spot-Marker. Wird durch die Integration **automatisch registriert** — kein
  manuelles Hinzufügen von Ressourcen nötig.
- 👆 **Tippen auf die Karte** zeigt, welche Zonen dort liegen und die
  Geländehöhe.
- 🔎 **Spot-Empfehlung**: findet hoch gelegene, zonenfreie Punkte im Umkreis.
- 📟 **Entities**:
  - `binary_sensor` — *Heimat in Verbotszone?* (mit Liste der Zonen)
  - `sensor` — *Höhe Heimat*
  - `sensor` — *Bester Spot in der Nähe* (Höhe + Koordinaten als Attribute)
- ⚙️ **Services** `drohnenspot.find_spots` und `drohnenspot.query_point`
  (beide mit Service-Antwort).

## Wie es funktioniert

Ansatz „Höhe zuerst, Zonen danach" — schonend für die öffentlichen Dienste:

1. Über den Suchradius wird ein Punktraster gelegt; die Höhen kommen gebündelt
   von OpenTopoData (EU-DEM).
2. Lokale Höhen-Gipfel werden nach Höhe und Prominenz bewertet (rein lokal,
   ohne weitere Abrufe).
3. Nur die besten Kandidaten werden per DIPUL-`GetFeatureInfo` auf Verbotszonen
   geprüft. Was in einer Zone liegt, fällt raus.

## Installation (HACS)

1. HACS → *Integrationen* → ⋮ → **Benutzerdefiniertes Repository**
2. URL `https://github.com/Xunil99/ha-drohnenspot`, Kategorie **Integration**
3. „Drohnenspot (DE)" installieren, Home Assistant **neu starten**.
4. *Einstellungen → Geräte & Dienste → Integration hinzufügen → „Drohnenspot"*.

Voraussetzung: Home Assistant **2024.7** oder neuer. Keine zusätzlichen
Python-Abhängigkeiten.

## Karte einrichten

Die Card-Ressource wird automatisch geladen. Einfach eine Karte hinzufügen
(manuelles YAML):

```yaml
type: custom:drohnenspot-card
title: Drohnenspot
# optional:
latitude: 50.30
longitude: 6.50
zoom: 11
radius_km: 12
count: 8
height: 480
```

## Services

### `drohnenspot.find_spots`

| Feld | Pflicht | Vorgabe | Bedeutung |
|------|---------|---------|-----------|
| `latitude` / `longitude` | nein | Heimat | Mittelpunkt der Suche |
| `radius_km` | nein | 10 | Suchradius (1–50) |
| `count` | nein | 8 | Anzahl Spots (1–30) |
| `min_elevation` | nein | – | Nur Spots oberhalb dieser Höhe (m) |

Liefert eine Antwort mit `spots[]` (Koordinaten, Höhe, Prominenz, Abstand).

### `drohnenspot.query_point`

`latitude` + `longitude` → Antwort mit `restricted`, `features[]` (Zonen) und
`elevation_m`.

## Daten & Lizenz

- **Geozonen**: © DFS / GeoBasis-DE / BKG — DIPUL-WMS, **CC BY 4.0**.
- **Höhen**: © OpenTopoData / EU-DEM (Copernicus).
- **Basiskarte**: © OpenTopoMap (CC-BY-SA), Kartendaten © OpenStreetMap.
- **Code**: [MIT](LICENSE).

## Bekannte Grenzen (Beta)

- Die Karte lädt Leaflet von einem CDN (Internet nötig).
- Die Empfehlung bewertet vorerst nur **Höhe + Prominenz**; „Abstand zur
  nächsten Zone" und ein echter **Viewshed** („schöne Aussicht") sind für v2
  geplant.
- Höhendaten über die öffentliche OpenTopoData-API (Limits gelten; Endpoint ist
  konfigurierbar/selbst hostbar).

## Roadmap

- [ ] Score um „Abstand zur nächsten Zone" (Bewegungsspielraum) erweitern
- [ ] Viewshed/Sichtbarkeit als Aussichts-Maß
- [ ] Optional BKG-DGM als Höhenquelle
- [ ] Konfigurierbare Zonen-Auswahl in der Card

---

## English (short)

A Home Assistant integration that shows an **elevation/relief map with the
official German drone no-fly zones** (DIPUL by DFS) and recommends **high,
restriction-free spots** nearby. Decision-support only — **not** a legal
guarantee; always re-check drone class, A1/A2/A3, 120 m AGL, VLOS and current
NOTAM before flying. Install via HACS as a custom *integration* repository; the
Lovelace card registers itself automatically. Data © DFS / GeoBasis-DE / BKG
(CC BY 4.0) and OpenTopoData/EU-DEM. Code under MIT.
