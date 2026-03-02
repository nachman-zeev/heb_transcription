const state = {
  token: localStorage.getItem('hb_token') || '',
  tenantName: '',
  userEmail: '',
  jobs: [],
  selectedJob: null,
  activeWordEl: null,
  period: 'week',
  ws: null,
};

const el = {
  loginView: document.getElementById('loginView'),
  appView: document.getElementById('appView'),
  loginForm: document.getElementById('loginForm'),
  tenantInput: document.getElementById('tenantInput'),
  emailInput: document.getElementById('emailInput'),
  passwordInput: document.getElementById('passwordInput'),
  loginError: document.getElementById('loginError'),
  tenantTitle: document.getElementById('tenantTitle'),
  wsStatus: document.getElementById('wsStatus'),
  refreshBtn: document.getElementById('refreshBtn'),
  logoutBtn: document.getElementById('logoutBtn'),
  usageText: document.getElementById('usageText'),
  usageSub: document.getElementById('usageSub'),
  queueText: document.getElementById('queueText'),
  queueSub: document.getElementById('queueSub'),
  activityChart: document.getElementById('activityChart'),
  dateFrom: document.getElementById('dateFrom'),
  dateTo: document.getElementById('dateTo'),
  filterBtn: document.getElementById('filterBtn'),
  clearFilterBtn: document.getElementById('clearFilterBtn'),
  jobsList: document.getElementById('jobsList'),
  selectedJobTitle: document.getElementById('selectedJobTitle'),
  tabTranscript: document.getElementById('tabTranscript'),
  tabDetails: document.getElementById('tabDetails'),
  transcriptView: document.getElementById('transcriptView'),
  detailsView: document.getElementById('detailsView'),
  audioPlayer: document.getElementById('audioPlayer'),
  transcriptContainer: document.getElementById('transcriptContainer'),
  wordSearch: document.getElementById('wordSearch'),
  detailsGrid: document.getElementById('detailsGrid'),
};

async function api(path, options = {}) {
  const headers = options.headers || {};
  headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  if (state.token) {
    headers['Authorization'] = `Bearer ${state.token}`;
  }

  const resp = await fetch(path, { ...options, headers });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      detail = body.detail || JSON.stringify(body);
    } catch (_) {}
    throw new Error(detail);
  }

  const ctype = resp.headers.get('content-type') || '';
  if (ctype.includes('application/json')) {
    return resp.json();
  }
  return resp;
}

function fmtDate(value) {
  if (!value) return '--';
  try {
    return new Date(value).toLocaleString('he-IL');
  } catch (_) {
    return value;
  }
}

function fmtDurationSec(sec) {
  if (sec == null) return '--';
  const v = Math.max(0, Math.floor(sec));
  const h = Math.floor(v / 3600);
  const m = Math.floor((v % 3600) / 60);
  const s = v % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

async function login(evt) {
  evt.preventDefault();
  el.loginError.textContent = '';
  try {
    const tenant_name = el.tenantInput.value.trim();
    const email = el.emailInput.value.trim();
    const password = el.passwordInput.value;
    const out = await api('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ tenant_name, email, password }),
    });
    state.token = out.access_token;
    localStorage.setItem('hb_token', state.token);
    await enterApp();
  } catch (err) {
    el.loginError.textContent = `שגיאת התחברות: ${err.message}`;
  }
}

async function enterApp() {
  const me = await api('/auth/me');
  state.tenantName = me.tenant_name;
  state.userEmail = me.email;

  el.loginView.classList.add('hidden');
  el.appView.classList.remove('hidden');
  el.tenantTitle.textContent = `${state.tenantName} | ${state.userEmail}`;

  bindRealtime();
  await refreshAll();
}

function logout() {
  state.token = '';
  localStorage.removeItem('hb_token');
  if (state.ws) {
    state.ws.close();
    state.ws = null;
  }
  location.reload();
}

async function refreshAll() {
  await Promise.all([loadUsage(), loadActivity(), loadJobs()]);
}

async function loadUsage() {
  const usage = await api('/dashboard/usage');
  el.usageText.textContent = `${usage.used_minutes.toFixed(1)} / ${usage.quota_minutes.toFixed(1)} דקות`;
  el.usageSub.textContent = `יתרה: ${usage.remaining_minutes.toFixed(1)} | ניצול: ${usage.utilization_percent.toFixed(1)}% | שיחות הושלמו: ${usage.completed_jobs}`;
}

async function loadActivity() {
  const data = await api(`/dashboard/activity?period=${state.period}`);
  const maxJobs = Math.max(1, ...data.points.map(p => p.jobs_total));
  el.activityChart.innerHTML = '';
  data.points.forEach((p) => {
    const bar = document.createElement('div');
    bar.className = 'activity-bar';
    bar.style.height = `${Math.max(6, (p.jobs_total / maxJobs) * 88)}px`;
    bar.title = `תאריך: ${p.day}\nסה"כ: ${p.jobs_total}\nהושלמו: ${p.jobs_completed}\nדקות: ${p.minutes_total}`;
    bar.dataset.day = String(p.day).slice(5);
    el.activityChart.appendChild(bar);
  });
}

async function loadJobs() {
  const q = new URLSearchParams();
  if (el.dateFrom.value) q.set('date_from', el.dateFrom.value);
  if (el.dateTo.value) q.set('date_to', el.dateTo.value);
  q.set('limit', '300');

  const out = await api(`/jobs?${q.toString()}`);
  state.jobs = out.items || [];
  renderJobsList();

  if (state.selectedJob) {
    const found = state.jobs.find(j => j.id === state.selectedJob.id);
    if (found) {
      await selectJob(found.id);
    }
  }
}

function renderJobsList() {
  el.jobsList.innerHTML = '';
  if (!state.jobs.length) {
    el.jobsList.textContent = 'אין שיחות להצגה';
    return;
  }

  state.jobs.forEach((job) => {
    const item = document.createElement('div');
    item.className = 'job-item';
    if (state.selectedJob && state.selectedJob.id === job.id) item.classList.add('active');
    item.innerHTML = `
      <div><strong>${job.source_filename}</strong></div>
      <div class="meta">${job.status} | ${fmtDate(job.queued_at)}</div>
      <div class="meta">משך הקלטה: ${fmtDurationSec(job.source_duration_sec)} | מילים: ${job.word_count || 0}</div>
    `;
    item.onclick = () => selectJob(job.id);
    el.jobsList.appendChild(item);
  });
}

async function selectJob(jobId) {
  const job = await api(`/jobs/${jobId}`);
  state.selectedJob = job;
  el.selectedJobTitle.textContent = job.source_filename;

  renderJobsList();
  renderTranscript(job);
  renderDetails(job);
  el.audioPlayer.src = `/jobs/${job.id}/audio-public?token=${encodeURIComponent(state.token)}`;
  el.audioPlayer.load();
}

function speakerClass(label) {
  if (!label) return '';
  return label.endsWith('1') ? 'spkA' : 'spkB';
}

function renderTranscript(job) {
  el.transcriptContainer.innerHTML = '';
  state.activeWordEl = null;

  job.channels.forEach((ch) => {
    const block = document.createElement('div');
    block.className = 'channel-block';

    const title = document.createElement('div');
    title.className = 'channel-title';
    title.textContent = `ערוץ ${ch.channel_index + 1} | ${ch.diarization_status || '--'}`;
    block.appendChild(title);

    const wordsWrap = document.createElement('div');
    (ch.words || []).forEach((w) => {
      const span = document.createElement('span');
      span.className = `word ${speakerClass(w.speaker_label)}`;
      span.textContent = w.text;
      span.dataset.start = String(w.start_sec || 0);
      span.dataset.end = String(w.end_sec || w.start_sec || 0);
      span.title = `${w.speaker_label || 'spk?'} | ${fmtDurationSec(w.start_sec)} - ${fmtDurationSec(w.end_sec)}`;
      span.onclick = () => {
        el.audioPlayer.currentTime = parseFloat(span.dataset.start || '0');
        el.audioPlayer.play();
      };
      wordsWrap.appendChild(span);
      wordsWrap.append(' ');
    });

    if (!ch.words || ch.words.length === 0) {
      wordsWrap.textContent = ch.transcript_text || '[אין טקסט]';
    }

    block.appendChild(wordsWrap);
    el.transcriptContainer.appendChild(block);
  });
}

function renderDetails(job) {
  const fields = [
    ['שם קובץ', job.source_filename],
    ['נתיב קובץ', job.source_file_path],
    ['משך הקלטה', fmtDurationSec(job.source_duration_sec)],
    ['משך תמלול', fmtDurationSec(job.transcription_duration_sec)],
    ['כמות מילים', String(job.word_count || 0)],
    ['זמן שליחה', fmtDate(job.queued_at)],
    ['זמן התחלה', fmtDate(job.started_at)],
    ['זמן סיום', fmtDate(job.completed_at)],
    ['סטטוס', job.status],
    ['מספר ערוצים', String(job.source_channel_count)],
  ];

  el.detailsGrid.innerHTML = '';
  fields.forEach(([label, value]) => {
    const box = document.createElement('div');
    box.className = 'detail-box';
    box.innerHTML = `<div class="detail-label">${label}</div><div class="detail-value">${value || '--'}</div>`;
    el.detailsGrid.appendChild(box);
  });
}

function updateActiveWordHighlight() {
  const t = el.audioPlayer.currentTime || 0;
  const words = el.transcriptContainer.querySelectorAll('.word');
  let active = null;

  for (const w of words) {
    const s = parseFloat(w.dataset.start || '0');
    const e = parseFloat(w.dataset.end || '0');
    if (t >= s && t <= e + 0.02) {
      active = w;
      break;
    }
  }

  if (state.activeWordEl && state.activeWordEl !== active) {
    state.activeWordEl.classList.remove('active');
  }
  if (active && active !== state.activeWordEl) {
    active.classList.add('active');
    active.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }
  state.activeWordEl = active;
}

function applyWordSearch() {
  const q = el.wordSearch.value.trim().toLowerCase();
  const words = el.transcriptContainer.querySelectorAll('.word');
  words.forEach((w) => {
    w.classList.remove('search-hit');
    if (!q) return;
    if (w.textContent.toLowerCase().includes(q)) {
      w.classList.add('search-hit');
    }
  });
}

function activateTab(name) {
  const transcript = name === 'transcript';
  el.tabTranscript.classList.toggle('active', transcript);
  el.tabDetails.classList.toggle('active', !transcript);
  el.transcriptView.classList.toggle('hidden', !transcript);
  el.detailsView.classList.toggle('hidden', transcript);
}

async function downloadExport(format) {
  if (!state.selectedJob) return;
  const resp = await fetch(`/jobs/${state.selectedJob.id}/export?format=${format}`, {
    headers: { Authorization: `Bearer ${state.token}` },
  });
  if (!resp.ok) return;

  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${state.selectedJob.source_filename}.${format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function bindRealtime() {
  if (state.ws) {
    state.ws.close();
  }

  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${proto}//${location.host}/ws/tenant?token=${encodeURIComponent(state.token)}`);
  state.ws = ws;

  ws.onopen = () => {
    el.wsStatus.textContent = 'Live: connected';
  };
  ws.onclose = () => {
    el.wsStatus.textContent = 'Live: disconnected';
    setTimeout(() => {
      if (state.token) bindRealtime();
    }, 3000);
  };
  ws.onmessage = (evt) => {
    try {
      const payload = JSON.parse(evt.data);
      if (payload.type === 'tenant_update') {
        const q = payload.queue || {};
        el.queueText.textContent = `ממתינים: ${q.queued || 0} | בתהליך: ${q.processing || 0} | ממתינים לניסיון חוזר: ${q.retry_wait || 0}`;
        el.queueSub.textContent = `הושלמו: ${q.completed || 0} | נכשלו: ${q.failed || 0} | dead-letter: ${q.dead_letter || 0} | workers: ${payload.workers_online || 0}`;
      }
    } catch (_) {}
  };
}

function bindEvents() {
  el.loginForm.addEventListener('submit', login);
  el.logoutBtn.addEventListener('click', logout);
  el.refreshBtn.addEventListener('click', refreshAll);
  el.filterBtn.addEventListener('click', loadJobs);
  el.clearFilterBtn.addEventListener('click', () => {
    el.dateFrom.value = '';
    el.dateTo.value = '';
    loadJobs();
  });
  el.audioPlayer.addEventListener('timeupdate', updateActiveWordHighlight);
  el.wordSearch.addEventListener('input', applyWordSearch);
  el.tabTranscript.addEventListener('click', () => activateTab('transcript'));
  el.tabDetails.addEventListener('click', () => activateTab('details'));

  document.querySelectorAll('.period-btn[data-period]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      document.querySelectorAll('.period-btn[data-period]').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      state.period = btn.dataset.period;
      await loadActivity();
    });
  });

  document.querySelectorAll('.export-row .btn[data-export]').forEach((btn) => {
    btn.addEventListener('click', () => downloadExport(btn.dataset.export));
  });
}

async function bootstrap() {
  bindEvents();
  if (state.token) {
    try {
      await enterApp();
      return;
    } catch (_) {
      localStorage.removeItem('hb_token');
      state.token = '';
    }
  }
}

bootstrap();
