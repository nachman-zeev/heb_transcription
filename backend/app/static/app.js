const state = {
  token: localStorage.getItem('hb_token') || '',
  tenantName: '',
  userEmail: '',
  jobs: [],
  selectedJob: null,
  selectedJobPollTimer: null,
  selectedJobPollInFlight: false,
  playbackTickTimer: null,
  txProgressTimer: null,
  txProgressDisplayPct: 0,
  txProgressTargetPct: 0,
  txProgressJobId: '',
  txProgressLabel: '',
  txProgressStatus: '',
  wordTimeline: [],
  lastCompletionNoticeJobId: '',
  activeWordEls: new Set(),
  period: 'week',
  ws: null,
};

const el = {
  loginView: document.getElementById('loginView'),
  appView: document.getElementById('appView'),
  loginForm: document.getElementById('loginForm'),
  bootstrapForm: document.getElementById('bootstrapForm'),
  tenantInput: document.getElementById('tenantInput'),
  emailInput: document.getElementById('emailInput'),
  passwordInput: document.getElementById('passwordInput'),
  bootstrapTenantInput: document.getElementById('bootstrapTenantInput'),
  bootstrapEmailInput: document.getElementById('bootstrapEmailInput'),
  bootstrapPasswordInput: document.getElementById('bootstrapPasswordInput'),
  bootstrapMsg: document.getElementById('bootstrapMsg'),
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
  selectedJobStatus: document.getElementById('selectedJobStatus'),
  tabTranscript: document.getElementById('tabTranscript'),
  tabDetails: document.getElementById('tabDetails'),
  transcriptView: document.getElementById('transcriptView'),
  detailsView: document.getElementById('detailsView'),
  uploadAudioInput: document.getElementById('uploadAudioInput'),
  uploadPriorityInput: document.getElementById('uploadPriorityInput'),
  uploadPriorityHelp: document.getElementById('uploadPriorityHelp'),
  uploadJobBtn: document.getElementById('uploadJobBtn'),
  uploadJobMsg: document.getElementById('uploadJobMsg'),
  audioPlayer: document.getElementById('audioPlayer'),
  transcriptionProgressWrap: document.getElementById('transcriptionProgressWrap'),
  transcriptionProgressLabel: document.getElementById('transcriptionProgressLabel'),
  transcriptionProgressPct: document.getElementById('transcriptionProgressPct'),
  transcriptionProgressBar: document.getElementById('transcriptionProgressBar'),
  transcriptContainer: document.getElementById('transcriptContainer'),
  wordSearch: document.getElementById('wordSearch'),
  detailsGrid: document.getElementById('detailsGrid'),
};

async function api(path, options = {}) {
  const headers = options.headers || {};
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  if (!isFormData) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }
  if (state.token) {
    headers['Authorization'] = `Bearer ${state.token}`;
  }

  const resp = await fetch(path, { ...options, headers });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      detail = formatApiErrorDetail(body.detail ?? body);
    } catch (_) {}
    throw new Error(detail);
  }

  const ctype = resp.headers.get('content-type') || '';
  if (ctype.includes('application/json')) {
    return resp.json();
  }
  return resp;
}

function formatApiErrorDetail(detail) {
  if (detail == null) return 'שגיאה לא ידועה';
  if (typeof detail === 'string') return detail;

  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (item && typeof item === 'object') {
        const loc = Array.isArray(item.loc) ? item.loc.join('.') : '';
        const msg = item.msg ? String(item.msg) : JSON.stringify(item);
        return loc ? `${loc}: ${msg}` : msg;
      }
      return String(item);
    });
    return parts.join(' | ');
  }

  if (typeof detail === 'object') {
    if (typeof detail.message === 'string' && detail.message.trim()) {
      return detail.message;
    }
    try {
      return JSON.stringify(detail);
    } catch (_) {
      return String(detail);
    }
  }

  return String(detail);
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

function statusLabel(status) {
  const map = {
    queued: 'ממתין בתור',
    processing: 'בתמלול',
    retry_wait: 'ממתין לניסיון חוזר',
    completed: 'הושלם',
    failed: 'נכשל',
    dead_letter: 'נכשל סופית',
  };
  return map[status] || status || '--';
}

function isTerminalStatus(status) {
  return status === 'completed' || status === 'failed' || status === 'dead_letter';
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function collectChannelProgress(job) {
  const channels = job?.channels || [];
  const total = channels.length || Number(job?.source_channel_count || 0) || 0;
  const completed = channels.filter((c) => c.status === 'completed').length;
  const processing = channels.filter((c) => c.status === 'processing');
  const failed = channels.filter((c) => c.status === 'failed').length;
  return {
    total,
    completed,
    processingCount: processing.length,
    processingChannel: processing.length ? Number(processing[0].channel_index) + 1 : 0,
    failed,
  };
}

function buildTranscriptionProgress(job) {
  if (!job) {
    return { show: false, pct: 0, label: 'סטטוס Job: --' };
  }

  const status = String(job.status || '');
  const channel = collectChannelProgress(job);

  if (status === 'completed') {
    return {
      show: false,
      pct: 100,
      label: `הסתיים בהצלחה: ${fmtDate(job.completed_at)}`,
      statusText: `סטטוס Job: הושלם | הסתיים: ${fmtDate(job.completed_at)}`,
    };
  }
  if (status === 'failed' || status === 'dead_letter') {
    const err = String(job.error_message || '').trim();
    return {
      show: false,
      pct: 100,
      label: statusLabel(status),
      statusText: `סטטוס Job: ${statusLabel(status)}${err ? ` | שגיאה: ${err}` : ''}`,
    };
  }
  if (status === 'retry_wait') {
    const retryAt = job.next_attempt_at ? fmtDate(job.next_attempt_at) : 'בקרוב';
    return {
      show: true,
      pct: 4,
      label: `ממתין לניסיון חוזר: ${retryAt}`,
      statusText: `סטטוס Job: ממתין לניסיון חוזר | ניסיון ${Number(job.retry_count || 0) + 1}/${Number(job.max_retries || 0) + 1}`,
    };
  }
  if (status === 'queued') {
    const channelText = channel.total > 0 ? ` | ערוצים: ${channel.completed}/${channel.total}` : '';
    return {
      show: true,
      pct: 2,
      label: 'ממתין בתור להתחלת תמלול',
      statusText: `סטטוס Job: ממתין בתור${channelText}`,
    };
  }

  // processing and any unknown non-terminal state
  let pct = 12;
  if (channel.total > 0) {
    const processingWeight = channel.processingCount > 0 ? 0.45 : 0.15;
    pct = ((channel.completed + processingWeight) / channel.total) * 100;
  }
  pct = Math.round(clamp(pct, 8, 96));

  const stage = channel.processingChannel > 0
    ? `מתמלל ערוץ ${channel.processingChannel} מתוך ${channel.total || '?'}`
    : 'התמלול בתהליך';
  const channelText = channel.total > 0 ? ` | הושלמו ${channel.completed}/${channel.total} ערוצים` : '';
  const failedText = channel.failed > 0 ? ` | ערוצים שנכשלו: ${channel.failed}` : '';

  return {
    show: true,
    pct,
    label: `${stage}${channelText}`,
    statusText: `סטטוס Job: בתמלול | ${stage}${channelText}${failedText}`,
  };
}

function updateTranscriptionProgress(job) {
  if (!el.transcriptionProgressWrap || !el.transcriptionProgressBar || !el.transcriptionProgressLabel || !el.transcriptionProgressPct) {
    return;
  }

  const render = (valuePct, labelText) => {
    const pct = clamp(Math.round(Number(valuePct || 0)), 0, 100);
    el.transcriptionProgressWrap.classList.remove('hidden');
    el.transcriptionProgressLabel.textContent = labelText || 'התמלול בתהליך';
    el.transcriptionProgressPct.textContent = `${pct}%`;
    el.transcriptionProgressBar.style.width = `${pct}%`;
    const track = el.transcriptionProgressBar.parentElement;
    if (track) track.setAttribute('aria-valuenow', String(pct));
  };

  const stopTicker = (reset = false) => {
    if (state.txProgressTimer) {
      clearInterval(state.txProgressTimer);
      state.txProgressTimer = null;
    }
    if (reset) {
      state.txProgressDisplayPct = 0;
      state.txProgressTargetPct = 0;
      state.txProgressJobId = '';
      state.txProgressLabel = '';
      state.txProgressStatus = '';
    }
  };

  const startTicker = () => {
    if (state.txProgressTimer) return;
    state.txProgressTimer = setInterval(() => {
      if (!state.selectedJob || state.selectedJob.id !== state.txProgressJobId || isTerminalStatus(state.selectedJob.status)) {
        stopTicker();
        return;
      }

      // Keep progress lively between backend polling updates.
      if (state.txProgressDisplayPct >= state.txProgressTargetPct - 0.25) {
        if (state.txProgressStatus === 'processing') {
          state.txProgressTargetPct = Math.min(95, state.txProgressTargetPct + 0.9);
        } else if (state.txProgressStatus === 'queued') {
          state.txProgressTargetPct = Math.min(9, state.txProgressTargetPct + 0.25);
        } else if (state.txProgressStatus === 'retry_wait') {
          state.txProgressTargetPct = Math.min(15, state.txProgressTargetPct + 0.35);
        }
      }

      const delta = state.txProgressTargetPct - state.txProgressDisplayPct;
      if (delta > 0.01) {
        const step = clamp(delta, 0.4, 1.8);
        state.txProgressDisplayPct = clamp(state.txProgressDisplayPct + step, 0, 100);
      }

      render(state.txProgressDisplayPct, state.txProgressLabel);
    }, 120);
  };

  const progress = buildTranscriptionProgress(job);
  if (!progress.show) {
    stopTicker(true);
    el.transcriptionProgressWrap.classList.add('hidden');
    el.transcriptionProgressLabel.textContent = progress.label || '';
    el.transcriptionProgressPct.textContent = '0%';
    el.transcriptionProgressBar.style.width = '0%';
    const track = el.transcriptionProgressBar.parentElement;
    if (track) track.setAttribute('aria-valuenow', '0');
    return;
  }

  const requestedPct = clamp(Number(progress.pct || 0), 0, 100);
  const isNewJob = state.txProgressJobId !== job.id;
  if (isNewJob) {
    state.txProgressDisplayPct = 0;
    state.txProgressTargetPct = 0;
  }

  state.txProgressJobId = job.id;
  state.txProgressLabel = progress.label || 'התמלול בתהליך';
  state.txProgressStatus = String(job.status || '');

  // Limit abrupt target jumps so UI stays smooth (max ~18% per backend update).
  const cappedTarget = Math.min(requestedPct, state.txProgressTargetPct + 18);
  state.txProgressTargetPct = Math.max(state.txProgressTargetPct, cappedTarget);
  state.txProgressTargetPct = clamp(state.txProgressTargetPct, 0, 100);

  if (state.txProgressDisplayPct <= 0 && state.txProgressTargetPct < 4) {
    state.txProgressTargetPct = 4;
  }

  render(state.txProgressDisplayPct, state.txProgressLabel);
  startTicker();
}

function updatePriorityHint() {
  if (!el.uploadPriorityInput || !el.uploadPriorityHelp) return;
  const value = clamp(parseInt(el.uploadPriorityInput.value || '100', 10) || 100, 1, 1000);
  el.uploadPriorityInput.value = String(value);
  el.uploadPriorityHelp.textContent = `עדיפות נוכחית: ${value} | מספר קטן = תור מוקדם יותר (1 הכי דחוף).`;
}

function updateSelectedJobStatus(job) {
  if (!el.selectedJobStatus) return;
  if (!job) {
    el.selectedJobStatus.textContent = 'סטטוס Job: --';
    updateTranscriptionProgress(null);
    return;
  }
  const progress = buildTranscriptionProgress(job);
  el.selectedJobStatus.textContent = progress.statusText || `סטטוס Job: ${statusLabel(job.status)}`;
  updateTranscriptionProgress(job);
}

function isNumericLikeToken(token) {
  const t = String(token || '').trim();
  return !!t && /^[0-9.,:+\-/%()]+$/.test(t);
}

function normalizeWordsForDisplay(words, durationSec) {
  const items = (words || []).map((w) => {
    const token = String(w.text || '').trim();
    if (!token) return null;

    const startRaw = Number(w.start_sec);
    const endRaw = Number(w.end_sec);
    const hasStart = Number.isFinite(startRaw);
    const hasEnd = Number.isFinite(endRaw);
    return {
      word: w,
      token,
      start: hasStart ? startRaw : null,
      end: hasEnd ? endRaw : null,
    };
  }).filter(Boolean);

  if (!items.length) return [];

  const observedMax = items.reduce((mx, it) => {
    const s = it.start ?? 0;
    const e = it.end ?? s;
    return Math.max(mx, s, e);
  }, 0);
  const duration = Math.max(
    Number.isFinite(Number(durationSec)) ? Number(durationSec) : 0,
    observedMax,
    0.2
  );

  let prevEnd = 0;
  return items.map((it) => {
    let start = it.start;
    let end = it.end;

    if (start == null && end != null) start = end;
    if (start == null) start = prevEnd;
    if (end == null) end = start;
    if (end < start) end = start;

    start = Math.max(0, Math.min(start, duration));
    end = Math.max(start, Math.min(end, duration));

    if (end <= start) {
      const minWidth = isNumericLikeToken(it.token) ? 0.08 : 0.05;
      end = Math.min(duration, start + minWidth);
    }

    if (end <= start && start > 0) {
      start = Math.max(0, start - 0.02);
      end = Math.min(duration, start + 0.04);
    }

    prevEnd = Math.max(prevEnd, end);
    return {
      ...it.word,
      text: it.token,
      display_start_sec: Number(start.toFixed(6)),
      display_end_sec: Number(end.toFixed(6)),
    };
  });
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

async function runBootstrap(evt) {
  evt.preventDefault();
  if (!el.bootstrapForm) return;
  el.bootstrapMsg.textContent = '';
  try {
    const tenant_name = el.bootstrapTenantInput.value.trim();
    const email = el.bootstrapEmailInput.value.trim();
    const password = el.bootstrapPasswordInput.value;
    await api('/auth/bootstrap', {
      method: 'POST',
      body: JSON.stringify({ tenant_name, email, password }),
    });
    el.bootstrapMsg.textContent = 'Bootstrap הושלם. אפשר להתחבר עם הפרטים שהזנת.';
    el.tenantInput.value = tenant_name;
    el.emailInput.value = email;
    el.passwordInput.value = password;
  } catch (err) {
    const message = String(err.message || err);
    if (message.includes('Bootstrap already completed')) {
      el.bootstrapMsg.textContent = 'המערכת כבר אותחלה בעבר. יש להתחבר עם משתמש קיים.';
    } else {
      el.bootstrapMsg.textContent = `שגיאה: ${message}`;
    }
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
  stopSelectedJobPolling();
  stopPlaybackTicker();
  updateTranscriptionProgress(null);
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
    const channels = job.channels || [];
    const totalChannels = channels.length || Number(job.source_channel_count || 0) || 0;
    const doneChannels = channels.filter((c) => c.status === 'completed').length;
    const channelMeta = totalChannels > 0 ? ` | ערוצים: ${doneChannels}/${totalChannels}` : '';
    item.innerHTML = `
      <div><strong>${job.source_filename}</strong></div>
      <div class="meta">${statusLabel(job.status)} | ${fmtDate(job.queued_at)}${channelMeta}</div>
      <div class="meta">משך הקלטה: ${fmtDurationSec(job.source_duration_sec)} | מילים: ${job.word_count || 0}</div>
    `;
    item.onclick = () => selectJob(job.id);
    el.jobsList.appendChild(item);
  });
}

function stopSelectedJobPolling() {
  if (state.selectedJobPollTimer) {
    clearInterval(state.selectedJobPollTimer);
    state.selectedJobPollTimer = null;
  }
  state.selectedJobPollInFlight = false;
}

function stopPlaybackTicker() {
  if (state.playbackTickTimer) {
    cancelAnimationFrame(state.playbackTickTimer);
    state.playbackTickTimer = null;
  }
}

function startPlaybackTicker() {
  stopPlaybackTicker();
  const tick = () => {
    if (el.audioPlayer.paused || el.audioPlayer.ended) {
      state.playbackTickTimer = null;
      return;
    }
    updateActiveWordHighlight();
    state.playbackTickTimer = requestAnimationFrame(tick);
  };
  state.playbackTickTimer = requestAnimationFrame(tick);
}

async function pollSelectedJobOnce() {
  if (!state.selectedJob || state.selectedJobPollInFlight) return;
  if (isTerminalStatus(state.selectedJob.status)) {
    stopSelectedJobPolling();
    return;
  }

  state.selectedJobPollInFlight = true;
  try {
    const latest = await api(`/jobs/${state.selectedJob.id}`);
    if (!state.selectedJob || latest.id !== state.selectedJob.id) return;

    const prevStatus = state.selectedJob.status;
    const prevWordCount = Number(state.selectedJob.word_count || 0);
    state.selectedJob = latest;
    updateSelectedJobStatus(latest);
    renderJobsList();

    const latestWordCount = Number(latest.word_count || 0);
    if (latest.status !== prevStatus || latestWordCount !== prevWordCount) {
      renderTranscript(latest);
      renderDetails(latest);
    }

    if (isTerminalStatus(latest.status)) {
      stopSelectedJobPolling();
      if (latest.id !== state.lastCompletionNoticeJobId) {
        state.lastCompletionNoticeJobId = latest.id;
        el.uploadJobMsg.textContent = `Job ${statusLabel(latest.status)}: ${latest.source_filename}`;
      }
    }
  } catch (_) {
    // Ignore temporary polling failures and retry on next tick.
  } finally {
    state.selectedJobPollInFlight = false;
  }
}

function startSelectedJobPolling() {
  stopSelectedJobPolling();
  if (!state.selectedJob || isTerminalStatus(state.selectedJob.status)) return;
  state.selectedJobPollTimer = setInterval(() => {
    pollSelectedJobOnce();
  }, 3000);
}

async function selectJob(jobId) {
  stopPlaybackTicker();
  const job = await api(`/jobs/${jobId}`);
  state.selectedJob = job;
  el.selectedJobTitle.textContent = job.source_filename;
  updateSelectedJobStatus(job);

  renderJobsList();
  renderTranscript(job);
  renderDetails(job);
  el.audioPlayer.src = `/jobs/${job.id}/audio-public?token=${encodeURIComponent(state.token)}`;
  el.audioPlayer.load();
  updateActiveWordHighlight();
  startSelectedJobPolling();
}

function speakerClass(label) {
  if (!label) return '';
  return label.endsWith('1') ? 'spkA' : 'spkB';
}

function renderTranscript(job) {
  el.transcriptContainer.innerHTML = '';
  state.activeWordEls = new Set();
  state.wordTimeline = [];

  job.channels.forEach((ch) => {
    const block = document.createElement('div');
    block.className = 'channel-block';

    const title = document.createElement('div');
    title.className = 'channel-title';
    title.textContent = `ערוץ ${ch.channel_index + 1} | ${ch.diarization_status || '--'}`;
    block.appendChild(title);

    const wordsWrap = document.createElement('div');
    const words = normalizeWordsForDisplay(ch.words || [], job.source_duration_sec);
    words.forEach((w) => {
      const span = document.createElement('span');
      span.className = `word ${speakerClass(w.speaker_label)}`;
      span.textContent = w.text;
      span.dataset.start = String(w.display_start_sec || 0);
      span.dataset.end = String(w.display_end_sec || w.display_start_sec || 0);
      span.dataset.token = String(w.text || '');
      span.title = `${w.speaker_label || 'spk?'} | ${fmtDurationSec(w.display_start_sec)} - ${fmtDurationSec(w.display_end_sec)}`;
      span.onclick = () => {
        el.audioPlayer.currentTime = parseFloat(span.dataset.start || '0');
        el.audioPlayer.play();
      };
      wordsWrap.appendChild(span);
      wordsWrap.append(' ');

      state.wordTimeline.push({
        el: span,
        start: parseFloat(span.dataset.start || '0'),
        end: parseFloat(span.dataset.end || '0'),
        token: span.dataset.token || '',
      });
    });

    if (!words.length) {
      wordsWrap.textContent = ch.transcript_text || '[אין טקסט]';
    }

    block.appendChild(wordsWrap);
    el.transcriptContainer.appendChild(block);
  });

  state.wordTimeline.sort((a, b) => a.start - b.start || a.end - b.end);
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
  const words = state.wordTimeline || [];
  const activeNow = new Set();
  let firstActive = null;

  for (const w of words) {
    const s = w.start;
    const e = w.end;
    const token = w.token;
    const rightPad = isNumericLikeToken(token) ? 0.12 : 0.05;
    if (t >= s - 0.02 && t <= e + rightPad) {
      activeNow.add(w.el);
      if (!firstActive) firstActive = w.el;
    }
  }

  for (const prev of state.activeWordEls) {
    if (!activeNow.has(prev)) {
      prev.classList.remove('active');
    }
  }

  for (const cur of activeNow) {
    if (!cur.classList.contains('active')) {
      cur.classList.add('active');
    }
  }

  if (firstActive && !state.activeWordEls.has(firstActive)) {
    firstActive.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }
  state.activeWordEls = activeNow;
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

async function createJobByUpload() {
  if (!el.uploadAudioInput || !el.uploadJobBtn) return;
  el.uploadJobMsg.textContent = '';

  const file = el.uploadAudioInput.files && el.uploadAudioInput.files[0];
  if (!file) {
    el.uploadJobMsg.textContent = 'בחר קובץ אודיו (.wav או .mp3)';
    return;
  }

  updatePriorityHint();
  const priority = clamp(parseInt(el.uploadPriorityInput.value || '100', 10) || 100, 1, 1000);
  const fd = new FormData();
  fd.append('file', file);
  fd.append('priority', String(priority));

  el.uploadJobBtn.disabled = true;
  try {
    const out = await api('/jobs/upload', {
      method: 'POST',
      body: fd,
    });
    el.uploadJobMsg.textContent = `נוצר Job בהצלחה: ${out.id}`;
    el.uploadAudioInput.value = '';
    await loadJobs();
    await selectJob(out.id);
  } catch (err) {
    el.uploadJobMsg.textContent = `שגיאה ביצירת Job: ${err.message}`;
  } finally {
    el.uploadJobBtn.disabled = false;
  }
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
  if (el.bootstrapForm) {
    el.bootstrapForm.addEventListener('submit', runBootstrap);
  }
  el.logoutBtn.addEventListener('click', logout);
  el.refreshBtn.addEventListener('click', refreshAll);
  if (el.uploadJobBtn) {
    el.uploadJobBtn.addEventListener('click', createJobByUpload);
  }
  if (el.uploadPriorityInput) {
    el.uploadPriorityInput.addEventListener('input', updatePriorityHint);
    el.uploadPriorityInput.addEventListener('change', updatePriorityHint);
  }
  el.filterBtn.addEventListener('click', loadJobs);
  el.clearFilterBtn.addEventListener('click', () => {
    el.dateFrom.value = '';
    el.dateTo.value = '';
    loadJobs();
  });
  el.audioPlayer.addEventListener('timeupdate', updateActiveWordHighlight);
  el.audioPlayer.addEventListener('play', () => {
    updateActiveWordHighlight();
    startPlaybackTicker();
  });
  el.audioPlayer.addEventListener('pause', () => {
    stopPlaybackTicker();
    updateActiveWordHighlight();
  });
  el.audioPlayer.addEventListener('ended', () => {
    stopPlaybackTicker();
    updateActiveWordHighlight();
  });
  el.audioPlayer.addEventListener('loadedmetadata', updateActiveWordHighlight);
  el.audioPlayer.addEventListener('loadeddata', updateActiveWordHighlight);
  el.audioPlayer.addEventListener('seeking', updateActiveWordHighlight);
  el.audioPlayer.addEventListener('seeked', updateActiveWordHighlight);
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
  updatePriorityHint();
  updateSelectedJobStatus(null);
  updateTranscriptionProgress(null);
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
