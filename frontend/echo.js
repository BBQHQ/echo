// Echo — Frontend

const API = '';

// ─── DOM ────────────────────────────────────────────
const recordBtn = document.getElementById('recordBtn');
const micIcon = document.getElementById('micIcon');
const stopIcon = document.getElementById('stopIcon');
const recordLabel = document.getElementById('recordLabel');
const timer = document.getElementById('timer');
const waveform = document.getElementById('waveform');
const waveCanvas = document.getElementById('waveCanvas');
const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const browseBtn = document.getElementById('browseBtn');
const processing = document.getElementById('processing');
const resultCard = document.getElementById('resultCard');
const resultText = document.getElementById('resultText');
const duration = document.getElementById('duration');
const copyBtn = document.getElementById('copyBtn');
const error = document.getElementById('error');
const errorText = document.getElementById('errorText');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const modelBtnLabel = document.getElementById('modelBtnLabel');
const setupBanner = document.getElementById('setupBanner');

// State
let mediaRecorder = null;
let audioChunks = [];
let timerInterval = null;
let warmupHeartbeat = null;
let startTime = 0;
let audioContext = null;
let analyser = null;
let animFrame = null;

// ─── Whisper status ─────────────────────────────────
function shortModel(filename) {
  return (filename || '').replace(/^ggml-/, '').replace(/\.bin$/, '');
}

async function checkWhisperStatus() {
  try {
    const resp = await fetch(`${API}/voice/status`);
    const data = await resp.json();
    if (data.model) modelBtnLabel.textContent = shortModel(data.model);

    if (data.engine_installed === false) {
      statusDot.className = 'status-dot error';
      statusText.textContent = 'Engine not installed';
      showSetup('Whisper engine not installed', 'Echo needs the whisper.cpp engine to transcribe. Downloading a model isn’t enough — run <code>scripts/install_whisper</code> (or drop a <code>whisper-server</code> build into the <code>whisper/</code> folder), then reload.');
    } else if (data.model_present === false) {
      statusDot.className = 'status-dot error';
      statusText.textContent = 'No model';
      showSetup('No transcription model', 'The active model isn’t downloaded yet. Open <strong>Model</strong> (top-right) and download one.');
    } else if (data.running) {
      statusDot.className = 'status-dot loaded'; statusText.textContent = 'Whisper running'; hideSetup();
    } else {
      statusDot.className = 'status-dot unloaded'; statusText.textContent = 'Whisper standby'; hideSetup();
    }
  } catch {
    statusDot.className = 'status-dot error';
    statusText.textContent = 'Offline';
  }
}

function showSetup(title, html) {
  setupBanner.innerHTML = `<strong>${title}</strong><span>${html}</span>`;
  setupBanner.style.display = 'block';
}
function hideSetup() { setupBanner.style.display = 'none'; }

function fmtTime(s) {
  const m = Math.floor(s / 60), sec = s % 60;
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
}

// ═══════════════════════════════════════════════════
// RECORD
// ═══════════════════════════════════════════════════
recordBtn.addEventListener('click', async () => {
  if (mediaRecorder && mediaRecorder.state === 'recording') stopRecording();
  else await startRecording();
});

async function startRecording() {
  try {
    fetch(`${API}/voice/warmup`, { method: 'POST' }).catch(() => {});
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      showError('Microphone requires HTTPS. Access Echo via https:// or http://localhost.');
      return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream, { mimeType: getSupportedMime() });
    audioChunks = [];

    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      stopVisualizer();
      if (pttAbort) { pttAbort = false; return; }
      const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
      await sendAudio(blob, 'recording.webm');
    };

    mediaRecorder.start(250);
    startTime = Date.now();
    // Heartbeat: keep whisper warm during long recordings (TTL is 5 min)
    warmupHeartbeat = setInterval(() => {
      fetch(`${API}/voice/warmup`, { method: 'POST' }).catch(() => {});
    }, 60000);
    recordBtn.classList.add('recording');
    micIcon.style.display = 'none'; stopIcon.style.display = 'block';
    recordLabel.textContent = 'Recording… click to stop';
    timer.style.display = 'block';
    hideResults();
    timerInterval = setInterval(() => {
      timer.textContent = fmtTime(Math.floor((Date.now() - startTime) / 1000));
    }, 250);
    startVisualizer(stream);
  } catch (err) { showError(`Microphone access denied: ${err.message}`); }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    clearInterval(timerInterval);
    if (warmupHeartbeat) { clearInterval(warmupHeartbeat); warmupHeartbeat = null; }
    recordBtn.classList.remove('recording');
    micIcon.style.display = 'block'; stopIcon.style.display = 'none';
    recordLabel.textContent = 'Click to record';
    timer.style.display = 'none'; waveform.style.display = 'none';
  }
}

// ─── Push-to-talk (hold backtick) ──────────────────
const PTT_KEY = '`';
const PTT_MIN_HOLD_MS = 200;
let pttActive = false;
let pttStartTime = 0;
let pttAbort = false;

document.addEventListener('keydown', async (e) => {
  if (e.key === 'Escape' && pttActive) {
    pttAbort = true; pttActive = false; stopRecording(); return;
  }
  if (e.key !== PTT_KEY || e.repeat || pttActive) return;
  const t = e.target;
  if (t.matches && t.matches('input, textarea, [contenteditable="true"]')) return;
  e.preventDefault();
  pttActive = true; pttAbort = false; pttStartTime = Date.now();
  await startRecording();
});

document.addEventListener('keyup', (e) => {
  if (e.key !== PTT_KEY || !pttActive) return;
  pttActive = false;
  if (Date.now() - pttStartTime < PTT_MIN_HOLD_MS) pttAbort = true;
  stopRecording();
});

function getSupportedMime() {
  for (const t of ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg', 'audio/mp4'])
    if (MediaRecorder.isTypeSupported(t)) return t;
  return 'audio/webm';
}

function startVisualizer(stream) {
  audioContext = new AudioContext();
  analyser = audioContext.createAnalyser(); analyser.fftSize = 256;
  audioContext.createMediaStreamSource(stream).connect(analyser);
  waveform.style.display = 'block';
  const ctx = waveCanvas.getContext('2d');
  const buf = new Uint8Array(analyser.frequencyBinCount);
  (function draw() {
    animFrame = requestAnimationFrame(draw);
    analyser.getByteTimeDomainData(buf);
    ctx.fillStyle = '#3d3d36'; ctx.fillRect(0, 0, waveCanvas.width, waveCanvas.height);
    ctx.lineWidth = 2; ctx.strokeStyle = '#36f1cd'; ctx.beginPath();
    const sw = waveCanvas.width / buf.length;
    for (let i = 0, x = 0; i < buf.length; i++, x += sw) {
      const y = (buf[i] / 128) * waveCanvas.height / 2;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.lineTo(waveCanvas.width, waveCanvas.height / 2); ctx.stroke();
  })();
}

function stopVisualizer() {
  if (animFrame) cancelAnimationFrame(animFrame);
  if (audioContext) audioContext.close();
  audioContext = analyser = null;
}

// ═══════════════════════════════════════════════════
// UPLOAD
// ═══════════════════════════════════════════════════
browseBtn.addEventListener('click', e => { e.stopPropagation(); fileInput.click(); });
uploadZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', e => {
  if (e.target.files.length) { sendAudio(e.target.files[0], e.target.files[0].name); fileInput.value = ''; }
});
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('dragover'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault(); uploadZone.classList.remove('dragover');
  if (e.dataTransfer.files.length) sendAudio(e.dataTransfer.files[0], e.dataTransfer.files[0].name);
});

async function sendAudio(blob, filename) {
  hideResults(); processing.style.display = 'flex';
  const fd = new FormData(); fd.append('file', blob, filename);
  try {
    const resp = await fetch(`${API}/voice/transcribe`, { method: 'POST', body: fd });
    const data = await resp.json();
    processing.style.display = 'none';
    if (data.error) showError(data.error);
    else { showResult(data.text, data.duration_ms); loadRecentVoice(); }
  } catch (err) {
    processing.style.display = 'none';
    showError(`Failed to connect: ${err.message}`);
  }
  checkWhisperStatus();
}

function showResult(text, ms) {
  resultText.textContent = text;
  duration.textContent = ms ? `${(ms / 1000).toFixed(1)}s` : '';
  resultCard.classList.remove('hidden');
  error.style.display = 'none';
}
function showError(msg) {
  errorText.textContent = msg;
  error.style.display = 'block';
  resultCard.classList.add('hidden');
}
function hideResults() {
  resultCard.classList.add('hidden');
  error.style.display = 'none';
}

copyBtn.addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(resultText.textContent); } catch { document.execCommand('copy'); }
  copyBtn.classList.add('copied'); setTimeout(() => copyBtn.classList.remove('copied'), 1500);
});

// ═══════════════════════════════════════════════════
// HISTORY
// ═══════════════════════════════════════════════════
const voiceRecordView = document.getElementById('voiceRecordView');
const voiceHistoryView = document.getElementById('voiceHistoryView');
const voiceRecentList = document.getElementById('voiceRecentList');
const voiceHistoryList = document.getElementById('voiceHistoryList');
const voiceHistoryCount = document.getElementById('voiceHistoryCount');

function showVoiceTab(tab) {
  document.querySelectorAll('#voiceTabs .board-tab').forEach(t => t.classList.remove('active'));
  if (tab === 'record') {
    document.querySelector('#voiceTabs .board-tab:first-child').classList.add('active');
    voiceRecordView.style.display = '';
    voiceHistoryView.style.display = 'none';
  } else {
    document.querySelector('#voiceTabs .board-tab:last-child').classList.add('active');
    voiceRecordView.style.display = 'none';
    voiceHistoryView.style.display = '';
    loadFullVoiceHistory();
  }
}

async function loadRecentVoice() {
  try {
    const resp = await fetch(`${API}/voice/history?limit=5&offset=0`);
    const data = await resp.json();
    const items = data.items || [];
    voiceRecentList.innerHTML = '';
    if (items.length === 0) {
      voiceRecentList.innerHTML = '<p class="empty">No transcriptions yet.</p>';
      return;
    }
    items.forEach(item => voiceRecentList.appendChild(buildVoiceLogItem(item)));
  } catch (err) {
    console.error('Failed to load recent voice:', err);
  }
}

async function loadFullVoiceHistory() {
  try {
    const resp = await fetch(`${API}/voice/history?limit=200&offset=0`);
    const data = await resp.json();
    const items = data.items || [];
    const total = data.total || 0;

    if (total > 0) { voiceHistoryCount.textContent = total; voiceHistoryCount.style.display = ''; }
    else { voiceHistoryCount.style.display = 'none'; }

    voiceHistoryList.innerHTML = '';
    if (items.length === 0) {
      voiceHistoryList.innerHTML = '<p class="empty">No transcriptions yet.</p>';
      return;
    }

    let lastDay = '';
    items.forEach(item => {
      const dt = new Date(item.created_at);
      const dayKey = dt.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' });
      if (dayKey !== lastDay) {
        const dayEl = document.createElement('div');
        dayEl.className = 'voice-log-day';
        dayEl.textContent = dayKey;
        voiceHistoryList.appendChild(dayEl);
        lastDay = dayKey;
      }
      voiceHistoryList.appendChild(buildVoiceLogItem(item));
    });
  } catch (err) {
    console.error('Failed to load voice history:', err);
  }
}

function buildVoiceLogItem(item) {
  const el = document.createElement('div');
  el.className = 'voice-log-item';
  el.setAttribute('data-id', item.id);

  const dt = new Date(item.created_at);
  const timeStr = dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  const durStr = item.duration_ms ? `${(item.duration_ms / 1000).toFixed(1)}s` : '';
  const srcLabel = item.source === 'upload' ? 'upload' : 'mic';

  el.innerHTML = `
    <svg class="voice-log-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
      <line x1="12" y1="19" x2="12" y2="23"/>
    </svg>
    <div class="voice-log-body">
      <div class="voice-log-preview">${esc(item.text)}</div>
      <div class="voice-log-meta">
        <span class="voice-log-time">${timeStr}</span>
        ${durStr ? `<span class="voice-log-dur">${durStr}</span>` : ''}
        <span class="voice-log-src">${srcLabel}</span>
      </div>
      <div class="voice-log-actions">
        <button class="btn-secondary" onclick="copyVoiceLog(event, ${item.id})">Copy</button>
        <button class="btn-secondary btn-danger" onclick="deleteVoiceLog(event, ${item.id})">Delete</button>
      </div>
    </div>
    <button class="btn-text voice-log-delete" onclick="deleteVoiceLog(event, ${item.id})" title="Delete">&times;</button>
  `;

  el.addEventListener('click', (e) => {
    if (e.target.closest('button')) return;
    el.classList.toggle('expanded');
  });

  return el;
}

async function copyVoiceLog(e, id) {
  e.stopPropagation();
  const item = e.target.closest('.voice-log-item');
  const text = item.querySelector('.voice-log-preview').textContent;
  try { await navigator.clipboard.writeText(text); } catch { document.execCommand('copy'); }
  const btn = e.target;
  btn.textContent = 'Copied!';
  setTimeout(() => { btn.textContent = 'Copy'; }, 1200);
}

async function deleteVoiceLog(e, id) {
  e.stopPropagation();
  await fetch(`${API}/voice/history/${id}`, { method: 'DELETE' });
  const item = e.target.closest('.voice-log-item');
  item.remove();
  loadRecentVoice();
}

// ═══════════════════════════════════════════════════
// MODEL MANAGER
// ═══════════════════════════════════════════════════
const modelOverlay = document.getElementById('modelOverlay');
const modelList = document.getElementById('modelList');
const customModelInput = document.getElementById('customModelInput');
let modelPoll = null;

document.getElementById('modelManagerBtn').addEventListener('click', openModelManager);
document.getElementById('modelCloseBtn').addEventListener('click', closeModelManager);
modelOverlay.addEventListener('click', e => { if (e.target === modelOverlay) closeModelManager(); });
document.getElementById('customDownloadBtn').addEventListener('click', () => {
  const name = customModelInput.value.trim();
  if (name) downloadModel(name);
});

const engineSection = document.getElementById('engineSection');
let enginePoll = null;

function openModelManager() {
  modelOverlay.style.display = 'flex';
  loadEngine();
  loadModels();
}
function closeModelManager() {
  modelOverlay.style.display = 'none';
  if (modelPoll) { clearInterval(modelPoll); modelPoll = null; }
  if (enginePoll) { clearInterval(enginePoll); enginePoll = null; }
}

// ─── Engine (CPU / NVIDIA CUDA) ─────────────────────
const NV_CHIP = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#76b900" stroke-width="2" stroke-linecap="round">
  <rect x="6" y="6" width="12" height="12" rx="1.5"/>
  <rect x="9.5" y="9.5" width="5" height="5" fill="#76b900" stroke="none"/>
  <line x1="9" y1="3" x2="9" y2="6"/><line x1="15" y1="3" x2="15" y2="6"/>
  <line x1="9" y1="18" x2="9" y2="21"/><line x1="15" y1="18" x2="15" y2="21"/>
  <line x1="3" y1="9" x2="6" y2="9"/><line x1="3" y1="15" x2="6" y2="15"/>
  <line x1="18" y1="9" x2="21" y2="9"/><line x1="18" y1="15" x2="21" y2="15"/>
</svg>`;
const NV_BADGE = `<span class="nv-badge">${NV_CHIP}<b>NVIDIA</b></span>`;

async function loadEngine() {
  try {
    const resp = await fetch(`${API}/engine`);
    const data = await resp.json();
    renderEngine(data);
    if (data.installing && !enginePoll) {
      enginePoll = setInterval(loadEngine, 1000);
    } else if (!data.installing && enginePoll) {
      clearInterval(enginePoll); enginePoll = null;
      checkWhisperStatus();
    }
  } catch {
    engineSection.innerHTML = '';
  }
}

function renderEngine(data) {
  const inst = data.installing;
  if (inst) {
    let inner;
    if (inst.phase === 'installing') {
      inner = `<div class="eng-progress"><div class="eng-bar" style="width:100%"></div><span>Installing…</span></div>`;
    } else if (inst.phase === 'error') {
      inner = `<div class="eng-progress error"><div class="eng-bar"></div><span>Failed</span></div>`;
    } else {
      const pct = inst.total ? Math.round((inst.received / inst.total) * 100) : 0;
      const mb = inst.total ? ` ${(inst.received/1048576).toFixed(0)}/${(inst.total/1048576).toFixed(0)} MB` : '';
      inner = `<div class="eng-progress"><div class="eng-bar" style="width:${pct}%"></div><span>${pct}%${mb}</span></div>`;
    }
    engineSection.innerHTML = `<div class="engine-card busy"><div class="engine-head">${NV_BADGE}<span class="engine-title">Installing ${inst.variant === 'cuda' ? 'GPU engine' : 'CPU engine'}…</span></div>${inner}</div>`;
    return;
  }

  const gpu = data.gpu || {};
  const onCuda = data.variant === 'cuda';
  let title, sub, action;

  if (onCuda) {
    title = `<span class="engine-title on">GPU acceleration <span class="on-dot">ON</span></span>`;
    sub = gpu.name ? `<div class="engine-sub">${esc(gpu.name)}</div>` : '';
    action = data.supported ? `<button class="btn-text" onclick="installEngine('cpu')">Switch to CPU</button>` : '';
  } else if (gpu.available) {
    title = `<span class="engine-title">${esc(gpu.name || 'NVIDIA GPU')} detected</span>`;
    sub = `<div class="engine-sub">Engine: ${data.variant === 'cpu' ? 'CPU' : data.variant === 'none' ? 'not installed' : 'CPU/unknown'} · GPU build is ~280 MB, one-time</div>`;
    action = data.supported
      ? `<button class="btn-nv" onclick="installEngine('cuda')">⚡ Enable GPU acceleration</button>`
      : `<span class="engine-note">GPU engine install is Windows-only.</span>`;
  } else {
    title = `<span class="engine-title muted">No NVIDIA GPU detected</span>`;
    sub = `<div class="engine-sub">Using CPU.</div>`;
    action = '';
  }

  engineSection.innerHTML = `<div class="engine-card${onCuda ? ' on' : ''}">
    <div class="engine-head">${NV_BADGE}${title}</div>
    ${sub}
    <div class="engine-action">${action}</div>
  </div>`;
}

async function installEngine(variant) {
  try {
    const resp = await fetch(`${API}/engine/install`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ variant }),
    });
    if (!resp.ok) { const err = await resp.json(); alert(err.detail || 'Install failed'); return; }
    loadEngine();
  } catch (err) { alert(`Install failed: ${err.message}`); }
}

async function loadModels() {
  try {
    const resp = await fetch(`${API}/models`);
    const data = await resp.json();
    renderModels(data);
    // Poll while a download is running so the progress bar advances.
    if (data.downloading && !modelPoll) {
      modelPoll = setInterval(loadModels, 1000);
    } else if (!data.downloading && modelPoll) {
      clearInterval(modelPoll); modelPoll = null;
      checkWhisperStatus();
    }
  } catch (err) {
    modelList.innerHTML = '<p class="empty">Could not load models.</p>';
  }
}

function renderModels(data) {
  const downloaded = new Set(data.downloaded || []);
  const dl = data.downloading;
  const rows = [...data.catalog];
  // Include any downloaded custom models not in the catalog.
  (data.downloaded || []).forEach(fn => {
    if (!rows.some(r => r.filename === fn)) {
      rows.push({ tier: 'Custom', filename: fn, size: '', ram: '', language: '', note: '' });
    }
  });

  modelList.innerHTML = '';
  rows.forEach(m => {
    const isActive = m.filename === data.active;
    const isDownloaded = downloaded.has(m.filename);
    const isDownloading = dl && dl.filename === m.filename;

    const row = document.createElement('div');
    row.className = 'model-row' + (isActive ? ' active' : '');

    let action = '';
    if (isDownloading) {
      const pct = dl.total ? Math.round((dl.received / dl.total) * 100) : 0;
      const err = dl.error ? ` error` : '';
      action = `<div class="dl-progress${err}"><div class="dl-bar" style="width:${pct}%"></div><span>${dl.error ? 'Failed' : pct + '%'}</span></div>`;
    } else if (isActive) {
      action = `<span class="badge badge-active">Active</span>`;
    } else if (isDownloaded) {
      action = `<button class="btn-primary" onclick="selectModel('${m.filename}')">Use</button>
                <button class="btn-text btn-danger" onclick="removeModel('${m.filename}')" title="Delete file">&times;</button>`;
    } else {
      action = `<button class="btn-secondary" onclick="downloadModel('${m.filename}')" ${dl ? 'disabled' : ''}>Download</button>`;
    }

    const meta = [m.size, m.ram && `${m.ram} RAM`, m.language].filter(Boolean).join(' · ');
    row.innerHTML = `
      <div class="model-info">
        <div class="model-tier">${esc(m.tier)} ${isDownloaded && !isActive ? '<span class="dot-ok">✓</span>' : ''}</div>
        <div class="model-file">${esc(m.filename)}</div>
        ${meta ? `<div class="model-meta">${esc(meta)}</div>` : ''}
        ${m.note ? `<div class="model-note">${esc(m.note)}</div>` : ''}
      </div>
      <div class="model-action">${action}</div>
    `;
    modelList.appendChild(row);
  });
}

async function downloadModel(filename) {
  try {
    const resp = await fetch(`${API}/models/download`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      alert(err.detail || 'Download failed');
      return;
    }
    customModelInput.value = '';
    loadModels();
  } catch (err) { alert(`Download failed: ${err.message}`); }
}

async function selectModel(filename) {
  try {
    const resp = await fetch(`${API}/models/select`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename }),
    });
    if (!resp.ok) { const err = await resp.json(); alert(err.detail || 'Could not switch model'); return; }
    loadModels();
    checkWhisperStatus();
  } catch (err) { alert(`Could not switch model: ${err.message}`); }
}

async function removeModel(filename) {
  if (!confirm(`Delete ${filename}? You can re-download it later.`)) return;
  try {
    const resp = await fetch(`${API}/models/${encodeURIComponent(filename)}`, { method: 'DELETE' });
    if (!resp.ok) { const err = await resp.json(); alert(err.detail || 'Delete failed'); return; }
    loadModels();
  } catch (err) { alert(`Delete failed: ${err.message}`); }
}

// ─── Helpers ────────────────────────────────────────
function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

// ─── Init ───────────────────────────────────────────
checkWhisperStatus();
setInterval(checkWhisperStatus, 10000);
loadRecentVoice();
