/* Surface Dance — Leaflet viewer for layers produced by
 * pipeline/change_detection.py (web/layers/index.json + <site>/<pol>/meta.json). */
(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  // ?demo=1 loads synthetic test layers from web/demo/ under a visible banner.
  const DEMO = new URLSearchParams(location.search).get('demo') === '1';
  const LAYERS = DEMO ? 'demo' : 'layers';
  if (DEMO) { $('demo-banner').hidden = false; document.body.classList.add('is-demo'); }
  const wrap = document.querySelector('.map-wrap');
  const handle = $('swipe-handle');

  // What each channel "listens to". Wording reviewed against NASA Earthdata SAR basics.
  const POL_NOTES = {
    HH: 'Co-polarized. Open water looks dark; flooded vegetation can look very bright, because the pulse bounces between water and trunks.',
    VV: 'Co-polarized. Sensitive to surface roughness, including wind ripples on water.',
    HV: 'Cross-polarized. Listens to volume scattering: tree crowns, crops and structurally complex ice.',
    VH: 'Cross-polarized. Listens to volume scattering: tree crowns, crops and structurally complex ice.',
  };
  const polKey = (p) => p.slice(0, 2).toUpperCase();
  const polLabel = (p) => (p.length === 4 && p.slice(0, 2) === p.slice(2) ? p.slice(0, 2) : p);
  const fmtDate = (iso) => new Date(iso + 'T00:00:00Z')
    .toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' });

  // ---- Map & basemaps -------------------------------------------------------
  const map = L.map('map', { zoomControl: false, worldCopyJump: true }).setView([12, -60], 3);
  L.control.zoom({ position: 'topright' }).addTo(map);
  const basemaps = {
    'Satellite': L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 18, attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics' }),
    'Streets': L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }),
  };
  basemaps['Satellite'].addTo(map);
  L.control.layers(basemaps, null, { position: 'topright' }).addTo(map);
  L.control.scale({ imperial: false, position: 'topright' }).addTo(map);
  map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
  map.attributionControl.addAttribution('NISAR: NASA/JPL-Caltech &amp; ISRO via ASF');

  for (const [name, z] of [['before', 410], ['after', 420], ['change', 430]]) {
    map.createPane(name).style.zIndex = z;
  }
  const afterPane = map.getPane('after');

  // ---- State ----------------------------------------------------------------
  const params = new URLSearchParams(location.search);
  const state = { index: null, site: null, pol: null, mode: params.get('mode') === 'change' ? 'change' : 'swipe', pct: 0.5, meta: null };
  const overlays = { before: null, after: null, change: null };

  // ---- Archive timeline -------------------------------------------------------
  const T0 = Date.UTC(2025, 9, 1), T1 = Date.UTC(2026, 11, 15);
  const pos = (iso) => {
    const t = typeof iso === 'number' ? iso : Date.parse(iso + 'T00:00:00Z');
    return (100 * (Math.min(Math.max(t, T0), T1) - T0) / (T1 - T0)).toFixed(3) + '%';
  };
  function el(cls, style, html) {
    const d = document.createElement('div');
    d.className = cls;
    Object.assign(d.style, style);
    if (html) d.innerHTML = html;
    return d;
  }
  function buildTimeline() {
    const tl = $('timeline');
    const today = Date.now();
    for (let y = 2025, m = 9; Date.UTC(y, m, 1) <= T1; m === 11 ? (y++, m = 0) : m++) {
      const t = Date.UTC(y, m, 1);
      tl.append(el('tl-tick', { left: pos(t) }));
      const name = new Date(t).toLocaleDateString('en-GB', { month: 'short', timeZone: 'UTC' });
      tl.append(el('tl-month' + (m % 3 ? ' minor' : ''), { left: pos(t), transform: t === T0 ? 'none' : '' }, m === 0 ? `${name}&nbsp;${String(y).slice(2)}` : name));
    }
    const seg = (cls, a, b, title) => {
      const s = el('tl-seg ' + cls, { left: pos(a), width: `calc(${pos(b)} - ${pos(a)})` });
      s.title = title;
      tl.append(s);
    };
    seg('beta', '2025-10-17', '2026-01-20', 'BETA · 17 Oct 2025 – 20 Jan 2026 · not fully calibrated');
    seg('prov', '2026-06-17', '2026-10-23', 'PROVISIONAL · CRID P05023 · 17 Jun – 23 Oct 2026');
    seg('val', '2026-10-21', today, 'VALIDATED · CRID P05036 · from 21 Oct 2026');
    seg('gap', '2026-07-27', '2026-08-10', 'Permanent instrument gap · 27 Jul – 10 Aug 2026');
    tl.append(el('tl-label', { left: pos('2025-10-17') }, '<b>BETA</b><span>context only</span>'));
    tl.append(el('tl-label', { left: pos('2026-06-17') }, '<b>PROVISIONAL</b><span>P05023</span>'));
    tl.append(el('tl-label gap-label', { left: pos('2026-07-27'), top: '58px' }, '<span>instrument gap</span>'));
    tl.append(el('tl-label end', { right: '0' }, '<b>VALIDATED</b><span>P05036</span>'));
    const td = el('tl-today', { left: pos(today) });
    td.title = 'Today';
    tl.append(td);
  }
  function markTimeline(meta) {
    const tl = $('timeline');
    tl.querySelectorAll('.tl-mark').forEach((m) => m.remove());
    for (const k of ['before', 'after']) {
      const m = el('tl-mark ' + k, { left: pos(meta[k].date) });
      m.title = `${k === 'before' ? 'Before' : 'After'}: ${fmtDate(meta[k].date)}`;
      tl.append(m);
    }
  }

  // ---- Swipe ----------------------------------------------------------------
  function updateClip() {
    const size = map.getSize();
    const nw = map.containerPointToLayerPoint([0, 0]);
    const se = map.containerPointToLayerPoint(size);
    const x = nw.x + size.x * state.pct;
    afterPane.style.clip = state.mode === 'swipe' ? `rect(${nw.y}px, ${se.x}px, ${se.y}px, ${x}px)` : '';
    handle.style.left = (state.pct * 100) + '%';
    handle.setAttribute('aria-valuenow', Math.round(state.pct * 100));
    // HUD cursor: share of the map showing the 'after' date (left of the line = before)
    $('hud-cursor').style.left = `${12 + 76 * (1 - state.pct)}%`;
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

  // ---- Play: the line sways between the two dates on its own --------------------
  const AMP = 0.45, PERIOD = 5000;
  let raf = null;
  function play() {
    if (state.mode !== 'swipe') setMode('swipe');
    const start = performance.now();
    const phase = Math.asin(Math.max(-1, Math.min(1, (state.pct - 0.5) / AMP)));
    const step = (now) => {
      state.pct = 0.5 + AMP * Math.sin(phase + (2 * Math.PI * (now - start)) / PERIOD);
      updateClip();
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    setPlayButton(true);
  }
  function stop() {
    if (raf) cancelAnimationFrame(raf);
    raf = null;
    setPlayButton(false);
  }
  function setPlayButton(on) {
    const b = $('play');
    b.setAttribute('aria-pressed', on);
    b.querySelector('.play-icon').textContent = on ? '❚❚' : '▶';
    b.querySelector('.play-label').textContent = on ? 'Pause' : 'Play the dance';
  }
  $('play').onclick = () => (raf ? stop() : play());

  // First load: a short sway shows that the line can be moved. Any touch stops it.
  let hinted = false;
  function hint() {
    if (hinted || state.mode !== 'swipe' || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    hinted = true;
    const start = performance.now(), DUR = 2200;
    const step = (now) => {
      const t = now - start;
      if (raf || t > DUR) { if (!raf) { state.pct = 0.5; updateClip(); } return; }
      state.pct = 0.5 + 0.16 * Math.sin((2 * Math.PI * t) / 1100) * (1 - t / DUR);
      updateClip();
      hintRaf = requestAnimationFrame(step);
    };
    hintRaf = requestAnimationFrame(step);
  }
  let hintRaf = null;
  const cancelHint = () => { if (hintRaf) cancelAnimationFrame(hintRaf); hintRaf = null; };
  handle.addEventListener('pointerdown', cancelHint);
  handle.addEventListener('keydown', cancelHint, true);
  handle.addEventListener('pointerdown', stop);
  handle.addEventListener('keydown', stop, true);

  // ---- Rendering --------------------------------------------------------------
  function setMode(mode) {
    state.mode = mode;
    document.body.classList.toggle('mode-change', mode === 'change');
    if (mode !== 'swipe') stop();
    $('play').hidden = !state.meta;
    $('mode-swipe').setAttribute('aria-pressed', mode === 'swipe');
    $('mode-change').setAttribute('aria-pressed', mode === 'change');
    wrap.classList.toggle('hidden-swipe', mode !== 'swipe' || !state.meta);
    $('opacity-row').hidden = mode !== 'change' || !state.meta;
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
    if (DEMO) q.set('demo', '1');
    history.replaceState(null, '', '?' + q.toString());
  }

  function renderPolChips() {
    const box = $('pol');
    box.replaceChildren(...state.site.polarizations.map((p) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('role', 'radio');
      b.setAttribute('aria-checked', p === state.pol);
      b.textContent = polLabel(p);
      b.title = p;
      b.onclick = () => {
        if (p === state.pol) return;
        state.pol = p;
        renderPolChips();
        loadLayer(false).catch(() => showEmpty());
      };
      return b;
    }));
    $('pol-note').textContent = POL_NOTES[polKey(state.pol)] || '';
  }

  function renderScenes(meta) {
    const rows = $('scenes').tBodies[0].rows;
    const vals = [
      [fmtDate(meta.before.date), fmtDate(meta.after.date)],
      [meta.before.collection, meta.after.collection],
      [meta.before.crid, meta.after.crid],
    ];
    vals.forEach((v, i) => { rows[i].cells[1].textContent = v[0]; rows[i].cells[2].textContent = v[1]; });
    $('files').textContent = `${meta.before.file} → ${meta.after.file}`;
  }

  async function loadLayer(fit) {
    const base = `${LAYERS}/${encodeURIComponent(state.site.id)}/${encodeURIComponent(state.pol)}`;
    const meta = await fetch(`${base}/meta.json`, { cache: 'no-cache' }).then((r) => {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    });
    state.meta = meta;
    $('site-title').textContent = state.site.name;
    $('question').textContent = state.site.question || '';
    $('question').hidden = !state.site.question;
    $('empty').hidden = true;
    document.body.classList.remove('is-empty');
    const b = meta.bounds_wgs84;
    const bounds = [[b.south, b.west], [b.north, b.east]];
    for (const k of Object.keys(overlays)) { if (overlays[k]) overlays[k].remove(); }
    overlays.before = L.imageOverlay(`${base}/before.png`, bounds, { pane: 'before', alt: `Radar, ${meta.before.date}` });
    overlays.after = L.imageOverlay(`${base}/after.png`, bounds, { pane: 'after', alt: `Radar, ${meta.after.date}` });
    overlays.change = L.imageOverlay(`${base}/change.png`, bounds, { pane: 'change', alt: 'Radar echo change', opacity: $('opacity').value / 100 });
    if (fit) map.fitBounds(bounds, { padding: [24, 24] });

    $('date-left').textContent = fmtDate(meta.before.date);
    $('date-right').textContent = fmtDate(meta.after.date);
    // Launch HUD: milestones, T+ days, gauges
    $('ms-before').textContent = fmtDate(meta.before.date);
    $('ms-after').textContent = fmtDate(meta.after.date);
    const days = Math.round((Date.parse(meta.after.date) - Date.parse(meta.before.date)) / 864e5);
    $('hud-days').textContent = String(days).padStart(3, '0');
    $('hud-meta').textContent = ` · ${polLabel(meta.polarization)} · ${meta.after.collection} ${meta.after.crid}`;
    for (const [id, v] of [['g-dec', meta.stats.pct_decrease], ['g-inc', meta.stats.pct_increase]]) {
      $(id).textContent = v.toFixed(1);
      $(id + '-arc').setAttribute('stroke-dasharray', `${Math.min(100, Math.max(0, v))} 100`);
    }
    renderScenes(meta);
    markTimeline(meta);

    const pr = meta.processing;
    const filt = pr.speckle_filter === 'none' ? 'none'
      : `${pr.speckle_filter === 'lee' ? 'Lee' : 'boxcar'} ${pr.window_px}×${pr.window_px} px (≈${pr.window_m} m)` + (pr.enl ? `, ENL ${pr.enl}` : '');
    const spec = $('processing');
    spec.replaceChildren();
    for (const [k, v] of [['channel', meta.polarization], ['speckle', filt], ['pixel', `${pr.web_pixel_m} m`], ['change', '10·log10(after/before)']]) {
      const dt = document.createElement('dt'); dt.textContent = k;
      const dd = document.createElement('dd'); dd.textContent = v;
      spec.append(dt, dd);
    }
    const s = meta.stats;
    $('stats').hidden = false;
    $('thr').textContent = s.threshold_db;
    renderCompare().catch(() => {});
    const lim = meta.display.change_limit_db;
    $('leg-min').textContent = '−' + lim.toFixed(1) + ' dB';
    $('leg-max').textContent = '+' + lim.toFixed(1) + ' dB';
    setMode(state.mode);
    hint();
  }

  // Mission panel: HH vs HV side by side, active channel highlighted
  const metaCache = {};
  function getMeta(site, pol) {
    const url = `${LAYERS}/${encodeURIComponent(site)}/${encodeURIComponent(pol)}/meta.json`;
    if (!metaCache[url]) {
      metaCache[url] = fetch(url, { cache: 'no-cache' }).then((r) => (r.ok ? r.json() : Promise.reject(r.status)));
    }
    return metaCache[url];
  }
  async function renderCompare() {
    const tbl = $('cmp');
    const pols = state.site.polarizations;
    const metas = await Promise.all(pols.map((p) => getMeta(state.site.id, p).catch(() => null)));
    const signed = (v) => (v > 0 ? '+' : '') + v.toFixed(2) + ' dB';
    pols.forEach((p, i) => {
      const m = metas[i];
      if (!m) return;
      const cell = (k) => tbl.querySelector(`tr[data-k="${k}"] td[data-pol="${p}"]`);
      if (cell('inc')) cell('inc').textContent = m.stats.pct_increase.toFixed(1) + '%';
      if (cell('dec')) cell('dec').textContent = m.stats.pct_decrease.toFixed(1) + '%';
      if (cell('med')) cell('med').textContent = signed(m.stats.median_change_db);
    });
    tbl.querySelectorAll('[data-pol]').forEach((el) => el.classList.toggle('on', el.dataset.pol === state.pol));
  }

  function showEmpty() {
    $('empty').hidden = false;
    document.body.classList.add('is-empty');
    wrap.classList.add('hidden-swipe');
    for (const id of ['site', 'mode-swipe', 'mode-change']) $(id).disabled = true;
  }

  // ---- Wiring -------------------------------------------------------------------
  $('mode-swipe').onclick = () => setMode('swipe');
  $('mode-change').onclick = () => setMode('change');
  $('opacity').oninput = (e) => overlays.change && overlays.change.setOpacity(e.target.value / 100);
  $('site').onchange = (e) => {
    state.site = state.index.sites.find((s) => s.id === e.target.value);
    if (!state.site.polarizations.includes(state.pol)) state.pol = state.site.polarizations[0];
    renderPolChips();
    loadLayer(true).catch(() => showEmpty());
  };

  document.querySelectorAll('a[href="#how"]').forEach((a) => a.addEventListener('click', () => { $('how').open = true; }));
  // Tall desktop screens have room: open "How to read it" by default.
  if (innerHeight >= 900 && innerWidth > 720) $('how').open = true;
  buildTimeline();
  fetch(`${LAYERS}/index.json`, { cache: 'no-cache' })
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((idx) => {
      if (!idx.sites || !idx.sites.length) return showEmpty();
      state.index = idx;
      $('site').replaceChildren(...idx.sites.map((s) => new Option(s.name, s.id)));
      state.site = idx.sites.find((s) => s.id === params.get('site')) || idx.sites[0];
      $('site').value = state.site.id;
      const wanted = params.get('pol');
      state.pol = state.site.polarizations.includes(wanted) ? wanted : state.site.polarizations[0];
      renderPolChips();
      return loadLayer(true);
    })
    .catch(() => showEmpty());

  setMode(state.mode);
})();
