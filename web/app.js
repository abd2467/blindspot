// Blindspot web app. Reads only the files in web/data/ (written by src/blindspot/s5_package).
// No build step: open with any static server, e.g.  python -m http.server -d web 8000
"use strict";

const COLORS = { recorded: "#f28c28", none: "#9b5de5", insufficient_data: "#6c757d", unknown: "#adb5bd" };
const GIBS_WMS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi";

const state = { manifest: null, patches: null, hotspots: null, ts: null, stats: null, idx: 0,
                layers: {}, charts: {} };

async function getJSON(path, optional = true) {
  try {
    const r = await fetch(path, { cache: "no-cache" });
    if (!r.ok) throw new Error(r.status);
    return await r.json();
  } catch (e) {
    if (!optional) throw e;
    console.warn("missing", path);
    return null;
  }
}

const fmtPct = (v) => (v == null || isNaN(v) ? "–" : `${Math.round(v * 100)}%`);

async function init() {
  const [manifest, patches, hotspots, ts, stats, events] = await Promise.all([
    getJSON("data/manifest.json", false), getJSON("data/patches.geojson"), getJSON("data/hotspots.geojson"),
    getJSON("data/timeseries.json"), getJSON("data/stats.json"), getJSON("data/events.geojson"),
  ]);
  Object.assign(state, { manifest, patches, hotspots, ts, stats });
  document.getElementById("demo-banner").hidden = !manifest.fixture;

  const [w, s, e, n] = manifest.study_bbox;
  const bounds = manifest.bounds || [[s, w], [n, e]];
  const map = L.map("map", { zoomControl: true }).fitBounds(bounds);
  state.map = map;
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 16, attribution: "© OpenStreetMap contributors · NISAR, FIRMS, EONET: NASA",
  }).addTo(map);

  state.layers.radar = L.imageOverlay("", bounds, { opacity: 0.85 }).addTo(map);
  state.layers.patches = L.geoJSON(null, { style: patchStyle, onEachFeature: bindPatch }).addTo(map);
  state.layers.hotspots = L.layerGroup().addTo(map);
  if (events) {
    L.geoJSON(events, {
      pointToLayer: (f, ll) => L.marker(ll, { title: f.properties.title }),
      onEachFeature: (f, l) => l.bindPopup(`<b>${f.properties.title}</b><br>${f.properties.date} (NASA EONET)`),
    }).addTo(map);
  }

  setupTimeline();
  renderHeadline();
  renderByDate();
  renderValidation();
  setupPanels();
  update();
}

function patchStyle(f) {
  const c = COLORS[f.properties.hotspot_status] || COLORS.unknown;
  return { color: c, weight: 1.5, fillColor: c, fillOpacity: 0.45 };
}

function bindPatch(f, layer) {
  layer.on("click", () => showPatch(f.properties));
  layer.bindTooltip(`${f.properties.patch_id} · ${f.properties.area_ha} ha · ${f.properties.first_change_date}`);
}

function setupTimeline() {
  const dates = state.manifest.dates || [];
  const slider = document.getElementById("date-slider");
  slider.max = Math.max(dates.length - 1, 0);
  slider.value = slider.max;
  state.idx = +slider.value;
  slider.addEventListener("input", () => { state.idx = +slider.value; update(); });
  document.getElementById("date-ticks").innerHTML = dates.map((d) => `<span>${d.slice(5)}</span>`).join("");
  document.getElementById("show-radar").addEventListener("change", update);
  document.getElementById("compare").addEventListener("change", update);
}

function update() {
  const dates = state.manifest.dates || [];
  const d = dates[state.idx];
  document.getElementById("date-label").textContent = d || "";
  const compare = document.getElementById("compare").checked;
  const showRadar = document.getElementById("show-radar").checked;
  const ov = state.manifest.overlays || {};
  const shown = compare ? dates[0] : d;
  if (showRadar && ov[shown]) {
    state.layers.radar.setUrl("data/" + ov[shown]);
    state.layers.radar.setOpacity(0.85);
  } else {
    state.layers.radar.setOpacity(0);
  }

  // patches that have changed by the selected date
  state.layers.patches.clearLayers();
  if (state.patches) {
    state.layers.patches.addData({
      type: "FeatureCollection",
      features: state.patches.features.filter((f) => f.properties.first_change_date <= d),
    });
  }
  // hotspots inside the 12-day window ending at the selected date
  state.layers.hotspots.clearLayers();
  if (state.hotspots && d) {
    const prev = state.idx > 0 ? dates[state.idx - 1] : "0000";
    state.hotspots.features
      .filter((f) => f.properties.acq_date > prev && f.properties.acq_date <= d)
      .forEach((f) => {
        const [lon, lat] = f.geometry.coordinates;
        L.circleMarker([lat, lon], { radius: 3.5, color: "#000", weight: 0.5, fillColor: "#ffd166", fillOpacity: 1 })
          .bindTooltip(`${f.properties.sensor} ${f.properties.acq_date} · FRP ${f.properties.frp}`)
          .addTo(state.layers.hotspots);
      });
  }
}

function renderHeadline() {
  const c = state.stats && state.stats.crosscheck;
  if (!c) return;
  document.getElementById("h-share").textContent = fmtPct(c.no_hotspot_share);
  document.getElementById("h-range").textContent =
    `Range ${fmtPct(c.mc.p05)} to ${fmtPct(c.mc.p95)} (Monte Carlo, ${c.mc.runs} runs over hotspot position, buffer and time window)`;
  let area = `${c.total_change_km2.toFixed(1)} km² of change in ${c.n_patches} patches; ${c.no_hotspot_km2.toFixed(1)} km² with no hotspot.`;
  const v = state.stats.validation && state.stats.validation.area_estimate;
  if (v) area += ` Error-adjusted disturbed area: ${v.km2} km² (95% CI ${v.ci95_low} to ${v.ci95_high}).`;
  document.getElementById("h-area").textContent = area;
}

function renderByDate() {
  const c = state.stats && state.stats.crosscheck;
  if (!c) return;
  const labels = c.by_date.map((r) => r.date.slice(5));
  state.charts.bydate = new Chart(document.getElementById("bydate-chart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "change, hotspot recorded (km²)", data: c.by_date.map((r) => r.change_km2 - r.no_hotspot_km2), backgroundColor: COLORS.recorded, stack: "a" },
        { label: "change, no hotspot (km²)", data: c.by_date.map((r) => r.no_hotspot_km2), backgroundColor: COLORS.none, stack: "a" },
      ],
    },
    options: { plugins: { legend: { labels: { color: "#9aa3ad", boxWidth: 10 } } },
      scales: { x: { ticks: { color: "#9aa3ad" } }, y: { ticks: { color: "#9aa3ad" } } } },
  });
}

function showPatch(p) {
  document.getElementById("explore-hint").hidden = true;
  document.getElementById("patch-card").hidden = false;
  document.getElementById("p-title").textContent = `Patch ${p.patch_id} · ${p.area_ha} ha`;
  document.getElementById("p-badges").innerHTML =
    `<span class="badge ${p.hotspot_status}">${p.hotspot_status.replace("_", " ")}</span>` +
    `<span class="badge">confidence: ${p.confidence_tier}</span>` +
    `<span class="badge">interpretation: ${p.interpretation.replace("_", " ")}</span>` +
    (p.flags || []).map((f) => `<span class="badge">flag: ${f}</span>`).join("");
  document.getElementById("p-facts").innerHTML = `
    <dt>First change</dt><dd>${p.first_change_date} (previous radar date ${p.prev_acq_date})</dd>
    <dt>HV drop</dt><dd>${p.mean_drop_hv_db} dB · HH change ${p.hh_change_db} dB</dd>
    <dt>Hotspots in window</dt><dd>${p.n_hotspots}${p.nearest_hotspot_km != null ? ` · nearest ${p.nearest_hotspot_km} km` : ""}</dd>
    ${p.notes ? `<dt>Review notes</dt><dd>${p.notes}</dd>` : ""}`;
  const s = state.ts && state.ts.patches[p.patch_id];
  if (!s) return;
  if (state.charts.patch) state.charts.patch.destroy();
  state.charts.patch = new Chart(document.getElementById("p-chart"), {
    type: "line",
    data: {
      labels: state.ts.dates.map((d) => d.slice(5)),
      datasets: [
        { label: "HV patch (dB)", data: s.hv_db, borderColor: COLORS.none, tension: 0.2 },
        { label: "HV stable forest (dB)", data: state.ts.reference.hv_db, borderColor: "#6c757d", borderDash: [4, 3] },
        { label: "HH patch (dB)", data: s.hh_db, borderColor: "#4dabf7", tension: 0.2, hidden: true },
      ],
    },
    options: { plugins: { legend: { labels: { color: "#9aa3ad", boxWidth: 10 } } },
      scales: { x: { ticks: { color: "#9aa3ad" } }, y: { ticks: { color: "#9aa3ad" } } } },
  });
}

function renderValidation() {
  const v = state.stats && state.stats.validation;
  const el = document.getElementById("validation");
  if (!v) return;
  const parts = [];
  if (v.radd_agreement) parts.push(`RADD alerts agree on ${fmtPct(v.radd_agreement.share)} of ${v.radd_agreement.n_patches} patches.`);
  if (v.sample) parts.push(`${v.sample.n_labelled} of ${v.sample.n} reference points labelled.`);
  if (v.synthetic) {
    const at3 = v.synthetic.curve.filter((r) => r.drop_db === 3 && r.detection_rate >= 0.8).map((r) => r.size_ha);
    parts.push(`Synthetic burn test: 3 dB burns detected reliably from ${at3.length ? Math.min(...at3) + " ha" : "–"}; false-alarm rate ${(v.synthetic.false_alarm_rate * 100).toFixed(2)}%.`);
  }
  el.innerHTML = `<h3>Validation</h3><p>${parts.join(" ")}</p>`;
}

async function loadPanelCharts(name) {
  if (name === "singapore" && !state.charts.psi) {
    const [psi, rain] = await Promise.all([getJSON("data/psi.json"), getJSON("data/rain.json")]);
    if (psi) state.charts.psi = lineChart("psi-chart", psi, "PSI 24-hr (max)", "#ff6b6b", 100);
    if (rain) state.charts.rain = lineChart("rain-chart", rain, "Rain (mm/day)", "#4dabf7");
  }
  if (name === "why") updateGibs();
}

function lineChart(id, rows, label, color, guide) {
  const datasets = [{ label, data: rows.map((r) => r.value), borderColor: color, pointRadius: 0, tension: 0.2 }];
  if (guide) datasets.push({ label: "Unhealthy (100)", data: rows.map(() => guide), borderColor: "#888", borderDash: [4, 4], pointRadius: 0 });
  return new Chart(document.getElementById(id), {
    type: "line", data: { labels: rows.map((r) => r.date.slice(5)), datasets },
    options: { plugins: { legend: { labels: { color: "#9aa3ad", boxWidth: 10 } } },
      scales: { x: { ticks: { color: "#9aa3ad", maxTicksLimit: 8 } }, y: { ticks: { color: "#9aa3ad" } } } },
  });
}

function updateGibs() {
  const day = document.getElementById("gibs-date").value;
  const [w, s, e, n] = state.manifest.study_bbox;
  const pad = 0.3;
  const q = new URLSearchParams({ SERVICE: "WMS", REQUEST: "GetMap", VERSION: "1.3.0",
    LAYERS: "VIIRS_SNPP_CorrectedReflectance_TrueColor", CRS: "EPSG:4326",
    BBOX: [s - pad, w - pad, n + pad, e + pad].join(","), WIDTH: 512, HEIGHT: 512, FORMAT: "image/jpeg", TIME: day });
  document.getElementById("gibs-img").src = `${GIBS_WMS}?${q}`;
}

function setupPanels() {
  document.querySelectorAll("nav button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach((x) => x.classList.toggle("active", x === b));
    document.querySelectorAll(".panel").forEach((p) => (p.hidden = p.id !== `panel-${b.dataset.panel}`));
    loadPanelCharts(b.dataset.panel);
  }));
  document.getElementById("gibs-date").addEventListener("change", updateGibs);
}

init().catch((e) => {
  document.body.insertAdjacentHTML("afterbegin", `<p style="padding:1em;color:#f66">Could not load web/data/manifest.json: ${e}. Run the pipeline (see README).</p>`);
});
