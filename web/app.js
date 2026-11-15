/* BlindSpot web app (WS5). Plain JS + Leaflet + Chart.js, no build step.
   Reads only the files in web/data/ described in docs/CONTRACTS.md. */
(function () {
  'use strict';

  var DATA = 'data/';
  var PAGES = ['explore', 'why', 'singapore', 'method'];
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var STATUS = {
    recorded: { label: 'Hotspot recorded', cls: 'sw-rec', color: 'recorded' },
    none: { label: 'No hotspot recorded', cls: 'sw-none', color: 'unrecorded' },
    insufficient_data: { label: 'Insufficient fire data', cls: 'sw-insuf', color: 'ink-faint' },
    unknown: { label: 'Not checked against hotspots yet', cls: 'sw-insuf', color: 'ink-faint' }
  };
  var INTERP = { fire_supported: 'Fire supported', other_disturbance: 'Other disturbance', unresolved: 'Unresolved', not_assessable: 'Not assessable', unreviewed: 'Not yet reviewed' };

  var D = {};                       // loaded data
  var S = { sel: 0, view: 'after', patch: null, page: 'explore', playing: null };
  var map, overlay, patchLayer, hotLayer, eventLayer, peatLayer, charts = {}, intro;
  var BLANK = 'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==';

  /* ---------- helpers ---------- */
  function $(id) { return document.getElementById(id); }
  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue('--' + name).trim(); }
  function alpha(hex, a) {
    var h = hex.replace('#', ''); if (h.length === 3) h = h.replace(/./g, '$&$&');
    var n = parseInt(h, 16); return 'rgba(' + (n >> 16 & 255) + ',' + (n >> 8 & 255) + ',' + (n & 255) + ',' + a + ')';
  }
  function lab(iso) { return +iso.slice(8, 10) + ' ' + MONTHS[+iso.slice(5, 7) - 1]; }
  function labY(iso) { return lab(iso) + ' ' + iso.slice(0, 4); }
  function days(a, b) { return (Date.parse(b) - Date.parse(a)) / 864e5; }
  function pct(x) { return Math.round(x * 100) + '%'; }
  function num(x, d) { return (x < 0 ? '−' : '') + Math.abs(x).toFixed(d); }
  function ovr(date) { var o = D.manifest.overlays[date]; return o ? DATA + o : ''; }
  function fetchJSON(name) {
    return fetch(DATA + name, { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } return null; }
  function esc(t) { return String(t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function reduced() { return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches; }

  /* ---------- theme ---------- */
  function setTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    store('bs-theme', t);
    var tb = document.querySelector('.theme-toggle');
    if (tb) {
      var lbl = t === 'dark' ? 'Dark mode. Switch to light mode' : 'Light mode. Switch to dark mode';
      tb.setAttribute('aria-label', lbl); tb.title = lbl;
    }
    if (D.manifest) { styleLayers(); drawCharts(); }
  }

  /* ---------- pages and intro ---------- */
  function showPage(p) {
    if (PAGES.indexOf(p) < 0) p = 'explore';
    S.page = p;
    document.querySelectorAll('.page').forEach(function (el) { el.hidden = el.getAttribute('data-page') !== p; });
    document.querySelectorAll('.hdr-nav a').forEach(function (a) {
      if (a.getAttribute('data-page') === p) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    $('app').scrollTop = 0;
    $('to-top').classList.remove('on');
    if (p === 'explore') setTimeout(refreshMap, 0);
    if (p === 'why') drawWhyChart();
    if (p === 'singapore') drawPsiChart();
  }
  function enterApp(instant) {
    var app = $('app');
    app.hidden = false;
    if (!location.hash) history.replaceState(null, '', '#explore');
    showPage((location.hash || '#explore').slice(1));
    requestAnimationFrame(function () { app.classList.add('shown'); refreshMap(); });
    if (instant) { $('intro').setAttribute('data-phase', 'gone'); if (intro) intro.stop(); }
  }
  function leaveApp() {
    stopPlay();
    var app = $('app');
    app.classList.remove('shown');
    setTimeout(function () { app.hidden = true; }, 450);
    history.replaceState(null, '', location.pathname + location.search);
    $('intro').setAttribute('data-phase', 'hero');
    if (intro) intro.reset();
  }

  var fitted = false, userMoved = false;
  function refreshMap() {
    if (!map || $('app').hidden || S.page !== 'explore') return;
    map.invalidateSize();
    if (!fitted && $('map').clientWidth > 0) { fitted = true; fitMap(); }
  }
  function fitMap() {
    var b = D.manifest.bounds;
    map.fitBounds(b, { padding: [24, 24], animate: false });
    map.setMinZoom(map.getZoom() - 1);
  }

  /* ---------- explore: headline ---------- */
  function renderHeadline() {
    var c = (D.stats && D.stats.crosscheck) || null, v = (D.stats && D.stats.validation) || null;
    if (!c) {
      var fs = (D.patches && D.patches.features) || [];
      document.querySelector('.headline').innerHTML = fs.length ? 'Radar found <span class="c-unrec">' + fs.length + ' patches</span> of land change. The hotspot cross-check is next.' : 'Radar results are on their way.';
      $('h-sub').textContent = 'This page updates as each part of the analysis is delivered.';
      var tot = fs.reduce(function (a, f) { return a + (f.properties.area_ha || 0); }, 0) / 100;
      $('f-total').textContent = fs.length ? tot.toFixed(2) : '–';
      $('f-none').textContent = '–'; $('f-adj').textContent = '–'; $('f-adj-l').textContent = 'error-adjusted area pending';
      return;
    }
    $('h-share').textContent = pct(c.no_hotspot_share);
    var bits = [];
    if (c.mc) bits.push('Likely range ' + pct(c.mc.p05) + ' to ' + pct(c.mc.p95));
    bits.push(c.n_patches + ' patches over ' + D.manifest.dates.length + ' radar dates');
    if (D.manifest.fixture) bits.push('demo data');
    $('h-sub').textContent = bits.join(' · ');
    $('f-total').textContent = c.total_change_km2.toFixed(2);
    $('f-none').textContent = c.no_hotspot_km2.toFixed(2);
    var ae = v && v.area_estimate;
    if (ae) { $('f-adj').textContent = ae.km2.toFixed(1); $('f-adj-l').textContent = 'km² error-adjusted (95% CI ' + ae.ci95_low.toFixed(1) + '–' + ae.ci95_high.toFixed(1) + ')'; }
    else { $('f-adj').textContent = '–'; $('f-adj-l').textContent = 'error-adjusted area pending'; }
  }

  /* ---------- explore: map ---------- */
  function buildMap() {
    var b = D.manifest.bounds;
    map = L.map('map', { preferCanvas: true, zoomControl: false, attributionControl: false, zoomSnap: 0.25, zoomDelta: 0.5, wheelPxPerZoomLevel: 120, maxBoundsViscosity: 0.8 });
    map.setView(L.latLngBounds(b).getCenter(), 12, { animate: false });   // real fit happens once the map is visible
    map.setMaxBounds(L.latLngBounds(b).pad(0.6));
    L.control.scale({ position: 'bottomright', imperial: false, maxWidth: 120 }).addTo(map);
    overlay = L.imageOverlay(ovr(D.manifest.dates[0]) || BLANK, b, { className: 'map-overlay-img', interactive: false }).addTo(map);
    if (D.manifest.peat) {
      peatLayer = L.imageOverlay(DATA + D.manifest.peat.url, D.manifest.peat.bounds, { interactive: false });
      $('peat-toggle').hidden = false;
      $('peat-toggle').onclick = function () {
        var on = !map.hasLayer(peatLayer);
        if (on) peatLayer.addTo(map); else map.removeLayer(peatLayer);
        $('peat-toggle').setAttribute('aria-pressed', String(on));
        if (patchLayer) patchLayer.bringToFront();
      };
    }
    // preload every overlay so playback does not flicker
    Object.keys(D.manifest.overlays).forEach(function (k) { var i = new Image(); i.src = ovr(k); });
    patchLayer = L.geoJSON(D.patches || { type: 'FeatureCollection', features: [] }, {
      style: patchStyle,
      onEachFeature: function (f, layer) {
        var p = f.properties, st = STATUS[p.hotspot_status] || STATUS.unknown;
        layer.bindTooltip(p.patch_id + ' · ' + p.area_ha.toFixed(1) + ' ha · ' + st.label, { className: 'ptip', sticky: true, direction: 'top', offset: [0, -6] });
        layer.on('click', function () { selectPatch(p.patch_id); });
      }
    }).addTo(map);
    hotLayer = L.layerGroup().addTo(map);
    eventLayer = L.layerGroup().addTo(map);
    drawEvents();
    $('z-in').onclick = function () { map.zoomIn(); };
    $('z-out').onclick = function () { map.zoomOut(); };
    $('z-fit').onclick = function () { userMoved = false; map.fitBounds(b, { padding: [24, 24] }); };
    // keep the study area framed when the layout changes, until the user moves the map
    map.on('dragstart', function () { userMoved = true; });
    $('z-in').addEventListener('click', function () { userMoved = true; });
    $('z-out').addEventListener('click', function () { userMoved = true; });
    if (window.ResizeObserver) new ResizeObserver(function () { if (!map || !$('map').clientWidth) return; map.invalidateSize(); if (!userMoved) fitMap(); }).observe($('map'));
    else window.addEventListener('resize', function () { map.invalidateSize(); });
    refreshMap();
  }
  function patchStyle(f) {
    var p = f.properties, st = STATUS[p.hotspot_status] || STATUS.unknown, col = css(st.color);
    var on = S.view === 'after' && p.first_change_date <= D.manifest.dates[S.sel];
    var selected = p.patch_id === S.patch;
    return {
      color: selected ? css('radar') : col, weight: selected ? 3 : 1.6, opacity: on ? 1 : 0,
      fillColor: col, fillOpacity: on ? (p.hotspot_status === 'insufficient_data' ? 0.12 : 0.32) : 0,
      dashArray: p.hotspot_status === 'insufficient_data' ? '4 3' : null, interactive: on
    };
  }
  function styleLayers() {
    if (!patchLayer) return;
    patchLayer.setStyle(patchStyle);
    patchLayer.eachLayer(function (l) {
      var on = S.view === 'after' && l.feature.properties.first_change_date <= D.manifest.dates[S.sel];
      var el = l.getElement && l.getElement(); if (el) el.style.pointerEvents = on ? 'auto' : 'none';
      if (l.feature.properties.patch_id === S.patch && on) l.bringToFront();
    });
    drawHotspots();
  }
  function drawHotspots() {
    hotLayer.clearLayers();
    if (S.view !== 'after' || !D.hotspots) return;
    var dates = D.manifest.dates, cur = dates[S.sel], prev = S.sel > 0 ? dates[S.sel - 1] : '0000';
    D.hotspots.features.forEach(function (f) {
      var d = f.properties.acq_date; if (!(d > prev && d <= cur)) return;
      var c = f.geometry.coordinates;
      L.circleMarker([c[1], c[0]], { radius: 4.5, weight: 1.5, color: css('hotspot-ring'), fillColor: css('hotspot'), fillOpacity: 1, interactive: true })
        .bindTooltip(f.properties.sensor + ' hotspot · ' + lab(d), { className: 'ptip', direction: 'top', offset: [0, -4] })
        .addTo(hotLayer);
    });
  }
  function drawEvents() {
    eventLayer.clearLayers();
    var fs = (D.events && D.events.features) || [], box = L.latLngBounds(D.manifest.bounds).pad(0.6), n = 0;
    fs.forEach(function (f) {
      if (!f.geometry || f.geometry.type !== 'Point') return;
      var ll = L.latLng(f.geometry.coordinates[1], f.geometry.coordinates[0]);
      if (!box.contains(ll)) return;
      n++;
      L.marker(ll, { icon: L.divIcon({ className: 'ev-pin', html: '<i></i>', iconSize: [12, 12] }), keyboard: false })
        .bindTooltip((f.properties.title || 'EONET event') + (f.properties.date ? ' · ' + lab(String(f.properties.date).slice(0, 10)) : ''), { className: 'ptip', direction: 'top', offset: [0, -6] })
        .addTo(eventLayer);
    });
    $('lg-event').hidden = n === 0;
  }

  function setDate(k, view) {
    S.sel = Math.max(0, Math.min(D.manifest.dates.length - 1, k));
    if (view) S.view = view;
    var date = S.view === 'after' ? D.manifest.dates[S.sel] : D.manifest.dates[0];
    overlay.setUrl(ovr(date) || BLANK);
    $('map-date').textContent = S.view === 'after' ? labY(D.manifest.dates[S.sel]) : 'Baseline · ' + labY(D.manifest.dates[0]);
    $('map-src').textContent = ovr(date) ? 'NISAR · L-band HV · 60 m' : 'Radar image not processed yet';
    document.querySelectorAll('.tick').forEach(function (t) { t.setAttribute('aria-pressed', String(+t.getAttribute('data-k') === S.sel)); });
    $('v-before').setAttribute('aria-pressed', String(S.view === 'before'));
    $('v-after').setAttribute('aria-pressed', String(S.view === 'after'));
    styleLayers();
    updateChartMarkers();
  }

  /* ---------- explore: timeline ---------- */
  function buildTimeline() {
    var box = $('ticks'), dates = D.manifest.dates;
    dates.forEach(function (d, k) {
      if (k > 0 && days(dates[k - 1], d) > 18) {           // a missing acquisition shows as a gap
        var g = document.createElement('div'); g.className = 'gap'; g.title = 'No NISAR acquisition between ' + lab(dates[k - 1]) + ' and ' + lab(d);
        g.innerHTML = '<span>gap</span>'; box.appendChild(g);
      }
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'tick'; b.setAttribute('data-k', k); b.setAttribute('aria-label', 'Radar date ' + labY(d));
      b.innerHTML = '<i aria-hidden="true"></i><span>' + lab(d) + '</span>';
      b.onclick = function () { stopPlay(); setDate(k, 'after'); };
      box.appendChild(b);
    });
    $('v-before').onclick = function () { stopPlay(); setDate(S.sel, 'before'); };
    $('v-after').onclick = function () { setDate(S.sel, 'after'); };
    $('play').onclick = function () { if (S.playing) stopPlay(); else play(); };
  }
  function play() {
    var k = 0; setDate(0, 'after');
    $('play').setAttribute('aria-pressed', 'true'); $('play').setAttribute('aria-label', 'Pause');
    S.playing = setInterval(function () {
      k++; if (k >= D.manifest.dates.length) { stopPlay(); return; }
      setDate(k, 'after');
    }, 1000);
  }
  function stopPlay() {
    if (S.playing) clearInterval(S.playing); S.playing = null;
    var b = $('play'); if (b) { b.setAttribute('aria-pressed', 'false'); b.setAttribute('aria-label', 'Play the season'); }
  }

  /* ---------- explore: patch panel ---------- */
  function selectPatch(id) {
    S.patch = id;
    var f = (D.patches.features || []).filter(function (x) { return x.properties.patch_id === id; })[0];
    if (!f) { $('p-title').textContent = 'No change patches yet'; return; }
    var p = f.properties, st = STATUS[p.hotspot_status] || STATUS.unknown;
    $('p-title').textContent = 'Patch ' + p.patch_id;
    $('p-drop').textContent = num(p.mean_drop_hv_db, 1) + ' dB';
    $('p-meta').textContent = 'since ' + lab(p.first_change_date) + ' · ' + p.area_ha.toFixed(1) + ' ha';
    var badges = '<span class="badge"><i class="' + st.cls + '"></i>' + st.label + '</span>';
    if (p.confidence_tier && p.confidence_tier !== 'unrated') badges += '<span class="badge">' + p.confidence_tier.charAt(0).toUpperCase() + p.confidence_tier.slice(1) + ' confidence</span>';
    badges += '<span class="badge">' + (INTERP[p.interpretation] || 'Not yet reviewed') + '</span>';
    (p.flags || []).forEach(function (fl) { badges += '<span class="badge">Flag: ' + fl.replace('_', ' ') + '</span>'; });
    $('p-badges').innerHTML = badges;
    var ev = [];
    var nh = p.n_hotspots || 0;
    ev.push(['Hotspots nearby', nh ? nh + ' within the buffer' + (p.nearest_hotspot_km != null ? ', nearest ' + p.nearest_hotspot_km.toFixed(1) + ' km' : '') : (p.hotspot_status === 'none' ? 'None recorded' : '–')]);
    if (p.window_start && p.window_end) ev.push(['Fire window', lab(p.window_start) + ' to ' + lab(p.window_end)]);
    ev.push(['HH change', p.hh_change_db != null ? num(p.hh_change_db, 1) + ' dB' : '–']);
    ev.push(['Dates changed', String(p.n_dates_changed != null ? p.n_dates_changed : '–')]);
    ev.push(['RADD alert', p.radd_agree === true ? 'Agrees' : p.radd_agree === false ? 'No alert' : 'Not checked']);
    var html = ev.map(function (r) { return '<div><dt>' + r[0] + '</dt><dd>' + r[1] + '</dd></div>'; }).join('');
    if (p.notes) html += '<div class="ev-wide"><dt>Reviewer note</dt><dd>' + esc(p.notes) + '</dd></div>';
    if (p.evidence_urls && p.evidence_urls.length) html += '<div class="ev-wide"><dt>Evidence</dt><dd>' + p.evidence_urls.map(function (u, i) { return '<a href="' + esc(u) + '" target="_blank" rel="noopener">Source ' + (i + 1) + '</a>'; }).join(' · ') + '</dd></div>';
    $('p-evidence').innerHTML = html;
    styleLayers();
    drawPatchChart();
    if (S.page === 'why') drawWhyChart();
  }
  function defaultPatch() {
    var fs = (D.patches && D.patches.features) || [];
    var none = fs.filter(function (f) { return f.properties.hotspot_status === 'none'; });
    var pool = none.length ? none : fs;
    pool.sort(function (a, b) { return b.properties.area_ha - a.properties.area_ha; });
    return pool.length ? pool[0].properties.patch_id : null;
  }

  /* ---------- charts ---------- */
  var markerPlugin = {
    id: 'bsMarker',
    afterDatasetsDraw: function (chart, args, o) {
      if (o == null || o.index == null) return;
      var x = chart.scales.x.getPixelForValue(o.index), a = chart.chartArea, c = chart.ctx;
      c.save(); c.strokeStyle = o.color; c.lineWidth = 1; c.beginPath(); c.moveTo(x, a.top - 4); c.lineTo(x, a.bottom + 4); c.stroke(); c.restore();
    }
  };
  var hlinePlugin = {
    id: 'bsHline',
    afterDatasetsDraw: function (chart, args, o) {
      if (o == null || o.value == null) return;
      var y = chart.scales.y.getPixelForValue(o.value), a = chart.chartArea, c = chart.ctx;
      c.save(); c.strokeStyle = o.color; c.setLineDash([4, 4]); c.lineWidth = 1; c.beginPath(); c.moveTo(a.left, y); c.lineTo(a.right, y); c.stroke(); c.restore();
    }
  };
  function baseOpts() {
    return {
      responsive: true, maintainAspectRatio: false, animation: reduced() ? false : { duration: 250 },
      plugins: { legend: { display: false }, tooltip: { backgroundColor: css('bg'), titleColor: css('ink'), bodyColor: css('ink-muted'), borderColor: css('line-strong'), borderWidth: 1, displayColors: false, titleFont: { family: 'Inter', weight: '500' }, bodyFont: { family: 'Inter' } } },
      layout: { padding: { top: 6, bottom: 0 } }
    };
  }
  function byDate() {
    var c = D.stats && D.stats.crosscheck;
    if (c && c.by_date) return c.by_date;
    // fallback: build from the patches
    return D.manifest.dates.map(function (d) {
      var ch = 0, no = 0;
      ((D.patches && D.patches.features) || []).forEach(function (f) {
        var p = f.properties; if (p.first_change_date !== d) return;
        ch += p.area_ha / 100; if (p.hotspot_status === 'none') no += p.area_ha / 100;
      });
      return { date: d, change_km2: ch, no_hotspot_km2: no };
    });
  }
  function drawBarChart() {
    var rows = byDate(), sel = S.sel;
    var none = css('unrecorded'), rec = css('recorded');
    var dim = function (col) { return rows.map(function (r, k) { return k === sel ? col : alpha(col, 0.45); }); };
    var data = {
      labels: rows.map(function (r) { return lab(r.date); }),
      datasets: [
        { label: 'Hotspot recorded', data: rows.map(function (r) { return Math.max(0, r.change_km2 - r.no_hotspot_km2); }), backgroundColor: dim(rec), stack: 's', borderSkipped: false, barPercentage: 0.56, categoryPercentage: 1 },
        { label: 'No hotspot recorded', data: rows.map(function (r) { return r.no_hotspot_km2; }), backgroundColor: dim(none), stack: 's', borderSkipped: false, barPercentage: 0.56, categoryPercentage: 1 }
      ]
    };
    if (!(D.stats && D.stats.crosscheck)) {      // not cross-checked yet: one neutral series, no recorded/unrecorded split
      var neutral = css('ink-faint');
      data.datasets = [{ label: 'Change, not yet cross-checked', data: rows.map(function (r) { return r.change_km2; }), backgroundColor: rows.map(function (r, k) { return k === sel ? neutral : alpha(neutral, 0.45); }), stack: 's', barPercentage: 0.56, categoryPercentage: 1 }];
    }
    var o = baseOpts();
    o.scales = {
      x: { stacked: true, grid: { display: false }, border: { color: css('line') }, ticks: { color: css('ink-faint'), font: { family: 'JetBrains Mono', size: 10 }, maxRotation: 0, autoSkip: false,
        callback: function (v, i) { return (i === 0 || i === rows.length - 1 || i === S.sel) ? this.getLabelForValue(v) : ''; } } },
      y: { stacked: true, display: false, beginAtZero: true }
    };
    o.plugins.tooltip.callbacks = { label: function (ctx) { return ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(2) + ' km²'; } };
    if (charts.bars) charts.bars.destroy();
    charts.bars = new Chart($('c-bars'), { type: 'bar', data: data, options: o });
  }
  function patchSeries() {
    var ts = D.timeseries; if (!ts || !S.patch || !ts.patches[S.patch]) return null;
    return { dates: ts.dates, hv: ts.patches[S.patch].hv_db, hh: ts.patches[S.patch].hh_db, ref: ts.reference.hv_db };
  }
  function lineChart(canvas, withHH) {
    var s = patchSeries();
    var box = canvas.parentNode; box.classList.toggle('empty', !s);
    if (!s) return null;
    var ds = [
      { label: 'Stable forest HV', data: s.ref, borderColor: css('ink-faint'), borderDash: [4, 4], borderWidth: 1.4, pointRadius: 0, tension: 0 },
      { label: 'This patch HV', data: s.hv, borderColor: css('unrecorded'), borderWidth: 2.2, pointRadius: 0, pointHoverRadius: 4, tension: 0 }
    ];
    var rain = rainByDate(s.dates);
    if (rain) ds.unshift({ type: 'bar', label: 'Rain since previous date', data: rain, yAxisID: 'r', backgroundColor: alpha(css('radar'), 0.18), borderWidth: 0, barPercentage: 0.5, order: 3 });
    if (withHH && s.hh) ds.push({ label: 'This patch HH', data: s.hh, borderColor: alpha(css('unrecorded'), 0.4), borderWidth: 1.4, pointRadius: 0, tension: 0 });
    var o = baseOpts();
    o.interaction = { mode: 'index', intersect: false };
    o.scales = {
      x: { display: !!withHH, grid: { display: false }, border: { color: css('line') }, ticks: { color: css('ink-faint'), font: { family: 'JetBrains Mono', size: 10.5 }, maxRotation: 0, autoSkipPadding: 18 } },
      y: { display: !!withHH, grid: { color: css('line') }, border: { display: false }, ticks: { color: css('ink-faint'), font: { family: 'JetBrains Mono', size: 10.5 }, callback: function (v) { return num(v, 0) + ' dB'; } } },
      r: { display: false, position: 'right', beginAtZero: true, grid: { display: false }, suggestedMax: 400 }
    };
    o.plugins.tooltip.callbacks = { label: function (ctx) { return ctx.dataset.yAxisID === 'r' ? 'Rain: ' + ctx.parsed.y.toFixed(0) + ' mm' : ctx.dataset.label + ': ' + num(ctx.parsed.y, 1) + ' dB'; } };
    o.plugins.bsMarker = { index: S.sel, color: css('radar') };
    return new Chart(canvas, { type: 'line', data: { labels: s.dates.map(lab), datasets: ds }, options: o, plugins: [markerPlugin] });
  }
  function rainByDate(dates) {
    if (!D.rain || !D.rain.length) return null;
    return dates.map(function (d, k) {
      var from = k > 0 ? dates[k - 1] : '0000';
      return D.rain.reduce(function (a, r) { return r.date > from && r.date <= d ? a + r.value : a; }, 0);
    });
  }
  function drawPatchChart() { if (charts.patch) charts.patch.destroy(); charts.patch = lineChart($('c-patch'), false); }
  function drawWhyChart() { if (charts.why) charts.why.destroy(); charts.why = lineChart($('c-why'), true); }
  function updateChartMarkers() {
    if (charts.bars) {
      var n = charts.bars.data.labels.length, ds = charts.bars.data.datasets;
      var dim = function (col) { var a = []; for (var k = 0; k < n; k++) a.push(k === S.sel ? col : alpha(col, 0.45)); return a; };
      if (ds.length === 2) { ds[0].backgroundColor = dim(css('recorded')); ds[1].backgroundColor = dim(css('unrecorded')); }
      else ds[0].backgroundColor = dim(css('ink-faint'));
      charts.bars.update('none');
    }
    ['patch', 'why'].forEach(function (k) { if (charts[k]) { charts[k].options.plugins.bsMarker.index = S.sel; charts[k].update('none'); } });
  }
  function drawPsiChart() {
    if (!D.psi || !D.psi.length) return;
    if (charts.psi) charts.psi.destroy();
    var o = baseOpts();
    o.interaction = { mode: 'index', intersect: false };
    o.scales = {
      x: { grid: { display: false }, border: { color: css('line') }, ticks: { color: css('ink-faint'), font: { family: 'JetBrains Mono', size: 10.5 }, maxRotation: 0, autoSkipPadding: 28 } },
      y: { beginAtZero: true, grid: { color: css('line') }, border: { display: false }, ticks: { color: css('ink-faint'), font: { family: 'JetBrains Mono', size: 10.5 } } }
    };
    o.plugins.bsHline = { value: 100, color: css('ink-muted') };
    o.plugins.tooltip.callbacks = { label: function (ctx) { return 'PSI ' + ctx.parsed.y; } };
    charts.psi = new Chart($('c-psi'), {
      type: 'line',
      data: { labels: D.psi.map(function (r) { return lab(r.date); }), datasets: [{ data: D.psi.map(function (r) { return r.value; }), borderColor: css('haze'), backgroundColor: alpha(css('haze'), 0.12), fill: true, borderWidth: 1.8, pointRadius: 0, pointHoverRadius: 4, tension: 0.2 }] },
      options: o, plugins: [hlinePlugin]
    });
  }
  function drawCharts() {
    drawBarChart(); drawPatchChart();
    if (S.page === 'why') drawWhyChart();
    if (S.page === 'singapore') drawPsiChart();
  }

  /* ---------- editorial content from data ---------- */
  function renderPsi() {
    if (!D.psi || !D.psi.length) { document.querySelectorAll('[data-psi-peak]').forEach(function (el) { el.textContent = '–'; }); return; }
    var peak = D.psi.reduce(function (m, r) { return r.value > m.value ? r : m; }, D.psi[0]);
    document.querySelectorAll('[data-psi-peak]').forEach(function (el) { el.textContent = Math.round(peak.value); });
    document.querySelectorAll('[data-psi-peak-label]').forEach(function (el) { el.textContent = "Singapore's peak 24-hr PSI this season, " + labY(peak.date); });
    $('psi-peak-label').textContent = '24-hr PSI, ' + labY(peak.date) + (D.manifest.fixture ? ' (demo data)' : '');
    $('psi-marker').style.left = Math.min(100, peak.value / 400 * 100) + '%';
  }
  function renderWhyImages() {
    var bb = D.manifest.study_bbox, dates = D.manifest.dates, want = '2026-10-09';
    var near = dates.reduce(function (m, d) { return Math.abs(days(d, want)) < Math.abs(days(m, want)) ? d : m; }, dates[0]);
    $('radar-img').src = ovr(near);
    $('radar-date').textContent = labY(near);
    var layers = ['VIIRS_SNPP_CorrectedReflectance_TrueColor', 'MODIS_Terra_CorrectedReflectance_TrueColor'], tryN = 0;
    function src(layer) {
      return 'https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&STYLES=&FORMAT=image/jpeg&CRS=EPSG:4326'
        + '&LAYERS=' + layer + '&BBOX=' + [bb[1], bb[0], bb[3], bb[2]].join(',') + '&WIDTH=512&HEIGHT=512&TIME=' + want;
    }
    var img = $('gibs-img');
    img.onerror = function () { tryN++; if (tryN < layers.length) img.src = src(layers[tryN]); else { img.hidden = true; $('gibs-fail').hidden = false; } };
    img.src = src(layers[0]);
  }
  function renderSure() {
    var c = D.stats && D.stats.crosscheck, v = (D.stats && D.stats.validation) || {}, out = [];
    function item(t, d) { out.push('<div><dt>' + t + '</dt><dd>' + d + '</dd></div>'); }
    var ae = v.area_estimate;
    if (ae) item(ae.km2.toFixed(1) + ' km²', 'error-adjusted area of burn and clearing, 95% interval ' + ae.ci95_low.toFixed(1) + ' to ' + ae.ci95_high.toFixed(1) + ' km² (Olofsson 2014)' + (v.sample ? ', from ' + v.sample.n_labelled + ' labelled reference points' : ''));
    else item('Pending', 'error-adjusted area from the labelled reference sample');
    if (c && c.mc) {
      var pr = c.params || {}, bk = pr.mc_buffer_km, sl = pr.mc_slack_days;
      item(pct(c.mc.p05) + ' to ' + pct(c.mc.p95), 'share with no hotspot across ' + c.mc.runs + ' Monte Carlo runs' + (bk && sl ? ' (buffer ' + bk[0] + ' to ' + bk[1] + ' km, window slack ' + sl[0] + ' to ' + sl[1] + ' days)' : ''));
    }
    var syn = v.synthetic;
    if (syn && syn.false_alarm_rate != null) item((syn.false_alarm_rate * 100).toFixed(2) + '%', 'of stable pixels flagged as change in the synthetic burn test');
    if (syn && syn.curve && syn.curve.length) {
      var top = Math.max.apply(null, syn.curve.map(function (r) { return r.drop_db; }));
      var ok = syn.curve.filter(function (r) { return r.drop_db === top && r.detection_rate >= 0.8; }).map(function (r) { return r.size_ha; });
      if (ok.length) item(Math.min.apply(null, ok) + ' ha', 'smallest synthetic burn found in at least 80% of trials at a ' + top + ' dB drop');
    }
    if (v.radd_agreement) item(pct(v.radd_agreement.share), 'of ' + v.radd_agreement.n_patches + ' patches also flagged by RADD alerts');
    else item('Pending', 'agreement with RADD forest disturbance alerts');
    $('sure').innerHTML = out.join('');
    var gen = D.manifest.generated; if (gen) $('generated').textContent = labY(gen.slice(0, 10)) + (D.manifest.fixture ? ' (demo data)' : '');
  }

  /* ---------- boot ---------- */
  function boot() {
    setTheme(store('bs-theme') || 'dark');
    var tb = document.querySelector('.theme-toggle');
    if (tb) tb.onclick = function () { setTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark'); };

    intro = window.BlindSpotIntro && window.BlindSpotIntro.init({
      root: $('intro'), stars: $('stars'), globe: $('globe'), drag: $('spin'),
      textures: { uDay: 'assets/globe/earth-day.jpg', uNight: 'assets/globe/earth-night.jpg', uWater: 'assets/globe/earth-water.png' },
      onReveal: function () { enterApp(false); },
      onArrive: function () { $('intro').setAttribute('data-phase', 'gone'); }
    });
    $('start').onclick = function () { $('intro').setAttribute('data-phase', 'flying'); if (intro) intro.dive(); else { enterApp(true); } };
    $('home').onclick = leaveApp;
    window.addEventListener('hashchange', function () { var p = location.hash.slice(1); if (PAGES.indexOf(p) < 0) return; if ($('app').hidden) enterApp(true); else showPage(p); });
    $('app').addEventListener('scroll', function () { $('to-top').classList.toggle('on', S.page !== 'explore' && $('app').scrollTop > 400); });
    $('to-top').onclick = function () { $('app').scrollTo({ top: 0, behavior: reduced() ? 'auto' : 'smooth' }); };

    var deep = PAGES.indexOf(location.hash.slice(1)) >= 0;
    if (deep) enterApp(true); else if (intro) intro.start();

    Promise.all(['manifest.json', 'patches.geojson', 'hotspots.geojson', 'timeseries.json', 'stats.json', 'psi.json', 'rain.json', 'events.geojson'].map(fetchJSON)).then(function (r) {
      D.manifest = r[0]; D.patches = r[1] || { type: 'FeatureCollection', features: [] }; D.hotspots = r[2]; D.timeseries = r[3]; D.stats = r[4]; D.psi = r[5]; D.rain = r[6]; D.events = r[7];
      if (!D.manifest) { $('h-sub').textContent = 'No data found in web/data/. Run make demo or make real.'; return; }
      if (D.manifest.fixture) { $('demo-banner').hidden = false; $('app').classList.add('has-banner'); }
      if (!D.manifest.dates || !D.manifest.dates.length) { $('h-sub').textContent = 'No radar dates in the data yet.'; return; }
      if (!D.manifest.bounds) { var bb = D.manifest.study_bbox; D.manifest.bounds = [[bb[1], bb[0]], [bb[3], bb[2]]]; }
      D.manifest.overlays = D.manifest.overlays || {};
      renderHeadline();
      buildMap();
      buildTimeline();
      var q = new URLSearchParams(location.search);   // ?patch=P0016&date=2026-09-22 for shareable views
      S.patch = q.get('patch') || defaultPatch();
      var qd = D.manifest.dates.indexOf(q.get('date'));
      var start = qd >= 0 ? qd : D.manifest.dates.indexOf(((D.patches.features.filter(function (f) { return f.properties.patch_id === S.patch; })[0] || {}).properties || {}).first_change_date);
      setDate(start >= 0 ? start : D.manifest.dates.length - 1, 'after');
      drawBarChart();
      if (S.patch) selectPatch(S.patch);
      document.querySelectorAll('.sw-rain').forEach(function (el) { el.parentNode.hidden = !(D.rain && D.rain.length); });
      renderPsi(); renderWhyImages(); renderSure();
      if (S.page === 'why') drawWhyChart();
      if (S.page === 'singapore') drawPsiChart();
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
