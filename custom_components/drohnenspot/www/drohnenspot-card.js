/*!
 * drohnenspot-card — Lovelace-Karte für ha-drohnenspot
 * Höhen-/Relief-Karte (OpenTopoMap) mit offiziellen Drohnen-Flugverbotszonen
 * (DIPUL-WMS, © DFS / GeoBasis-DE / BKG, CC BY 4.0) und Spot-Empfehlung.
 *
 * Orientierungshilfe, keine Rechtsgarantie.
 */
const CARD_VERSION = "0.1.0b1";
const DIPUL_WMS = "https://uas-betrieb.de/geoservices/dipul/wms";
const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";

// Im Overlay sichtbare Zonen-Layer (visuell wichtigste Auswahl).
const OVERLAY_LAYERS = [
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
]
  .map((n) => "dipul:" + n)
  .join(",");

let _leafletPromise = null;
function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  if (_leafletPromise) return _leafletPromise;
  _leafletPromise = new Promise((resolve, reject) => {
    if (!document.querySelector("link[data-drohnenspot-leaflet]")) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = LEAFLET_CSS;
      link.setAttribute("data-drohnenspot-leaflet", "");
      document.head.appendChild(link);
    }
    const script = document.createElement("script");
    script.src = LEAFLET_JS;
    script.onload = () => resolve(window.L);
    script.onerror = () =>
      reject(new Error("Leaflet konnte nicht geladen werden (Internet nötig)."));
    document.head.appendChild(script);
  });
  return _leafletPromise;
}

class DrohnenspotCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initStarted) {
      this._initStarted = true;
      this._init();
    } else {
      this._refreshFromEntities();
    }
  }

  getCardSize() {
    return 9;
  }

  async _init() {
    this._renderShell();
    try {
      this._L = await loadLeaflet();
    } catch (err) {
      this._setStatus(err.message || String(err));
      return;
    }
    this._setupMap();
    this._refreshFromEntities();
  }

  _renderShell() {
    const title = this._config.title || "Drohnenspot";
    const height = this._config.height || 480;
    this.innerHTML = `
      <ha-card header="${title}">
        <div class="ds-wrap">
          <div class="ds-map" style="height:${height}px"></div>
          <div class="ds-bar">
            <button class="ds-btn">Spots in Kartenmitte suchen</button>
            <span class="ds-status">Tippe auf die Karte für Zonen-Info.</span>
          </div>
          <div class="ds-disclaimer">
            ⚠️ Orientierungshilfe, keine Rechtsgarantie. Vor dem Start
            Drohnenklasse, A1/A2/A3, 120&nbsp;m&nbsp;AGL, Sichtflug (VLOS) und
            aktuelle NOTAM prüfen.
          </div>
          <div class="ds-attr">
            Geozonen © DFS / GeoBasis-DE / BKG (CC&nbsp;BY&nbsp;4.0) ·
            Höhen © OpenTopoData/EU-DEM · Karte © OpenTopoMap (CC-BY-SA) ·
            v${CARD_VERSION}
          </div>
        </div>
      </ha-card>
      <style>
        .ds-wrap { padding: 0 0 8px; }
        .ds-map { width: 100%; border-radius: 0; z-index: 0; }
        .ds-bar { display:flex; align-items:center; gap:12px; padding:10px 16px 4px; flex-wrap:wrap; }
        .ds-btn {
          background: var(--primary-color, #03a9f4); color: var(--text-primary-color,#fff);
          border: none; border-radius: 8px; padding: 8px 14px; cursor: pointer; font-size: 0.95em;
        }
        .ds-btn:disabled { opacity: 0.6; cursor: default; }
        .ds-status { color: var(--secondary-text-color); font-size: 0.9em; }
        .ds-disclaimer { padding: 4px 16px; color: var(--secondary-text-color); font-size: 0.8em; }
        .ds-attr { padding: 2px 16px; color: var(--disabled-text-color, #9e9e9e); font-size: 0.7em; }
      </style>
    `;
    this._mapEl = this.querySelector(".ds-map");
    this._statusEl = this.querySelector(".ds-status");
    this._btn = this.querySelector(".ds-btn");
    this._btn.addEventListener("click", () => this._searchSpots());
  }

  _setupMap() {
    const L = this._L;
    const lat = this._config.latitude ?? this._hass.config.latitude;
    const lon = this._config.longitude ?? this._hass.config.longitude;
    const zoom = this._config.zoom ?? 11;

    this._map = L.map(this._mapEl).setView([lat, lon], zoom);

    L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {
      maxZoom: 17,
      attribution: "© OpenTopoMap (CC-BY-SA) · © OpenStreetMap",
    }).addTo(this._map);

    this._dipulLayer = L.tileLayer
      .wms(DIPUL_WMS, {
        layers: OVERLAY_LAYERS,
        format: "image/png",
        transparent: true,
        version: "1.3.0",
        opacity: 0.5,
        attribution: "Geozonen © DFS / BKG",
      })
      .addTo(this._map);

    L.control
      .layers(null, { "Flugverbotszonen (DIPUL)": this._dipulLayer }, { collapsed: false })
      .addTo(this._map);

    this._homeMarker = L.marker([lat, lon]).addTo(this._map).bindPopup("Heimat");
    this._spotLayer = L.layerGroup().addTo(this._map);
    this._bestLayer = L.layerGroup().addTo(this._map);

    this._map.on("click", (e) => this._onMapClick(e));

    // Layout nach erstem Rendern korrigieren (Karte in versteckten Tabs).
    setTimeout(() => this._map && this._map.invalidateSize(), 200);
  }

  async _callService(service, data) {
    // callService(domain, service, data, target, notifyOnError, returnResponse)
    return await this._hass.callService("drohnenspot", service, data, undefined, false, true);
  }

  async _onMapClick(e) {
    const L = this._L;
    const { lat, lng } = e.latlng;
    const popup = L.popup().setLatLng(e.latlng).setContent("Prüfe …").openOn(this._map);
    try {
      const res = await this._callService("query_point", { latitude: lat, longitude: lng });
      const r = (res && res.response) || res || {};
      const feats = r.features || [];
      let html = `<b>${r.restricted ? "🚫 eingeschränkt" : "✅ frei (laut Zonen)"}</b>`;
      if (r.elevation_m != null) html += `<br>Höhe: ${r.elevation_m} m`;
      html += feats.length ? `<br>${feats.join("<br>")}` : "<br>keine Zonen hier";
      popup.setContent(html);
    } catch (err) {
      popup.setContent("Fehler: " + (err.message || err));
    }
  }

  async _searchSpots() {
    this._btn.disabled = true;
    this._btn.textContent = "Suche läuft …";
    this._setStatus("");
    try {
      const center = this._map.getCenter();
      const res = await this._callService("find_spots", {
        latitude: center.lat,
        longitude: center.lng,
        radius_km: this._config.radius_km ?? 10,
        count: this._config.count ?? 8,
        ...(this._config.min_elevation != null
          ? { min_elevation: this._config.min_elevation }
          : {}),
      });
      const r = (res && res.response) || res || {};
      const spots = r.spots || [];
      this._renderSpots(spots);
      this._setStatus(
        `${spots.length} Spot(s) · ${r.zones_checked || 0} Kandidaten geprüft`
      );
    } catch (err) {
      this._setStatus("Fehler: " + (err.message || err));
    } finally {
      this._btn.disabled = false;
      this._btn.textContent = "Spots in Kartenmitte suchen";
    }
  }

  _renderSpots(spots) {
    const L = this._L;
    this._spotLayer.clearLayers();
    const latlngs = [];
    spots.forEach((s, idx) => {
      const dipul = `https://maps.dipul.de/?lat=${s.latitude}&lng=${s.longitude}`;
      const marker = L.marker([s.latitude, s.longitude], { title: `Spot ${idx + 1}` });
      marker.bindPopup(
        `<b>Spot ${idx + 1}</b><br>Höhe: ${s.elevation_m} m<br>` +
          `Prominenz: ${s.prominence_m} m<br>Abstand: ${s.distance_km} km<br>` +
          `<a href="${dipul}" target="_blank" rel="noopener">DIPUL-Check ↗</a>`
      );
      marker.addTo(this._spotLayer);
      latlngs.push([s.latitude, s.longitude]);
    });
    if (latlngs.length > 1) {
      this._map.fitBounds(latlngs, { padding: [40, 40], maxZoom: 13 });
    }
  }

  _refreshFromEntities() {
    if (!this._map || !this._hass) return;
    const cfg = this._config;

    const rEnt =
      cfg.restricted_entity || "binary_sensor.drohnenspot_heimat_in_verbotszone";
    const rState = this._hass.states[rEnt];
    if (rState && this._homeMarker) {
      const on = rState.state === "on";
      this._homeMarker.setPopupContent(
        `Heimat — ${on ? "🚫 in Verbotszone" : "✅ frei (laut Zonen)"}`
      );
    }

    const sEnt =
      cfg.best_spot_entity || "sensor.drohnenspot_bester_spot_in_der_nahe";
    const sState = this._hass.states[sEnt];
    this._bestLayer.clearLayers();
    if (sState && sState.attributes && sState.attributes.latitude != null) {
      const a = sState.attributes;
      const L = this._L;
      L.marker([a.latitude, a.longitude], { opacity: 0.95 })
        .bindPopup(
          `<b>⭐ Bester Spot</b><br>Höhe: ${sState.state} m<br>` +
            `Abstand: ${a.distance_km ?? "?"} km`
        )
        .addTo(this._bestLayer);
    }
  }

  _setStatus(text) {
    if (this._statusEl) this._statusEl.textContent = text;
  }
}

customElements.define("drohnenspot-card", DrohnenspotCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "drohnenspot-card",
  name: "Drohnenspot Karte",
  description: "Höhenkarte mit Drohnen-Flugverbotszonen (DIPUL) und Spot-Suche",
  preview: false,
});

console.info(`%c drohnenspot-card %c v${CARD_VERSION} `, "background:#03a9f4;color:#fff", "");
