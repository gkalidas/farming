'use strict';

const $ = id => document.getElementById(id);

// ── status check ────────────────────────────────────────────────────────────
async function checkStatus() {
  try {
    const d = await fetch('/api/status').then(r => r.json());
    $('dot-ollama').className  = 'dot ' + (d.ollama  ? 'ok' : 'err');
    $('dot-weather').className = 'dot ' + (d.weather ? 'ok' : 'err');
  } catch (_) {
    $('dot-ollama').className = 'dot err';
  }
}
checkStatus();

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
  previewImg.src    = url;
  previewImg.hidden = false;
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

  showOverlay('Sending to vision model…');

  const fd = new FormData();
  fd.append('crop',     crop);
  fd.append('location', location);
  fd.append('image',    file);

  try {
    const res  = await fetch('/api/analyse', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Server error');
    showResult(data, crop);
    loadHistory();
  } catch (err) {
    hideOverlay();
    alert('Analysis failed: ' + err.message);
  }
});

// ── render result ────────────────────────────────────────────────────────────
function showResult(data, crop) {
  hideOverlay();

  const r = data.result || {};

  $('r-condition').textContent = r.condition  || 'Unknown condition';
  $('r-crop').textContent      = crop;

  const sev    = (r.severity || 'unknown').toLowerCase();
  const badge  = $('r-severity');
  badge.textContent  = sev;
  badge.className    = 'severity-badge sev-' + (
    ['healthy','mild','moderate','severe'].includes(sev) ? sev : 'mild'
  );

  renderList($('r-actions'), r.immediate_actions || []);
  renderList($('r-avoid'),   r.do_not            || []);
  renderList($('r-watch'),   r.watch_for         || []);

  const weatherBlock = $('r-weather-block');
  if (r.weather_note) {
    $('r-weather').textContent = r.weather_note;
    weatherBlock.hidden = false;
  } else {
    weatherBlock.hidden = true;
  }

  $('r-timeline').textContent = r.timeline || '—';

  // module pills
  const pillsEl = $('r-modules');
  pillsEl.innerHTML = '';
  (data.modules || []).forEach(m => {
    const p = document.createElement('span');
    p.className   = 'pill ' + (m.available ? 'pill-ok' : 'pill-off');
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
    if (!rows.length) { list.innerHTML = '<div style="color:var(--dim);font-size:13px;padding:12px 0">No analyses yet.</div>'; return; }
    list.innerHTML = rows.map(row => {
      const r    = row.result || {};
      const date = new Date(row.created_at).toLocaleDateString('en-IN', { day:'2-digit', month:'short' });
      return `
        <div class="history-item">
          <div>
            <div class="history-crop">${row.crop}</div>
            <div class="history-cond">${r.condition || '—'}</div>
          </div>
          <div class="history-date">${date}</div>
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

// ── overlay helpers ───────────────────────────────────────────────────────────
function showOverlay(msg) {
  $('overlay-text').textContent = msg || 'Analysing…';
  $('overlay').hidden = false;
}
function hideOverlay() {
  $('overlay').hidden = true;
}
