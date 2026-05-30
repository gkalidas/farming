'use strict';

const $ = id => document.getElementById(id);

// ── status check ────────────────────────────────────────────────────────────
async function checkStatus() {
  try {
    const d = await fetch('/api/status').then(r => r.json());
    $('dot-ollama').className  = 'dot ' + (d.ollama  ? 'ok' : 'err');
    $('dot-weather').className = 'dot ok'; // weather is always tried
  } catch (_) {
    $('dot-ollama').className = 'dot err';
  }
}
checkStatus();

// ── plots: load into selector ────────────────────────────────────────────────
async function loadPlotSelector() {
  try {
    const plots = await fetch('/api/plots').then(r => r.json());
    const sel   = $('plot-select');
    // keep the "— no plot —" option, rebuild the rest
    while (sel.options.length > 1) sel.remove(1);
    plots.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.crop} — ${p.location} (planted ${p.planted_at})`;
      sel.appendChild(opt);
    });
  } catch (_) {}
}
loadPlotSelector();

// ── file upload / preview ────────────────────────────────────────────────────
const fileInput   = $('file-input');
const uploadZone  = $('upload-zone');
const previewWrap = $('preview-wrap');
const previewImg  = $('preview-img');
const analyseBtn  = $('analyse-btn');

uploadZone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', () => {
  const file = fileInput.files[0];
  if (!file) return;
  const url = URL.createObjectURL(file);
  previewImg.src     = url;
  previewImg.hidden  = false;
  previewWrap.hidden = true;
  uploadZone.classList.add('has-image');
  analyseBtn.disabled = false;
});

// drag-and-drop on desktop
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('has-image'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('has-image'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  const file = e.dataTransfer.files[0];
  if (!file || !file.type.startsWith('image/')) return;
  const dt = new DataTransfer();
  dt.items.add(file);
  fileInput.files = dt.files;
  fileInput.dispatchEvent(new Event('change'));
});

// ── analyse ──────────────────────────────────────────────────────────────────
analyseBtn.addEventListener('click', async () => {
  const file = fileInput.files[0];
  if (!file) return;

  const crop     = $('crop-select').value;
  const location = $('location-input').value.trim();
  const plotId   = $('plot-select').value;

  showOverlay('Sending photo…');

  try {
    console.log('[farming] step 1: reading file', file.name, file.size, file.type);

    // Read file into memory first — catches iCloud/network-drive stalls
    const bytes = await file.arrayBuffer();
    const blob  = new Blob([bytes], { type: file.type || 'image/jpeg' });
    console.log('[farming] step 2: file read ok, bytes=', bytes.byteLength);

    const fd = new FormData();
    fd.append('crop',     crop);
    fd.append('location', location);
    fd.append('image',    blob, file.name || 'photo.jpg');
    if (plotId) fd.append('plot_id', plotId);

    showOverlay('Running disease detection…');
    console.log('[farming] step 3: sending fetch');

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 180_000); // 3-min hard timeout

    let res;
    try {
      res = await fetch('/api/analyse', { method: 'POST', body: fd, signal: ctrl.signal });
    } finally {
      clearTimeout(timer);
    }

    console.log('[farming] step 4: response received, status=', res.status);
    showOverlay('Generating advisory…');
    const data = await res.json();
    if (!res.ok) throw new Error((data.detail?.[0]?.msg || data.detail) || 'Server error');
    showResult(data, crop);
    loadHistory();
  } catch (err) {
    console.error('[farming] error:', err);
    const msg = err.name === 'AbortError' ? 'Timed out after 3 minutes.' : (err.message || String(err));
    showOverlay('Error: ' + msg);
    setTimeout(hideOverlay, 4000);
  }
});

// ── render result ────────────────────────────────────────────────────────────
function showResult(data, crop) {
  hideOverlay();

  const r = data.result || {};

  // uncertainty banner
  const isUncertain = (r.condition || '').toLowerCase() === 'unrecognised' ||
                      (data.visual_diagnosis || '').toLowerCase().includes('unrecognised');
  $('r-uncertainty').hidden = !isUncertain;

  $('r-condition').textContent = r.condition  || 'Unknown condition';
  $('r-crop').textContent      = crop;

  const sev   = (r.severity || 'unknown').toLowerCase();
  const badge = $('r-severity');
  badge.textContent = sev;
  badge.className   = 'severity-badge sev-' + (
    ['healthy','mild','moderate','severe'].includes(sev) ? sev : 'mild'
  );

  renderList($('r-actions'), r.immediate_actions || []);

  // spray timing
  const sprayBlock = $('r-spray-block');
  if (r.spray_timing) {
    $('r-spray').textContent = r.spray_timing;
    sprayBlock.hidden = false;
  } else {
    sprayBlock.hidden = true;
  }

  renderList($('r-avoid'), r.do_not    || []);
  renderList($('r-watch'), r.watch_for || []);

  // weather note
  const weatherBlock = $('r-weather-block');
  if (r.weather_note) {
    $('r-weather').textContent = r.weather_note;
    weatherBlock.hidden = false;
  } else {
    weatherBlock.hidden = true;
  }

  // soil note
  const soilBlock = $('r-soil-block');
  if (r.soil_note) {
    $('r-soil').textContent = r.soil_note;
    soilBlock.hidden = false;
  } else {
    soilBlock.hidden = true;
  }

  // root note
  const rootBlock = $('r-root-block');
  if (r.root_note) {
    $('r-root').textContent = r.root_note;
    rootBlock.hidden = false;
  } else {
    rootBlock.hidden = true;
  }

  $('r-timeline').textContent = r.timeline || '—';

  // module pills
  const pillsEl = $('r-modules');
  pillsEl.innerHTML = '';
  (data.modules || []).forEach(m => {
    const p = document.createElement('span');
    p.className   = 'pill ' + (m.available ? 'pill-ok' : 'pill-off');
    p.title       = m.summary || '';
    p.textContent = m.module;
    pillsEl.appendChild(p);
  });

  $('upload-card').hidden = true;
  $('result-card').hidden = false;
}

function renderList(el, items) {
  el.innerHTML = items.map(i => `<li>${i}</li>`).join('');
}

// ── new analysis ─────────────────────────────────────────────────────────────
$('new-btn').addEventListener('click', () => {
  fileInput.value      = '';
  previewImg.hidden    = true;
  previewWrap.hidden   = false;
  uploadZone.classList.remove('has-image');
  analyseBtn.disabled  = true;
  $('result-card').hidden = true;
  $('upload-card').hidden = false;
});

// ── history ───────────────────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const rows = await fetch('/api/history').then(r => r.json());
    const list = $('history-list');
    if (!rows.length) {
      list.innerHTML = '<div style="color:var(--dim);font-size:13px;padding:12px 0">No analyses yet.</div>';
      return;
    }
    list.innerHTML = rows.map(row => {
      const r    = row.result || {};
      const date = new Date(row.created_at).toLocaleDateString('en-IN', { day:'2-digit', month:'short' });
      const sev  = (r.severity || '').toLowerCase();
      const sevCls = ['healthy','mild','moderate','severe'].includes(sev) ? 'sev-' + sev : '';
      return `
        <div class="history-item">
          <div>
            <div class="history-crop">${row.crop}</div>
            <div class="history-cond">${r.condition || '—'}</div>
          </div>
          <div style="display:flex;align-items:center;gap:8px">
            ${sev ? `<span class="severity-badge ${sevCls}" style="font-size:10px;padding:2px 8px">${sev}</span>` : ''}
            <div class="history-date">${date}</div>
          </div>
        </div>`;
    }).join('');
  } catch (_) {}
}

$('history-toggle').addEventListener('click', () => {
  const list = $('history-list');
  const open = !list.hidden;
  list.hidden = open;
  $('history-chevron').textContent = open ? '▼' : '▲';
  if (!open) loadHistory();
});

// ── plots section ─────────────────────────────────────────────────────────────
$('plots-toggle').addEventListener('click', () => {
  const body = $('plots-body');
  const open = !body.hidden;
  body.hidden = open;
  $('plots-chevron').textContent = open ? '▼' : '▲';
  if (!open) renderPlots();
});

async function renderPlots() {
  try {
    const plots = await fetch('/api/plots').then(r => r.json());
    const list  = $('plots-list');
    if (!plots.length) {
      list.innerHTML = '<div style="color:var(--dim);font-size:13px;padding:12px 0">No plots registered yet.</div>';
      return;
    }
    list.innerHTML = plots.map(p => `
      <div class="history-item">
        <div>
          <div class="history-crop">${p.crop} — ${p.location}</div>
          <div class="history-cond">Planted ${p.planted_at}${p.notes ? ' · ' + p.notes : ''}</div>
        </div>
        <div class="history-date">#${p.id}</div>
      </div>`).join('');
  } catch (_) {}
}

$('add-plot-btn').addEventListener('click', () => {
  $('plot-form').hidden = false;
  $('add-plot-btn').hidden = true;
});

$('pf-cancel').addEventListener('click', () => {
  $('plot-form').hidden = true;
  $('add-plot-btn').hidden = false;
});

$('pf-submit').addEventListener('click', async () => {
  const crop     = $('pf-crop').value;
  const location = $('pf-location').value.trim();
  if (!location) { alert('Please enter a location'); return; }

  const fd = new FormData();
  fd.append('crop',     crop);
  fd.append('location', location);
  fd.append('notes',    $('pf-notes').value.trim());

  try {
    const res  = await fetch('/api/plots', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Server error');

    // reset form
    $('pf-location').value = '';
    $('pf-notes').value    = '';
    $('plot-form').hidden  = true;
    $('add-plot-btn').hidden = false;

    await renderPlots();
    await loadPlotSelector();
  } catch (err) {
    alert('Failed to register plot: ' + err.message);
  }
});

// ── overlay helpers ───────────────────────────────────────────────────────────
function showOverlay(msg) {
  const text = $('overlay-text');
  text.textContent = msg || 'Analysing…';
  text.style.color = (msg || '').startsWith('Error') ? '#f07070' : '';
  $('overlay').style.display = 'flex';
}
function hideOverlay() {
  $('overlay').style.display = 'none';
  $('overlay-text').style.color = '';
}
