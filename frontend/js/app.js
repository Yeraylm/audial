/* ============================================================
   Audial · app.js
   Custom cursor · Scroll progress · IntersectionObserver reveals
   Magnetic buttons · Ripple · 3D Tilt · Parallax blobs
   Tab fix (CSS-only, no GSAP for opacity)
   ============================================================ */

// API base URL (empty = same origin; set AUDIAL_API in config.js or env for remote backend)
const API = (window.AUDIAL_API || '').replace(/\/$/, '');

// Attach session ID to every fetch
const _fetch = window.fetch.bind(window);
window.fetch = function(url, opts = {}) {
  if (typeof url === 'string' && url.startsWith(API + '/api')) {
    opts.headers = { ...(opts.headers || {}), 'X-Session-ID': window.AUDIAL_SESSION || '' };
  }
  return _fetch(url, opts);
};

let currentAudioId = null;
let pollingTimer   = null;
let selectedLang   = 'auto';
const charts = {};

/* ---- DOM helpers ---- */
const $  = (s, ctx = document) => ctx.querySelector(s);
const $$ = (s, ctx = document) => Array.from(ctx.querySelectorAll(s));
const safe = fn => { try { fn(); } catch (e) { console.warn('[safe]', e); } };

function fmtDur(s) {
  if (s == null) return '-';
  s = parseFloat(s) || 0;
  const h = Math.floor(s/3600), m = Math.floor((s%3600)/60), ss = Math.floor(s%60);
  return h > 0 ? `${h}h ${String(m).padStart(2,'0')}m` : `${m}m ${String(ss).padStart(2,'0')}s`;
}
function fmtDate(iso) {
  try { return new Date(iso).toLocaleString(window.i18n?.lang === 'en' ? 'en-GB' : 'es-ES',
    {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}); }
  catch { return iso; }
}
function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function t(key) { return window.i18n ? window.i18n.t(key) : key; }
function refreshIcons() { if (window.lucide) lucide.createIcons(); }

/* ============================================================
   CUSTOM CURSOR
   ============================================================ */
(function initCursor() {
  const dot  = $('#cursorDot');
  const ring = $('#cursorRing');
  if (!dot || !ring) return;

  let rx = 0, ry = 0;
  let cx = 0, cy = 0;

  document.addEventListener('mousemove', e => {
    cx = e.clientX; cy = e.clientY;
    dot.style.left  = cx + 'px';
    dot.style.top   = cy + 'px';
  });

  // Ring follows with lag
  (function animRing() {
    rx += (cx - rx) * 0.12;
    ry += (cy - ry) * 0.12;
    ring.style.left = rx + 'px';
    ring.style.top  = ry + 'px';
    requestAnimationFrame(animRing);
  })();

  // Hover state
  document.addEventListener('mouseover', e => {
    const el = e.target.closest('a,button,.audio-row,.feature-card,.suggestion-chip,.related-card,.entity-chip,.tab-btn');
    document.body.classList.toggle('cursor-hover', !!el);
  });

  // Click state
  document.addEventListener('mousedown', () => document.body.classList.add('cursor-click'));
  document.addEventListener('mouseup',   () => document.body.classList.remove('cursor-click'));
})();

/* ============================================================
   SCROLL PROGRESS BAR
   ============================================================ */
(function initScrollProgress() {
  const bar = $('#scrollProgress');
  if (!bar) return;
  window.addEventListener('scroll', () => {
    const total = document.documentElement.scrollHeight - window.innerHeight;
    bar.style.width = (total > 0 ? (window.scrollY / total) * 100 : 0) + '%';
  }, { passive: true });
})();

/* ============================================================
   SCROLL REVEALS (IntersectionObserver)
   ============================================================ */
(function initReveals() {
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('visible');
        obs.unobserve(e.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

  const observe = () => $$('.reveal:not(.visible)').forEach(el => obs.observe(el));
  observe();
  window.addEventListener('pageChanged', observe);
})();

/* ============================================================
   RIPPLE EFFECT
   ============================================================ */
document.addEventListener('click', e => {
  const btn = e.target.closest('.ripple');
  if (!btn) return;
  const r   = btn.getBoundingClientRect();
  const sz  = Math.max(r.width, r.height);
  const wave = document.createElement('span');
  wave.className = 'ripple-wave';
  wave.style.cssText = `width:${sz}px;height:${sz}px;left:${e.clientX - r.left - sz/2}px;top:${e.clientY - r.top - sz/2}px`;
  btn.appendChild(wave);
  wave.addEventListener('animationend', () => wave.remove());
});

/* ============================================================
   MAGNETIC BUTTONS
   ============================================================ */
(function initMagnetic() {
  const apply = () => {
    $$('.magnetic').forEach(el => {
      el.addEventListener('mousemove', e => {
        const r   = el.getBoundingClientRect();
        const x   = (e.clientX - r.left - r.width  / 2) * 0.25;
        const y   = (e.clientY - r.top  - r.height / 2) * 0.25;
        el.style.transform = `translate(${x}px, ${y}px)`;
      });
      el.addEventListener('mouseleave', () => { el.style.transform = ''; });
    });
  };
  apply();
  window.addEventListener('pageChanged', apply);
})();

/* ============================================================
   3D TILT on feature cards
   ============================================================ */
(function initTilt() {
  const apply = () => {
    $$('.tilt').forEach(el => {
      el.addEventListener('mousemove', e => {
        const r  = el.getBoundingClientRect();
        const x  = (e.clientX - r.left) / r.width  - .5;
        const y  = (e.clientY - r.top)  / r.height - .5;
        el.style.transform = `perspective(700px) rotateY(${x * 14}deg) rotateX(${-y * 14}deg) scale3d(1.03,1.03,1.03)`;
      });
      el.addEventListener('mouseleave', () => {
        el.style.transform = 'perspective(700px) rotateY(0deg) rotateX(0deg) scale3d(1,1,1)';
      });
    });
  };
  apply();
  window.addEventListener('pageChanged', apply);
})();

/* ============================================================
   PARALLAX BLOBS on mouse move
   ============================================================ */
document.addEventListener('mousemove', e => {
  const fx = (e.clientX / window.innerWidth  - .5) * 30;
  const fy = (e.clientY / window.innerHeight - .5) * 30;
  $$('.blob').forEach((b, i) => {
    const s = (i + 1) * 0.4;
    b.style.transform = `translate(${fx * s}px, ${fy * s}px)`;
  });
}, { passive: true });

/* ============================================================
   UPLOAD ZONE: mouse spotlight
   ============================================================ */
const dz = $('#dropzone');
if (dz) {
  dz.addEventListener('mousemove', e => {
    const r = dz.getBoundingClientRect();
    dz.style.setProperty('--mx', `${((e.clientX - r.left) / r.width)  * 100}%`);
    dz.style.setProperty('--my', `${((e.clientY - r.top)  / r.height) * 100}%`);
  });
}

/* ============================================================
   LANG PICKER (audio language selector in dropzone)
   ============================================================ */
$$('[data-audio-lang]').forEach(btn => {
  btn.addEventListener('click', e => {
    e.stopPropagation();
    $$('[data-audio-lang]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedLang = btn.dataset.audioLang;
  });
});

// Re-render everything when language changes
window.addEventListener('langchange', () => {
  i18n.applyTranslations();
  refreshIcons();

  // Re-render dynamic content on the currently visible page
  const activePage = document.querySelector('.page.active');
  const pageId = activePage?.id || '';

  if (pageId === 'page-conversations') {
    refreshAudios();
  } else if (pageId === 'page-dashboard') {
    refreshDashboard();
  } else if (pageId === 'page-detail' && currentAudioId) {
    // Re-render only the static labels of the active tab (data comes from backend, not i18n)
    // Re-render tasks/decisions/questions labels and static strings
    $$('.col-title [data-i18n]').forEach(el => {
      const v = t(el.dataset.i18n); if (v) el.textContent = v;
    });
    // Refresh tab labels
    $$('.tab-btn [data-i18n]').forEach(el => {
      const v = t(el.dataset.i18n); if (v) el.textContent = v;
    });
    // Refresh metrics labels if metrics panel visible
    const metricsPanel = $('.tab-panel[data-tab="metrics"]');
    if (metricsPanel?.classList.contains('active')) {
      const a = window._lastAnalysis;
      if (a) safe(() => renderMetrics(a.metrics));
    }
    // Refresh transcript count label
    const cnt = $('#transcriptCount');
    if (cnt) {
      const n = $$('.segment-row').length;
      if (n) cnt.textContent = `${n} ${t('transcript.count')}`;
    }
  } else if (pageId === 'page-chat') {
    const chatInput = $('#chatInput');
    if (chatInput) chatInput.placeholder = t('chat.placeholder');
    const sel = $('#chatAudio');
    if (sel && sel.options[0]) sel.options[0].text = t('chat.all');
  }
});

/* ============================================================
   NAVIGATION
   ============================================================ */
window.showPage = function(name) {
  $$('.page').forEach(p => p.classList.remove('active'));
  $$('.nav-pill').forEach(a => a.classList.remove('active'));

  const page = $(`#page-${name}`);
  if (page) page.classList.add('active');

  const nav = $(`.nav-pill[data-page="${name}"]`);
  if (nav) nav.classList.add('active');

  window.scrollTo({ top: 0, behavior: 'smooth' });
  window.dispatchEvent(new Event('pageChanged'));

  if (name === 'dashboard')     refreshDashboard();
  if (name === 'conversations') refreshAudios();

  i18n.applyTranslations();
  refreshIcons();
};

$$('.nav-pill').forEach(a => {
  if (a.dataset.page) {
    a.addEventListener('click', e => { e.preventDefault(); showPage(a.dataset.page); });
  }
});

/* ============================================================
   UPLOAD
   ============================================================ */
const fi     = $('#fileInput');
const selBtn = $('#selectBtn');

if (dz) {
  dz.addEventListener('click',    () => fi && fi.click());
  dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drag'); });
  dz.addEventListener('dragleave',() => dz.classList.remove('drag'));
  dz.addEventListener('drop', e => {
    e.preventDefault(); dz.classList.remove('drag');
    const f = e.dataTransfer?.files?.[0];
    if (f) upload(f);
  });
}
if (selBtn) selBtn.addEventListener('click', e => { e.stopPropagation(); fi && fi.click(); });
if (fi) fi.addEventListener('change', e => { if (e.target.files?.[0]) upload(e.target.files[0]); });

async function upload(file) {
  const card    = $('#uploadCard');
  const fName   = $('#uploadFileName');
  const sTxt    = $('#statusText');
  const spinner = $('#uploadSpinner');
  if (!card) return;

  card.classList.remove('hidden');
  if (fName) fName.textContent = file.name;
  if (sTxt)  sTxt.textContent  = '⏳ Subiendo…';
  if (spinner) spinner.classList.remove('hidden');
  setProgress(0, null);

  const fd = new FormData();
  fd.append('file', file);
  // Whisper language (audio language for transcription)
  if (selectedLang && selectedLang !== 'auto') fd.append('language', selectedLang);
  // UI language → LLM output language
  fd.append('ui_language', window.i18n?.lang || 'es');

  try {
    const res = await fetch(`${API}/api/audio/upload`, { method:'POST', body:fd });
    if (!res.ok) throw new Error(await res.text());
    const job = await res.json();
    if (sTxt) sTxt.textContent = '🔄 Procesando en segundo plano…';
    pollJob(job.id, job.audio_id);
    refreshAudios();
  } catch (err) {
    if (sTxt) sTxt.textContent = `❌ Error: ${err.message}`;
    if (spinner) spinner.classList.add('hidden');
    console.error('[Audial] Upload error:', err);
  }
}

function setProgress(ratio, stage) {
  const bar  = $('#progressBar');
  const ring = $('#ringProgress');
  if (bar)  bar.style.width = `${Math.round(ratio * 100)}%`;
  if (ring) {
    const circ = 339;
    ring.style.strokeDashoffset = String(circ - ratio * circ);
  }
  const order = ['transcription','diarization','llm_analysis','embeddings','done'];
  $$('.stage-step').forEach(s => {
    s.classList.remove('active','done');
    if (!stage) return;
    const cur = order.indexOf(stage), mine = order.indexOf(s.dataset.stage);
    if (cur === mine)    s.classList.add('active');
    else if (mine < cur) s.classList.add('done');
  });
}

function pollJob(jobId, audioId) {
  clearInterval(pollingTimer);
  let attempts = 0;
  const MAX = 400; // ~12 min

  pollingTimer = setInterval(async () => {
    if (++attempts > MAX) {
      clearInterval(pollingTimer);
      const sTxt = $('#statusText');
      if (sTxt) sTxt.textContent = '⏰ Tiempo de espera agotado. Consulta Conversaciones.';
      $('#uploadSpinner')?.classList.add('hidden');
      return;
    }
    try {
      const r = await fetch(`${API}/api/audio/job/${jobId}`);
      if (!r.ok) { clearInterval(pollingTimer); return; }
      const job = await r.json();
      setProgress(job.progress, job.stage);
      const sTxt = $('#statusText');
      const stageLabel = t(`stage.${job.stage}`) || job.stage;
      if (sTxt) sTxt.textContent = `[${stageLabel}] ${job.message || '…'}`;
      console.log(`[Audial] ${jobId.slice(0,8)} | ${job.stage} | ${Math.round(job.progress*100)}% | ${job.message}`);

      if (job.status === 'done' || job.status === 'failed') {
        clearInterval(pollingTimer);
        $('#uploadSpinner')?.classList.add('hidden');
        if (job.status === 'done') {
          if (sTxt) sTxt.textContent = '✅ Procesamiento completo';
          setProgress(1, 'done');
          console.log('[Audial] ✅ Job completado');
          setTimeout(() => openAudio(audioId || job.audio_id), 1200);
        } else {
          if (sTxt) sTxt.textContent = `❌ ${job.message}`;
          console.error('[Audial] Job fallido:', job.message);
        }
        refreshAudios();
        refreshDashboard();
      }
    } catch (e) { console.warn('[Audial] pollJob:', e); }
  }, 1800);
}

/* ============================================================
   CONVERSATIONS
   ============================================================ */
$('#refreshBtn')?.addEventListener('click', refreshAudios);

async function refreshAudios() {
  const list = $('#audioList');
  if (!list) return;
  try {
    const r = await fetch(`${API}/api/audio/`);
    if (!r.ok) throw new Error('API error');
    const data = await r.json();

    const navCnt = $('#navCount');
    if (navCnt) navCnt.textContent = data.length || '';

    const sel = $('#chatAudio');
    if (sel) {
      sel.innerHTML = `<option value="">${t('chat.all')}</option>` +
        data.map(a => `<option value="${a.id}">${esc(a.filename)}</option>`).join('');
    }

    if (!data.length) {
      list.innerHTML = `
        <div class="empty-state">
          <div class="icon"><i data-lucide="music-2"></i></div>
          <h3>${t('conv.empty.title')}</h3>
          <p>${t('conv.empty.desc')}</p>
          <button class="btn btn-primary-gradient mt-3 ripple magnetic" onclick="showPage('upload')">
            <i data-lucide="upload"></i> ${t('conv.empty.cta')}
          </button>
        </div>`;
      refreshIcons(); return;
    }

    list.innerHTML = data.map(a => {
      const canOpen = a.job_status === 'done';
      return `
        <div class="audio-row" onclick="${canOpen ? `openAudio('${a.id}')` : ''}">
          <div class="audio-avatar"><i data-lucide="audio-lines"></i></div>
          <div class="audio-meta">
            <div class="name">${esc(a.filename)}</div>
            <div class="sub">${fmtDur(a.duration_sec)} · ${fmtDate(a.uploaded_at)}</div>
          </div>
          ${getBadge(a.job_status)}
          <button class="btn btn-link text-muted p-1 ms-2" onclick="event.stopPropagation();removeAudio('${a.id}')" title="Eliminar">
            <i data-lucide="trash-2" style="width:16px;height:16px"></i>
          </button>
        </div>`;
    }).join('');
    refreshIcons();
  } catch (e) {
    list.innerHTML = `<div class="empty-state"><p>Error: ${esc(e.message)}</p></div>`;
  }
}

function getBadge(status) {
  const badges = {
    done:    `<span class="badge-pill badge-ok">${t('conv.badge.done')}</span>`,
    running: `<span class="badge-running"><span class="spinner-border" style="width:8px;height:8px;border-width:1px"></span> ${t('conv.badge.running')}</span>`,
    failed:  `<span class="badge-failed">${t('conv.badge.failed')}</span>`,
    pending: `<span class="badge-pending">${t('conv.badge.pending')}</span>`,
  };
  return badges[status] || `<span class="badge-pill" style="background:rgba(255,255,255,.05);color:var(--tx-3)">${esc(status)}</span>`;
}

window.removeAudio = async function(id) {
  if (!confirm('¿Eliminar este audio y su análisis?')) return;
  await fetch(`${API}/api/audio/${id}`, { method:'DELETE' });
  refreshAudios();
  if (id === currentAudioId) showPage('conversations');
};

/* ============================================================
   DETAIL VIEW
   ============================================================ */
window.openAudio = async function(id) {
  if (!id) return;
  currentAudioId = id;
  showPage('detail');

  const titleEl  = $('#detailTitle');
  const headerEl = $('#detailHeader');
  if (titleEl)  titleEl.textContent  = id.slice(0,8) + '…';
  if (headerEl) headerEl.textContent = t('detail.title');

  // Reset primera pestaña
  $$('.tab-btn').forEach(b => b.classList.remove('active'));
  $$('.tab-panel').forEach(p => p.classList.remove('active'));
  const firstTab = $('#detailTabs .tab-btn');
  if (firstTab) firstTab.classList.add('active');
  $('.tab-panel[data-tab="summary"]')?.classList.add('active');

  // Export buttons
  $('#exportJsonBtn') && ($('#exportJsonBtn').onclick = () => window.open(`${API}/api/analysis/${id}/export.json`,'_blank'));
  $('#exportPdfBtn')  && ($('#exportPdfBtn').onclick  = () => window.open(`${API}/api/analysis/${id}/export.pdf`, '_blank'));

  const [aRes, tRes] = await Promise.all([
    fetch(`${API}/api/analysis/${id}`),
    fetch(`${API}/api/analysis/${id}/transcript`),
  ]);

  if (!aRes.ok || !tRes.ok) {
    if (headerEl) headerEl.textContent = '';
    const panel = $('.tab-panel.active');
    if (panel) panel.innerHTML = `
      <div class="detail-unavailable">
        <div style="font-size:48px;margin-bottom:16px">⚠️</div>
        <h3>${t('detail.unavail.title')}</h3>
        <p class="text-muted">${t('detail.unavail.desc')}</p>
        <button class="btn btn-outline-accent mt-3 ripple" onclick="showPage('conversations')">
          <i data-lucide="arrow-left" class="nav-icon"></i> ${t('detail.unavail.back')}
        </button>`;
    refreshIcons(); return;
  }

  const [a, tr] = await Promise.all([aRes.json(), tRes.json()]);
  if (titleEl)  titleEl.textContent  = a.summary_short?.slice(0,50) + (a.summary_short?.length > 50 ? '…' : '') || id.slice(0,8);
  if (headerEl) headerEl.textContent = t('detail.title');

  window._lastAnalysis = a; // cache for lang re-render

  safe(() => renderSummary(a));
  safe(() => renderTranscript(tr));
  safe(() => renderEntities(a.entities));
  safe(() => renderTasks(a.tasks, a.decisions, a.questions));
  safe(() => renderSentiment(a.sentiment, a.conflicts));
  safe(() => renderTopics(a.topics, a.intents));
  safe(() => renderTimeline(a.timeline));
  safe(() => renderMetrics(a.metrics));
  safe(() => loadRelated(id));
  refreshIcons();
};

/* --- TABS: use only CSS animation (class toggle), no GSAP --- */
document.addEventListener('click', e => {
  const btn = e.target.closest('.tab-btn');
  if (!btn?.dataset.tab) return;
  const tab = btn.dataset.tab;
  $$('.tab-btn').forEach(b => b.classList.remove('active'));
  $$('.tab-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  const target = $(`.tab-panel[data-tab="${tab}"]`);
  if (target) target.classList.add('active'); // CSS @keyframes tabReveal handles animation
});

/* ---- renderers ---- */
function renderSummary(a) {
  const s = $('#summaryShort'), m = $('#summaryMedium'), l = $('#summaryLong');
  if (s) s.textContent = a.summary_short  || '–';
  if (m) m.textContent = a.summary_medium || '–';
  if (l) l.textContent = a.summary_long   || '–';
}

function renderTranscript(tr) {
  const list = $('#segmentsList'), cnt = $('#transcriptCount');
  if (!list) return;
  const segs = tr.segments || [];
  const render = filter => {
    const f = filter ? segs.filter(s => s.text?.toLowerCase().includes(filter.toLowerCase())) : segs;
    if (cnt) cnt.textContent = `${f.length} ${t('transcript.count')}`;
    list.innerHTML = f.map(s => `
      <div class="segment-row">
        <span class="seg-time">${fmtDur(s.start)}</span>
        <span class="seg-speaker">${esc(s.speaker || 'SPK_00')}</span>
        <span class="seg-text">${esc(s.text)}</span>
      </div>`).join('');
  };
  render('');
  const srch = $('#transcriptSearch');
  if (srch) srch.oninput = e => render(e.target.value);
}

function renderEntities(ent) {
  const block = $('#entitiesBlock');
  if (!block) return;
  const cats = Object.keys(ent || {});
  if (!cats.length) { block.innerHTML = '<p class="text-muted">–</p>'; return; }
  block.innerHTML = cats.map(k => {
    const items = ent[k] || [];
    const chips = items.map(i => `<span class="entity-chip">${esc(typeof i === 'string' ? i : (i.name||JSON.stringify(i)))}</span>`).join('');
    return `<div class="col-md-4"><div class="entity-group"><div class="entity-group-title">${esc(k)}</div><div>${chips || '<span class="text-muted small">–</span>'}</div></div></div>`;
  }).join('');
}

function renderTasks(tasks, decisions, questions) {
  const empty = msg => `<p class="text-muted small py-2">${msg}</p>`;
  const tl = $('#tasksList'), dl = $('#decisionsList'), ql = $('#questionsList');

  if (tl) tl.innerHTML = (tasks || []).map(t2 => `
    <div class="item-card">
      <div class="item-main">${esc(t2.task || '')}</div>
      <div class="item-meta">
        <span class="meta-pill">👤 ${esc(t2.owner||'–')}</span>
        <span class="meta-pill">📅 ${esc(t2.deadline||'–')}</span>
        <span class="meta-pill" style="color:var(--amber-lt)">${esc(t2.priority||'–')}</span>
      </div>
    </div>`).join('') || empty(t('tasks.empty'));

  if (dl) dl.innerHTML = (decisions || []).map(d => `
    <div class="item-card">
      <div class="item-main">${esc(d.decision||'')}</div>
      <div class="item-meta"><span class="meta-pill">👤 ${esc(d.made_by||'–')}</span></div>
      ${d.rationale ? `<div class="text-muted small mt-1">${esc(d.rationale)}</div>` : ''}
    </div>`).join('') || empty(t('decisions.empty'));

  if (ql) ql.innerHTML = (questions || []).map(q => `
    <div class="item-card">
      <div class="item-main">${esc(q.question||'')}</div>
      <div class="item-meta">
        <span class="meta-pill">👤 ${esc(q.asked_by||'–')}</span>
        <span class="meta-pill" style="color:${q.answered?'var(--emerald-lt)':'var(--tx-3)'}">${q.answered?'✓':'✗'}</span>
      </div>
    </div>`).join('') || empty(t('questions.empty'));
}

function renderSentiment(s, conflicts) {
  destroyChart('sentEvo'); destroyChart('sentSpk');
  const evo = s?.evolution || [], per = s?.per_speaker || [];
  const base = baseOpts();

  const evoEl = $('#sentimentEvolutionChart');
  if (evoEl) charts.sentEvo = new Chart(evoEl, {
    type:'line',
    data:{ labels: evo.map((e,i) => `seg ${e.segment??i}`),
      datasets:[{ label:'Sentiment', data: evo.map(e => e.score),
        borderColor:'#F5A623', backgroundColor:'rgba(245,166,35,.12)', fill:true, tension:.35, pointRadius:3, pointBackgroundColor:'#F5A623' }]},
    options:{ ...base, scales:{ y:{...base.scales.y,min:-1,max:1}, x:base.scales.x }, plugins:{ legend:{display:false} } }
  });

  const spkEl = $('#sentimentSpeakerChart');
  if (spkEl) charts.sentSpk = new Chart(spkEl, {
    type:'bar',
    data:{ labels: per.map(p => p.speaker),
      datasets:[{ data: per.map(p => p.score),
        backgroundColor: per.map(p => p.score >= 0 ? 'rgba(106,176,76,.7)' : 'rgba(232,90,79,.7)'), borderRadius:8 }]},
    options:{ ...base, scales:{ y:{...base.scales.y,min:-1,max:1}, x:base.scales.x }, plugins:{ legend:{display:false} } }
  });

  const cb = $('#conflictsBlock'); if (!cb) return;
  const confs = conflicts || [];
  if (!confs.length) { cb.innerHTML = `<p class="text-muted small mt-3">${t('sentiment.empty')}</p>`; return; }
  cb.innerHTML = `<h5 class="mt-4 mb-3" style="font-family:Fraunces,serif">${t('conflicts.title')}</h5>` +
    confs.map(c => `
    <div class="conflict-card">
      <div class="conflict-header">
        <span class="conflict-severity">Sev. ${c.severity??'?'}</span>
        <span class="conflict-topic">${esc(c.topic||'')}</span>
        <span class="text-muted small">${esc((c.parties||[]).join(' vs '))}</span>
      </div>
      <div class="text-muted small fst-italic">"${esc(c.evidence||'')}"</div>
    </div>`).join('');
}

function renderTopics(topics, intents) {
  const tl = $('#topicsList'), il = $('#intentsList');
  if (tl) tl.innerHTML = (topics||[]).map(tp => `
    <div class="topic-card">
      <div class="topic-header">
        <span class="topic-name">${esc(tp.topic||'?')}</span>
        <span class="topic-range">seg ${tp.start_idx??'?'}–${tp.end_idx??'?'}</span>
      </div>
      <div class="text-muted small">${esc(tp.summary||'')}</div>
    </div>`).join('') || `<p class="text-muted small">${t('topics.empty')}</p>`;

  if (il) il.innerHTML = (intents||[]).map(i => `
    <div class="item-card">
      <div class="item-main">${esc(i.intent||'?')}</div>
      <div class="item-meta"><span class="meta-pill">${Math.round((i.confidence??0)*100)}%</span></div>
      ${i.evidence ? `<div class="text-muted small fst-italic mt-1">"${esc(i.evidence)}"</div>` : ''}
    </div>`).join('') || `<p class="text-muted small">${t('intents.empty')}</p>`;
}

function renderTimeline(items) {
  const tl = $('#timelineList'); if (!tl) return;
  if (!items?.length) { tl.innerHTML = `<p class="text-muted small">${t('timeline.empty')}</p>`; return; }
  tl.innerHTML = items.map(e => {
    const stars = '★'.repeat(Math.min(e.importance||1, 5));
    return `<div class="tl-item">
      <div class="tl-time">${esc(e.time||'–')}</div>
      <div class="tl-dot-col"><div class="tl-dot"></div><div class="tl-line"></div></div>
      <div class="tl-content">
        <div class="tl-event">${esc(e.event||'')} <span class="tl-imp">${stars}</span></div>
        ${e.speaker ? `<div class="tl-speaker">${esc(e.speaker)}</div>` : ''}
      </div>
    </div>`;
  }).join('');
}

function renderMetrics(m) {
  const stats = $('#metricsStats'); if (!stats || !m) return;
  stats.innerHTML = [
    [t('metrics.duration'),  fmtDur(m.total_duration_sec)],
    [t('metrics.segments'),  m.num_segments],
    [t('metrics.speakers'),  m.num_speakers],
    [t('metrics.avg'),       `${m.avg_segment_sec??'–'}s`],
    [t('metrics.wpm'),       m.words_per_minute],
  ].map(([k,v]) => `
    <div class="metric-row">
      <span class="metric-key">${esc(k)}</span>
      <span class="metric-val">${esc(String(v??'–'))}</span>
    </div>`).join('');

  destroyChart('part');
  const part = m.participation_pct || {};
  const partEl = $('#participationChart');
  if (partEl && Object.keys(part).length) {
    charts.part = new Chart(partEl, {
      type:'doughnut',
      data:{ labels:Object.keys(part), datasets:[{ data:Object.values(part),
        backgroundColor:['#F5A623','#E85A4F','#6AB04C','#4FC3F7','#B084F0','#FFC95A'], borderWidth:2, borderColor:'#0e0c1a' }]},
      options:{ responsive:true, plugins:{ legend:{ position:'right', labels:{ color:'#AEA290', boxWidth:12, font:{size:11} } } }, cutout:'62%' }
    });
  }
}

async function loadRelated(id) {
  const rl = $('#relatedList'); if (!rl) return;
  try {
    const r = await fetch(`${API}/api/dashboard/related/${id}`);
    const items = r.ok ? await r.json() : [];
    if (!items.length) { rl.innerHTML = `<p class="text-muted small">${t('related.empty')}</p>`; return; }
    rl.innerHTML = items.map(x => `
      <div class="related-card" onclick="openAudio('${x.audio_id}')">
        <span class="related-score">${(x.score*100).toFixed(0)}%</span>
        <span class="text-muted small" style="flex:1">${esc(x.excerpt)}</span>
        <i data-lucide="arrow-right" style="color:var(--tx-3);width:16px;height:16px"></i>
      </div>`).join('');
    refreshIcons();
  } catch {}
}

function destroyChart(k) { if (charts[k]) { try { charts[k].destroy(); } catch {} delete charts[k]; } }

function baseOpts() {
  return {
    responsive:true, maintainAspectRatio:false,
    scales:{
      y:{ grid:{ color:'rgba(255,255,255,.05)' }, ticks:{ color:'#AEA290', font:{size:11} } },
      x:{ grid:{ color:'rgba(255,255,255,.04)' }, ticks:{ color:'#AEA290', font:{size:11}, maxTicksLimit:8 } }
    }
  };
}

/* ============================================================
   DASHBOARD
   ============================================================ */
async function refreshDashboard() {
  try {
    const r = await fetch(`${API}/api/dashboard/overview`);
    if (!r.ok) return;
    const d = await r.json();

    const kpiRow = $('#kpiRow');
    if (kpiRow) {
      const items = [
        { n:d.total_audios??0,          l:t('dashboard.kpi.audios'),   icon:'music-2' },
        { n:d.total_analyses??0,        l:t('dashboard.kpi.analyses'), icon:'check-circle-2' },
        { n:d.total_duration_hours??0,  l:t('dashboard.kpi.hours'),    icon:'clock', suf:'h' },
        { n:d.totals?.tasks??0,         l:t('dashboard.kpi.tasks'),    icon:'list-checks' },
      ];
      kpiRow.innerHTML = items.map(it => `
        <div class="col-md-6 col-lg-3">
          <div class="kpi-tile reveal">
            <div class="kpi-icon"><i data-lucide="${it.icon}"></i></div>
            <div class="kpi-n" data-target="${it.n}" data-suf="${it.suf||''}">0</div>
            <div class="kpi-l">${esc(it.l)}</div>
          </div>
        </div>`).join('');
      refreshIcons();
      animateCounters();
    }

    destroyChart('gs');
    const sd = d.sentiment_distribution || {};
    const gsEl = $('#globalSentimentChart');
    if (gsEl) charts.gs = new Chart(gsEl, {
      type:'doughnut',
      data:{ labels:Object.keys(sd).length ? Object.keys(sd) : ['–'], datasets:[{
        data:Object.values(sd).length ? Object.values(sd) : [1],
        backgroundColor:['#6AB04C','#AEA290','#E85A4F','#F5A623'], borderWidth:2, borderColor:'#0e0c1a' }]},
      options:{ responsive:true, plugins:{ legend:{ position:'right', labels:{ color:'#AEA290',boxWidth:12,font:{size:11} } } }, cutout:'62%' }
    });

    destroyChart('tt');
    const tot = d.totals||{};
    const ttEl = $('#totalsChart');
    if (ttEl) charts.tt = new Chart(ttEl, {
      type:'bar',
      data:{ labels:['Tareas','Decisiones','Conflictos'], datasets:[{
        data:[tot.tasks??0, tot.decisions??0, tot.conflicts??0],
        backgroundColor:['#F5A623','#6AB04C','#E85A4F'], borderRadius:8, borderWidth:0 }]},
      options:{ ...baseOpts(), plugins:{ legend:{display:false} } }
    });
  } catch (e) { console.warn('[Audial] dashboard:', e); }
}

function animateCounters() {
  $$('.kpi-n[data-target]').forEach(el => {
    const target = parseFloat(el.dataset.target) || 0;
    const suf    = el.dataset.suf || '';
    const isInt  = Number.isInteger(target);
    const dur    = 900, start = performance.now();
    const tick = now => {
      const p = Math.min((now - start) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = (isInt ? Math.round(target*eased) : (target*eased).toFixed(1)) + suf;
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

/* ============================================================
   CHAT
   ============================================================ */
$('#chatForm')?.addEventListener('submit', async e => {
  e.preventDefault();
  const input = $('#chatInput'), sel = $('#chatAudio');
  const msg = input?.value?.trim(); if (!msg) return;
  appendMsg('user', msg);
  if (input) input.value = '';

  const typing = appendTyping();
  try {
    const r = await fetch(`${API}/api/chat`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ message:msg, audio_id:sel?.value||null, top_k:5 })
    });
    const data = await r.json(); typing.remove();
    appendMsg('bot', r.ok ? (data.answer||'…') : `⚠️ ${data.detail||'Error'}`, r.ok ? data.sources : []);
  } catch { typing.remove(); appendMsg('bot','⚠️ Error de conexión.'); }
});

window.useSuggestion = function(btn) {
  const input = $('#chatInput');
  if (input) { input.value = btn.textContent.trim(); input.focus(); }
};

function appendMsg(role, text, sources = []) {
  const log = $('#chatLog'); if (!log) return;
  log.querySelector('.chat-welcome')?.remove();
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.innerHTML = esc(text).replace(/\n/g,'<br>');
  if (sources?.length) {
    const s = document.createElement('div');
    s.className = 'msg-sources';
    s.textContent = 'Fuentes: ' + sources.slice(0,5).map(x => `seg ${x.segment_idx} (${x.score})`).join(' · ');
    div.appendChild(s);
  }
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function appendTyping() {
  const log = $('#chatLog'); if (!log) return { remove:()=>{} };
  const div = document.createElement('div');
  div.className = 'msg bot';
  div.innerHTML = `<span class="tw"><span class="td"></span><span class="td"></span><span class="td"></span></span>`;
  log.appendChild(div); log.scrollTop = log.scrollHeight;
  return div;
}

// Inject typing CSS
(()=>{ const s=document.createElement('style');
  s.textContent=`.tw{display:inline-flex;gap:5px;align-items:center;height:18px}.td{width:7px;height:7px;background:var(--tx-2);border-radius:50%;animation:td 1.2s infinite ease-in-out}.td:nth-child(2){animation-delay:.2s}.td:nth-child(3){animation-delay:.4s}@keyframes td{0%,80%,100%{opacity:.3;transform:scale(.7)}40%{opacity:1;transform:scale(1)}}`;
  document.head.appendChild(s);
})();

/* ============================================================
   BOOT
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  refreshIcons();
  refreshAudios();
  refreshDashboard();
  setInterval(refreshDashboard, 30000);
});
