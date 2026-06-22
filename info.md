# Drohnenspot (DE)

Höhen-/Reliefkarte mit den **offiziellen Drohnen-Flugverbotszonen** (DIPUL der
DFS) direkt im Home-Assistant-Dashboard — plus eine Empfehlung für hoch
gelegene, zonenfreie Spots im Umkreis.

- 🗺️ Lovelace-Karte (OpenTopoMap-Relief + DIPUL-Zonen-Overlay), wird
  automatisch registriert.
- 🛰️ Sensoren: „Heimat in Verbotszone?", Geländehöhe, bester Spot in der Nähe.
- 🔎 Service `drohnenspot.find_spots` und `drohnenspot.query_point`.

⚠️ **Orientierungshilfe, keine Rechtsgarantie.** Vor jedem Start zusätzlich
Drohnenklasse, A1/A2/A3, 120 m AGL, Sichtflug (VLOS) und aktuelle NOTAM prüfen.

Daten: Geozonen © DFS / GeoBasis-DE / BKG (CC BY 4.0) · Höhen © OpenTopoData/EU-DEM.
