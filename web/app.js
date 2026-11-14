/* Surface Dance Observatory — Leaflet viewer for layers produced by
 * pipeline/change_detection.py (web/layers/index.json + <site>/<pol>/meta.json). */
(function () {
  'use strict';

  const LAYERS = 'layers';
  const $ = (id) => document.getElementById(id);
  const wrap = document.querySelector('.map-wrap');
  const handle = $('swipe-handle');

  // ---- Map & basemaps -------------------------------------------------------
  const map = L.map('map', { zoomControl: true, worldCopyJump: true }).setView([10, -40], 3);
  const basemaps = {
    'Satellite (Esri)': L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 18, attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics' }),
    'Streets (OSM)': L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }),
  };
  basemaps['Satellite (Esri)'].addTo(map);
  L.control.layers(basemaps, null, { position: 'bottomleft' }).addTo(map);
  L.control.scale({ imperial: false }).addTo(map);
  map.attributionControl.addAttribution('NISAR: NASA/JPL-Caltech &amp; ISRO via ASF DAAC');

  for (const [name, z] of [['before', 410], ['after', 420], ['change', 430]]) {
    map.createPane(name).style.zIndex = z;
  }
  const afterPane = map.getPane('after');

  // ---- State ----------------------------------------------------------------
  const params = new URLSearchParams(location.search);
  const state = { index: null, site: null, pol: null, mode: params.get('mode') === 'change' ? 'change' : 'swipe', pct: 0.5, meta: null };
  const overlays = { before: null, after: null, change: null };

  // ---- Swipe ----------------------------------------------------------------
  function updateClip() {
    const size = map.getSize();
    const nw = map.containerPointToLayerPoint([0, 0]);
    const se = map.containerPointToLayerPoint(size);
    const x = nw.x + size.x * state.pct;
    afterPane.style.clip = state.mode === 'swipe' ? `rect(${nw.y}px, ${se.x}px, ${se.y}px, ${x}px)` : '';
    handle.style.left = (state.pct * 100) + '%';
    handle.setAttribute('aria-valuenow', Math.round(state.pct * 100));
  }
  function setPct(clientX) {
    const r = wrap.getBoundingClientRect();
    state.pct = Math.min(1, Math.max(0, (clientX - r.left) / r.width));
    updateClip();
  }
  handle.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    handle.setPointerCapture(e.pointerId);
    map.dragging.disable();
  });
  handle.addEventListener('pointermove', (e) => { if (handle.hasPointerCapture(e.pointerId)) setPct(e.clientX); });
  handle.addEventListener('pointerup', (e) => { handle.releasePointerCapture(e.pointerId); map.dragging.enable(); });
  handle.addEventListener('keydown', (e) => {
    const step = e.shiftKey ? 0.1 : 0.02;
    if (e.key === 'ArrowLeft') state.pct = Math.max(0, state.pct - step);
    else if (e.key === 'ArrowRight') state.pct = Math.min(1, state.pct + step);
    else return;
    e.preventDefault();
    updateClip();
  });
  map.on('move zoom resize viewreset zoomend moveend', updateClip);

  // ---- Rendering --------------------------------------------------------------
  function dl(el, rows) {
    el.replaceChildren();
    for (const [k, v, cls] of rows) {
      if (cls === 'hdr') {
        const d = document.createElement('div'); d.className = 'hdr'; d.textContent = k; el.append(d); continue;
      }
      const dt = document.createElement('dt'); dt.textContent = k;
      const dd = document.createElement('dd'); dd.textContent = v ?? '—';
      el.append(dt, dd);
    }
  }

  function setMode(mode) {
    state.mode = mode;
    $('mode-swipe').setAttribute('aria-pressed', mode === 'swipe');
    $('mode-change').setAttribute('aria-pressed', mode === 'change');
    wrap.classList.toggle('hidden-swipe', mode !== 'swipe' || !state.meta);
    $('opacity-row').hidden = mode !== 'change';
    $('legend').hidden = mode !== 'change' || !state.meta;
    if (state.meta) {
      toggle(overlays.before, mode === 'swipe');
      toggle(overlays.after, mode === 'swipe');
      toggle(overlays.change, mode === 'change');
    }
    updateClip();
    syncUrl();
  }
  function toggle(layer, on) { if (!layer) return; on ? layer.addTo(map) : layer.remove(); }

  function syncUrl() {
    if (!state.site) return;
    const q = new URLSearchParams({ site: state.site.id, pol: state.pol, mode: state.mode });
    history.replaceState(null, '', '?' + q.toString());
  }

  async function loadLayer(fit) {
    const base = `${LAYERS}/${encodeURIComponent(state.site.id)}/${encodeURIComponent(state.pol)}`;
    const meta = await fetch(`${base}/meta.json`, { cache: 'no-cache' }).then((r) => {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    });
    state.meta = meta;
    const b = meta.bounds_wgs84;
    const bounds = [[b.south, b.west], [b.north, b.east]];
    for (const k of Object.keys(overlays)) { if (overlays[k]) overlays[k].remove(); }
    overlays.before = L.imageOverlay(`${base}/before.png`, bounds, { pane: 'before', alt: `Radar ${meta.before.date}` });
    overlays.after = L.imageOverlay(`${base}/after.png`, bounds, { pane: 'after', alt: `Radar ${meta.after.date}` });
    overlays.change = L.imageOverlay(`${base}/change.png`, bounds, { pane: 'change', alt: 'Backscatter change', opacity: $('opacity').value / 100 });
    if (fit) map.fitBounds(bounds, { padding: [20, 20] });

    $('date-left').textContent = meta.before.date;
    $('date-right').textContent = meta.after.date;

    dl($('scenes'), [
      ['Before', null, 'hdr'], ['Date', meta.before.date], ['Collection', meta.before.collection], ['CRID', meta.before.crid], ['File', meta.before.file],
      ['After', null, 'hdr'], ['Date', meta.after.date], ['Collection', meta.after.collection], ['CRID', meta.after.crid], ['File', meta.after.file],
    ]);
    const pr = meta.processing;
    const filt = pr.speckle_filter === 'none' ? 'None'
      : `${pr.speckle_filter === 'lee' ? 'Lee' : 'Boxcar'} ${pr.window_px}×${pr.window_px} px (≈${pr.window_m} m)` + (pr.enl ? `, ENL ${pr.enl}` : '');
    dl($('processing'), [
      ['Polarization', meta.polarization],
      ['Speckle filter', filt],
      ['Pixel size', `${pr.web_pixel_m} m (web)`],
      ['Change', '10·log10(after / before) dB'],
    ]);
    const s = meta.stats;
    $('stats').hidden = false;
    $('stats').innerHTML = '<h2>Change ≥ <span id="thr"></span> dB</h2>' +
      '<div class="stat"><span><span class="sw red"></span>Increase</span><b id="s-inc"></b></div>' +
      '<div class="stat"><span><span class="sw blue"></span>Decrease</span><b id="s-dec"></b></div>' +
      '<div class="stat"><span>Median change</span><b id="s-med"></b></div>';
    $('thr').textContent = s.threshold_db;
    $('s-inc').textContent = s.pct_increase.toFixed(1) + ' % of area';
    $('s-dec').textContent = s.pct_decrease.toFixed(1) + ' % of area';
    $('s-med').textContent = (s.median_change_db > 0 ? '+' : '') + s.median_change_db.toFixed(2) + ' dB';
    const lim = meta.display.change_limit_db;
    $('leg-min').textContent = '−' + lim.toFixed(1) + ' dB';
    $('leg-max').textContent = '+' + lim.toFixed(1) + ' dB';
    setMode(state.mode);
  }

  function fillPols(preferred) {
    const sel = $('pol');
    sel.replaceChildren(...state.site.polarizations.map((p) => new Option(p, p)));
    state.pol = state.site.polarizations.includes(preferred) ? preferred : state.site.polarizations[0];
    sel.value = state.pol;
  }

  function showEmpty(msg) {
    $('empty').hidden = false;
    if (msg) $('empty').querySelector('strong').textContent = msg;
    wrap.classList.add('hidden-swipe');
    for (const id of ['site', 'pol', 'mode-swipe', 'mode-change']) $(id).disabled = true;
  }

  // ---- Wiring -------------------------------------------------------------------
  $('mode-swipe').onclick = () => setMode('swipe');
  $('mode-change').onclick = () => setMode('change');
  $('opacity').oninput = (e) => overlays.change && overlays.change.setOpacity(e.target.value / 100);
  $('site').onchange = (e) => {
    state.site = state.index.sites.find((s) => s.id === e.target.value);
    fillPols(state.pol);
    loadLayer(true).catch(() => showEmpty('Could not load this layer.'));
  };
  $('pol').onchange = (e) => {
    state.pol = e.target.value;
    loadLayer(false).catch(() => showEmpty('Could not load this layer.'));
  };

  fetch(`${LAYERS}/index.json`, { cache: 'no-cache' })
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((idx) => {
      if (!idx.sites || !idx.sites.length) return showEmpty();
      state.index = idx;
      $('site').replaceChildren(...idx.sites.map((s) => new Option(s.name, s.id)));
      state.site = idx.sites.find((s) => s.id === params.get('site')) || idx.sites[0];
      $('site').value = state.site.id;
      fillPols(params.get('pol'));
      return loadLayer(true);
    })
    .catch(() => showEmpty());

  setMode(state.mode);
})();
