/*!
 * drohnenspot-card — Lovelace-Karte für ha-drohnenspot
 * Höhen-/Relief-Karte (OpenTopoMap) mit offiziellen Drohnen-Flugverbotszonen
 * (DIPUL-WMS, © DFS / GeoBasis-DE / BKG, CC BY 4.0) und Spot-Empfehlung.
 *
 * Orientierungshilfe, keine Rechtsgarantie.
 */
const CARD_VERSION = "0.1.0b7";
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
  "nationalparks",
  "vogelschutzgebiete",
  "ffh-gebiete",
  "wohngrundstuecke",
]
  .map((n) => "dipul:" + n)
  .join(",");

// Naturschutzgebiete als eigener, separat schaltbarer Layer.
const NATURE_LAYERS = "dipul:naturschutzgebiete";

// Sehenswertes-POIs.
const POI_EMOJI = { viewpoint: "👀", historic: "🏰", peak: "⛰️", tower: "🗼" };
const POI_LABEL = {
  viewpoint: "Aussichtspunkt",
  historic: "Historischer Ort",
  peak: "Gipfel",
  tower: "Aussichtsturm",
};

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

  disconnectedCallback() {
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }
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
      <link rel="stylesheet" href="${LEAFLET_CSS}" />
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
            Höhen © OpenTopoData/EU-DEM · Karte © Esri ·
            v${CARD_VERSION}
          </div>
        </div>
      </ha-card>
      <style>
        .ds-wrap { padding: 0 0 8px; }
        .ds-map { width: 100%; border-radius: 0; z-index: 0; overflow: hidden; position: relative; background: #eaeaea; }
        /* Kritische Leaflet-Layout-Regeln, scoped — wirken sofort, auch wenn
           die externe leaflet.css verzögert/blockiert ist (Shadow-DOM-Scope). */
        .ds-map .leaflet-pane,
        .ds-map .leaflet-tile,
        .ds-map .leaflet-marker-icon,
        .ds-map .leaflet-marker-shadow,
        .ds-map .leaflet-tile-container,
        .ds-map .leaflet-image-layer,
        .ds-map .leaflet-layer { position: absolute; left: 0; top: 0; }
        .ds-map .leaflet-control-container .leaflet-top,
        .ds-map .leaflet-control-container .leaflet-bottom { position: absolute; z-index: 1000; }
        .ds-map .leaflet-top { top: 0; }
        .ds-map .leaflet-bottom { bottom: 0; }
        .ds-map .leaflet-left { left: 0; }
        .ds-map .leaflet-right { right: 0; }
        .ds-pin { background: transparent; border: none; }
        .ds-pin span { display:flex; align-items:center; justify-content:center; width:28px; height:28px; border-radius:50%; background: var(--primary-color,#03a9f4); color:#fff; font-weight:700; font-size:13px; box-shadow:0 0 0 2px #fff,0 1px 4px rgba(0,0,0,.4); }
        .ds-pin-home span { background:#2e7d32; }
        .ds-pin-best span { background:#f9a825; }
        .ds-pin-poi span { background:#fff; color:#000; font-size:15px; box-shadow:0 0 0 2px #555,0 1px 4px rgba(0,0,0,.4); }
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

    // Basiskarte: standardmäßig Esri World Topo (zuverlässig unter Last,
    // Relief-/Topo-Look). Über tile_url/tile_attribution frei austauschbar.
    const tileUrl =
      this._config.tile_url ||
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}";
    const tileAttr =
      this._config.tile_attribution || "Tiles © Esri — Esri, USGS, NOAA";
    const baseOpts = {
      maxZoom: this._config.max_zoom || 18,
      attribution: tileAttr,
    };
    if (this._config.tile_subdomains) baseOpts.subdomains = this._config.tile_subdomains;
    L.tileLayer(tileUrl, baseOpts).addTo(this._map);

    const wmsOpts = (layers) => ({
      layers,
      format: "image/png",
      transparent: true,
      version: "1.3.0",
      opacity: 0.5,
      attribution: "Geozonen © DFS / BKG",
    });

    this._dipulLayer = L.tileLayer.wms(DIPUL_WMS, wmsOpts(OVERLAY_LAYERS)).addTo(this._map);
    this._natureLayer = L.tileLayer.wms(DIPUL_WMS, wmsOpts(NATURE_LAYERS)).addTo(this._map);
    // Sehenswertes: leere Ebene, lädt POIs erst beim Einschalten (on-demand).
    this._poiLayer = L.layerGroup();

    L.control
      .layers(
        null,
        {
          "Flugverbotszonen (DIPUL)": this._dipulLayer,
          Naturschutzgebiete: this._natureLayer,
          Sehenswertes: this._poiLayer,
        },
        { collapsed: false }
      )
      .addTo(this._map);

    this._map.on("overlayadd", (e) => {
      if (e.layer === this._poiLayer) this._loadPois();
    });
    this._map.on("overlayremove", (e) => {
      if (e.layer === this._poiLayer) this._poiLayer.clearLayers();
    });

    this._homeMarker = L.marker([lat, lon], { icon: this._pin("🏠", "ds-pin-home") })
      .addTo(this._map)
      .bindPopup("Heimat");
    this._spotLayer = L.layerGroup().addTo(this._map);
    this._bestLayer = L.layerGroup().addTo(this._map);

    this._map.on("click", (e) => this._onMapClick(e));

    // Robuste Größenkorrektur: Leaflet kennt die Container-Größe im
    // HA-Dashboard (Masonry/Panel/versteckte Tabs) anfangs oft nicht ->
    // verstreute Kacheln mit Lücken und falsch platzierte Marker.
    // ResizeObserver + mehrere verzögerte invalidateSize-Aufrufe beheben das.
    const fixSize = () => {
      if (this._map) this._map.invalidateSize(false);
    };
    if (window.ResizeObserver) {
      this._resizeObserver = new ResizeObserver(() => fixSize());
      this._resizeObserver.observe(this._mapEl);
    }
    requestAnimationFrame(fixSize);
    [50, 150, 300, 600, 1000, 2000].forEach((ms) => setTimeout(fixSize, ms));
  }

  _pin(html, cls) {
    return this._L.divIcon({
      className: "ds-pin " + cls,
      html: `<span>${html}</span>`,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
      popupAnchor: [0, -14],
    });
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
      const marker = L.marker([s.latitude, s.longitude], {
        title: `Spot ${idx + 1}`,
        icon: this._pin(String(idx + 1), "ds-pin-spot"),
      });
      const weg = s.road_distance_m != null ? `Weg: ${s.road_distance_m} m<br>` : "";
      const poiTxt = s.poi
        ? `Nahe: ${POI_EMOJI[s.poi.kind] || "📍"} ${s.poi.name || POI_LABEL[s.poi.kind] || "Sehenswertes"} (${s.poi.distance_m} m)<br>`
        : "";
      marker.bindPopup(
        `<b>Spot ${idx + 1}</b><br>Höhe: ${s.elevation_m} m<br>` +
          `Prominenz: ${s.prominence_m} m<br>Abstand: ${s.distance_km} km<br>` +
          weg +
          poiTxt +
          `<a href="${dipul}" target="_blank" rel="noopener">DIPUL-Check ↗</a>`
      );
      marker.addTo(this._spotLayer);
      latlngs.push([s.latitude, s.longitude]);
    });
    if (latlngs.length > 1) {
      this._map.fitBounds(latlngs, { padding: [40, 40], maxZoom: 13 });
    }
  }

  async _loadPois() {
    if (!this._map) return;
    const center = this._map.getCenter();
    const ne = this._map.getBounds().getNorthEast();
    const radiusKm = Math.min(50, Math.max(0.5, center.distanceTo(ne) / 1000));
    this._setStatus("Lade Sehenswertes …");
    try {
      const res = await this._callService("get_pois", {
        latitude: center.lat,
        longitude: center.lng,
        radius_km: radiusKm,
      });
      const r = (res && res.response) || res || {};
      this._renderPois(r.pois || []);
      this._setStatus(`${(r.pois || []).length} Sehenswertes geladen`);
    } catch (err) {
      this._setStatus("Sehenswertes: " + (err.message || err));
    }
  }

  _renderPois(pois) {
    if (!this._poiLayer) return;
    const L = this._L;
    this._poiLayer.clearLayers();
    pois.forEach((p) => {
      const emoji = POI_EMOJI[p.kind] || "📍";
      const label = POI_LABEL[p.kind] || "Sehenswertes";
      L.marker([p.latitude, p.longitude], {
        icon: this._pin(emoji, "ds-pin-poi"),
        title: p.name || label,
      })
        .bindPopup(`<b>${emoji} ${label}</b>${p.name ? "<br>" + p.name : ""}`)
        .addTo(this._poiLayer);
    });
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
      L.marker([a.latitude, a.longitude], { icon: this._pin("⭐", "ds-pin-best") })
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
