/* ============================================================
   Audial · app.js
   Custom cursor · Scroll progress · IntersectionObserver reveals
   Magnetic buttons · Ripple · 3D Tilt · Parallax blobs
   Tab fix (CSS-only, no GSAP for opacity)
   ============================================================ */

const API = (window.AUDIAL_API || '').replace(/\/$/, '');

// ── Auth state ────────────────────────────────────────────────────────
let _authToken = localStorage.getItem('audial_token') || null;
let _authUser  = JSON.parse(localStorage.getItem('audial_user') || 'null');

function _setAuth(token, user) {
  _authToken = token; _authUser = user;
  if (token) { localStorage.setItem('audial_token', token); localStorage.setItem('audial_user', JSON.stringify(user)); }
  else { localStorage.removeItem('audial_token'); localStorage.removeItem('audial_user'); }
  _updateUserNav();
}

function _updateUserNav() {
  const avatar = $('#userAvatar'), nameEl = $('#userNavName'), emailEl = $('#userMenuEmail');
  const adminItem = $('#navAdminItem');
  if (_authUser) {
    if (avatar) avatar.textContent = (_authUser.display_name || _authUser.email || '?')[0].toUpperCase();
    if (nameEl)  nameEl.textContent = _authUser.display_name || _authUser.email || '';
    if (emailEl) emailEl.textContent = _authUser.email || '';
    // Mostrar nav Admin solo para owner/admin
    const isAdmin = _authUser.role === 'owner' || _authUser.role === 'admin';
    adminItem?.classList.toggle('hidden', !isAdmin);
  } else {
    if (avatar)  avatar.textContent = '?';
    if (nameEl)  nameEl.textContent = t('auth.guest.short');
    if (emailEl) emailEl.textContent = '';
    adminItem?.classList.add('hidden');
  }
}

// Intercept fetch: add auth header + session ID; auto-clear token on 401
const _fetch = window.fetch.bind(window);
window.fetch = async function(url, opts = {}) {
  if (typeof url === 'string' && (url.startsWith(API + '/api') || url.startsWith('/api'))) {
    const headers = { ...(opts.headers || {}), 'X-Session-ID': window.AUDIAL_SESSION || '' };
    if (_authToken) headers['Authorization'] = `Bearer ${_authToken}`;
    opts.headers = headers;
  }
  const response = await _fetch(url, opts);
  // Si el servidor responde 401, el token es inválido (usuario eliminado o BD reseteada)
  if (response.status === 401 && _authToken) {
    console.warn('[Audial] Token inválido o usuario no encontrado, limpiando sesión');
    _setAuth(null, null);
    // Recargar datos como invitado
    setTimeout(() => { refreshAudios(); refreshDashboard(); }, 100);
  }
  return response;
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
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function fmtSpeaker(spk) {
  if (!spk) return t('transcript.speaker') + ' 1';
  const m = spk.match(/(\d+)$/);
  if (m) return t('transcript.speaker') + ' ' + (parseInt(m[1]) + 1);
  return spk;
}
// Map LLM entity keys (Spanish or English) → display label in current UI language
function fmtEntityKey(k) {
  const map = {
    'personas': t('entities.personas'), 'people': t('entities.personas'), 'persons': t('entities.personas'),
    'empresas': t('entities.empresas'), 'companies': t('entities.empresas'), 'organizations': t('entities.empresas'),
    'lugares':  t('entities.lugares'),  'places':  t('entities.lugares'),  'locations': t('entities.lugares'),
    'fechas':   t('entities.fechas'),   'dates':   t('entities.fechas'),
    'productos':t('entities.productos'),'products':t('entities.productos'),
    'tareas':   t('entities.tareas'),   'tasks':   t('entities.tareas'),
  };
  return map[k.toLowerCase()] || k.charAt(0).toUpperCase() + k.slice(1);
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

  // Ocultar hasta el primer mousemove para no aparecer en (0,0)
  dot.style.opacity  = '0';
  ring.style.opacity = '0';

  let rx = 0, ry = 0;
  let cx = 0, cy = 0;
  let _moved = false;

  document.addEventListener('mousemove', e => {
    cx = e.clientX; cy = e.clientY;
    dot.style.left = cx + 'px';
    dot.style.top  = cy + 'px';
    if (!_moved) {
      _moved = true;
      rx = cx; ry = cy; // snap del ring a la posición real
      dot.style.opacity  = '';
      ring.style.opacity = '';
    }
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
  _updateUserNav();   // restaurar nombre de usuario tras traducción
  refreshIcons();

  // Re-render dynamic content on the currently visible page
  const activePage = document.querySelector('.page.active');
  const pageId = activePage?.id || '';

  if (pageId === 'page-conversations') {
    refreshAudios();
  } else if (pageId === 'page-dashboard') {
    refreshDashboard();
  } else if (pageId === 'page-detail' && currentAudioId) {
    const newLang = window.i18n?.lang || 'es';
    translateAndRender(currentAudioId, newLang);
    const cnt = $('#transcriptCount');
    if (cnt) { const n = $$('.segment-row').length; if (n) cnt.textContent = `${n} ${t('transcript.count')}`; }
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
  if (name === 'admin')         { adminLoadOverview(); adminSwitchTab('overview'); }

  // Forzar visibilidad de .reveal en la página activa (evita opacity:0 persistente)
  setTimeout(() => {
    $$('.page.active .reveal').forEach(el => el.classList.add('visible'));
  }, 80);

  i18n.applyTranslations();
  _updateUserNav();   // restaurar nombre de usuario (applyTranslations puede sobreescribirlo)
  refreshIcons();
};

function _closeNavbar() {
  const nc = document.getElementById('navMain');
  if (nc && window.bootstrap) bootstrap.Collapse.getInstance(nc)?.hide();
}

$$('.nav-pill').forEach(a => {
  if (a.dataset.page) {
    a.addEventListener('click', e => {
      e.preventDefault();
      showPage(a.dataset.page);
      _closeNavbar(); // cerrar menú móvil al navegar
    });
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
      const stored  = a.job_stage === 'stored';           // guardado (p. ej. desde la app) sin analizar
      const title   = a.contact_name || a.filename;
      const callIcon = a.call_type === 'incoming' ? '↙ ' : a.call_type === 'outgoing' ? '↗ ' : '';
      const when    = a.call_started_at || a.uploaded_at;
      const analyzeBtn = stored
        ? `<button class="btn btn-outline-accent btn-sm" onclick="event.stopPropagation();analyzeAudio('${a.id}')">
             <i data-lucide="sparkles" class="nav-icon"></i> ${window.i18n?.lang === 'en' ? 'Analyze' : 'Analizar'}
           </button>`
        : '';
      const guestBadge = a.is_guest
        ? `<span class="badge-guest" title="Se eliminará automáticamente en 24h">⏱ temporal</span>`
        : '';
      return `
        <div class="audio-row" onclick="${canOpen ? `openAudio('${a.id}')` : ''}">
          <div class="audio-avatar"><i data-lucide="audio-lines"></i></div>
          <div class="audio-meta">
            <div class="name">${callIcon}${esc(title)}</div>
            <div class="sub">${a.phone_number && a.phone_number !== title ? esc(a.phone_number) + ' · ' : ''}${fmtDur(a.duration_sec)} · ${fmtDate(when)}</div>
          </div>
          <div class="audio-actions">
            ${analyzeBtn}
            ${getBadge(a.job_status, a.job_stage)}
            ${guestBadge}
            <button class="btn btn-link text-muted p-1" onclick="event.stopPropagation();renameAudio('${a.id}','${esc(a.filename)}')" title="${t('audio.rename')}">
              <i data-lucide="pencil" style="width:15px;height:15px"></i>
            </button>
            <button class="btn btn-link text-muted p-1" onclick="event.stopPropagation();removeAudio('${a.id}')" title="${t('audio.delete')}">
              <i data-lucide="trash-2" style="width:15px;height:15px"></i>
            </button>
          </div>
        </div>`;
    }).join('');
    refreshIcons();
  } catch (e) {
    list.innerHTML = `<div class="empty-state"><p>Error: ${esc(e.message)}</p></div>`;
  }
}

window.analyzeAudio = async function(id) {
  const r = await fetch(`${API}/api/audio/${id}/analyze`, {
    method: 'POST', body: new URLSearchParams({ ui_language: window.i18n?.lang || 'es' }),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    alert(typeof d.detail === 'string' ? d.detail : 'No se pudo iniciar el análisis');
  }
  refreshAudios();
};

function getBadge(status, stage) {
  if (stage === 'stored') {
    const txt = window.i18n?.lang === 'en' ? 'Not analyzed' : 'Sin analizar';
    return `<span class="badge-pill" style="background:rgba(255,255,255,.06);color:var(--tx-2)">${txt}</span>`;
  }
  const badges = {
    done:    `<span class="badge-pill badge-ok">${t('conv.badge.done')}</span>`,
    running: `<span class="badge-running"><span class="spinner-border" style="width:8px;height:8px;border-width:1px"></span> ${t('conv.badge.running')}</span>`,
    failed:  `<span class="badge-failed">${t('conv.badge.failed')}</span>`,
    pending: `<span class="badge-pending">${t('conv.badge.pending')}</span>`,
  };
  return badges[status] || `<span class="badge-pill" style="background:rgba(255,255,255,.05);color:var(--tx-3)">${esc(status)}</span>`;
}

window.removeAudio = async function(id) {
  if (!confirm(t('audio.confirm.delete'))) return;
  await fetch(`${API}/api/audio/${id}`, { method:'DELETE' });
  refreshAudios();
  if (id === currentAudioId) showPage('conversations');
};

window.reuploadAudio = async function(id, warnEl) {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.mp3,.wav,.m4a,.ogg,.flac';
  input.onchange = async e => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (warnEl) warnEl.innerHTML = `<span style="color:var(--tx-2);font-size:13px">⏳ ${t('audio.reuploading')}</span>`;
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await fetch(`${API}/api/audio/${id}/reupload`, { method: 'POST', body: fd });
      if (!r.ok) throw new Error(await r.text());
      // Restaurar el reproductor
      const playerBar = $('#audioPlayerBar');
      if (playerBar && warnEl) {
        const audio = document.createElement('audio');
        audio.id = 'audioPlayer';
        audio.controls = true;
        audio.preload = 'none';
        audio.className = 'audio-player-ctrl';
        audio.innerHTML = `<source id="audioPlayerSrc" src="${API}/api/audio/${id}/file" />`;
        warnEl.replaceWith(audio);
        audio.load();
      }
    } catch (err) {
      if (warnEl) warnEl.innerHTML = `<span style="color:var(--tx-3);font-size:13px">❌ ${esc(err.message)}</span>`;
    }
  };
  input.click();
};

// ── Rename Modal ──────────────────────────────────────────────────────
let _renameBsModal = null;
let _renameTargetId = null;
let _renameOldName  = null;

window.renameAudio = function(id, currentName) {
  _renameTargetId = id;
  _renameOldName  = currentName;
  const input = document.getElementById('renameInput');
  const errEl = document.getElementById('renameError');
  if (input) { input.value = currentName; }
  if (errEl) errEl.classList.add('hidden');
  if (!_renameBsModal && window.bootstrap) {
    const el = document.getElementById('renameModal');
    if (el) _renameBsModal = new bootstrap.Modal(el);
  }
  _renameBsModal?.show();
  setTimeout(() => { const inp = document.getElementById('renameInput'); inp?.focus(); inp?.select(); }, 350);
};

async function _submitRename() {
  const newName = document.getElementById('renameInput')?.value?.trim();
  const errEl   = document.getElementById('renameError');
  if (!newName) {
    if (errEl) { errEl.textContent = t('audio.rename.required'); errEl.classList.remove('hidden'); }
    return;
  }
  const btn = document.getElementById('renameSubmitBtn');
  if (btn) btn.disabled = true;
  try {
    const r = await fetch(`${API}/api/audio/${_renameTargetId}/rename`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: newName }),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      if (errEl) { errEl.textContent = d.detail || 'Error'; errEl.classList.remove('hidden'); }
      return;
    }
    _renameBsModal?.hide();
    refreshAudios();
    if (currentAudioId === _renameTargetId) {
      const pName = $('#audioPlayerName');
      if (pName) pName.textContent = newName;
    }
  } catch (e) {
    if (errEl) { errEl.textContent = e.message; errEl.classList.remove('hidden'); }
  } finally {
    if (btn) btn.disabled = false;
  }
}

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

  // Audio player
  const playerBar  = $('#audioPlayerBar');
  const playerSrc  = $('#audioPlayerSrc');
  const playerName = $('#audioPlayerName');
  const player     = $('#audioPlayer');
  if (playerBar && playerSrc && player) {
    playerSrc.src = `${API}/api/audio/${id}/file`;
    player.load();
    if (playerName) playerName.textContent = id.slice(0,8) + '…';
    playerBar.style.display = 'flex';
    // Handle missing file (HF Spaces ephemeral storage wipe on restart)
    player.onerror = () => {
      const warn = document.createElement('div');
      warn.className = 'audio-unavail';
      warn.style.cssText = 'display:flex;align-items:center;gap:8px;padding:8px 12px;color:var(--tx-3);font-size:13px;flex-wrap:wrap';
      warn.innerHTML = `<i data-lucide="file-x" style="width:15px;height:15px;flex-shrink:0"></i><span>${t('audio.file.unavail')}</span>
        <button class="btn btn-sm btn-outline-accent ms-2" style="font-size:11px;padding:3px 10px"
          onclick="reuploadAudio('${id}',this.closest('.audio-unavail'))">
          <i data-lucide="upload" style="width:12px;height:12px"></i> ${t('audio.reupload')}
        </button>`;
      player.replaceWith(warn);
      refreshIcons();
    };
  }

  // Pasar idioma UI para obtener análisis Y transcript en el idioma correcto
  const uiLang = window.i18n?.lang || 'es';
  const [aRes, tRes] = await Promise.all([
    fetch(`${API}/api/analysis/${id}?lang=${uiLang}`),
    fetch(`${API}/api/analysis/${id}/transcript?lang=${uiLang}`),
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
  const titleText = (a.summary_short || '').slice(0, 50) + (a.summary_short?.length > 50 ? '…' : '');
  if (titleEl)  titleEl.textContent  = titleText || id.slice(0, 8);
  if (headerEl) headerEl.textContent = t('detail.title');

  // Actualizar nombre en el reproductor
  const audioInfo = await fetch(`${API}/api/audio/${id}`).then(r => r.ok ? r.json() : null).catch(() => null);
  const pName = $('#audioPlayerName');
  if (pName && audioInfo?.filename) {
    pName.textContent = audioInfo.filename;
    // Breadcrumb muestra el nombre del audio, no el resumen del análisis
    if (titleEl) titleEl.textContent = audioInfo.filename.length > 45
      ? audioInfo.filename.slice(0, 45) + '…'
      : audioInfo.filename;
    // Add rename button next to filename if not already there
    let rBtn = document.getElementById('playerRenameBtn');
    if (!rBtn) {
      rBtn = document.createElement('button');
      rBtn.id = 'playerRenameBtn';
      rBtn.className = 'btn btn-link text-muted p-0 ms-2';
      rBtn.title = t('audio.rename');
      rBtn.style.cssText = 'vertical-align:middle;line-height:1';
      rBtn.innerHTML = '<i data-lucide="pencil" style="width:13px;height:13px"></i>';
      pName.parentElement?.insertBefore(rBtn, pName.nextSibling);
    }
    rBtn.onclick = () => renameAudio(id, pName.textContent);
    refreshIcons();
  }

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
        <span class="seg-speaker">${esc(fmtSpeaker(s.speaker))}</span>
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
    return `<div class="col-md-4"><div class="entity-group"><div class="entity-group-title">${esc(fmtEntityKey(k))}</div><div>${chips || '<span class="text-muted small">–</span>'}</div></div></div>`;
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

  // Global sentiment badge (always shown when available)
  const globalBadgeId = 'sentimentGlobalBadge';
  let existingBadge = document.getElementById(globalBadgeId);
  if (existingBadge) existingBadge.remove();
  if (s?.global?.label) {
    const sentPanel = $('.tab-panel[data-tab="sentiment"]');
    if (sentPanel) {
      const badge = document.createElement('div');
      badge.id = globalBadgeId;
      badge.style.cssText = 'margin-bottom:16px';
      const lbl = s.global.label;
      const score = s.global.score != null ? Math.round(Math.abs(s.global.score) * 100) : null;
      const color = lbl === 'positive' || lbl === 'positivo' ? '#39FF14' :
                    lbl === 'negative' || lbl === 'negativo' ? '#FF5252' : '#8DA88D';
      badge.innerHTML = `<span style="display:inline-flex;align-items:center;gap:8px;padding:6px 14px;border-radius:20px;background:rgba(255,255,255,.06);font-size:13px;color:${color};font-weight:600;text-transform:capitalize">${lbl}${score != null ? ` &nbsp;·&nbsp; ${score}%` : ''}</span>`;
      sentPanel.insertBefore(badge, sentPanel.firstChild);
    }
  }

  const evoEl = $('#sentimentEvolutionChart');
  if (evoEl) charts.sentEvo = new Chart(evoEl, {
    type:'line',
    data:{ labels: evo.map((e,i) => `seg ${e.segment??i}`),
      datasets:[{ label:'Sentiment', data: evo.map(e => e.score),
        borderColor:'#39FF14', backgroundColor:'rgba(245,166,35,.12)', fill:true, tension:.35, pointRadius:3, pointBackgroundColor:'#39FF14' }]},
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
        backgroundColor:['#39FF14','#00E5CC','#00C853','#4FC3F7','#B084F0','#FFC95A'], borderWidth:2, borderColor:'#0e0c1a' }]},
      options:{ responsive:true, plugins:{ legend:{ position:'right', labels:{ color:'#8DA88D', boxWidth:12, font:{size:11} } } }, cutout:'62%' }
    });
  }
}

async function loadRelated(id) {
  const rl = $('#relatedList'); if (!rl) return;
  try {
    const r = await fetch(`${API}/api/dashboard/related/${id}`);
    const items = r.ok ? await r.json() : [];
    if (!items.length) {
      rl.innerHTML = `<p class="text-muted small">${t('related.empty')}</p>`;
      return;
    }
    rl.innerHTML = items.map(x => `
      <div class="related-card" onclick="openAudio('${x.audio_id}')">
        <span class="related-score">${(x.score*100).toFixed(0)}%</span>
        <span class="text-muted small" style="flex:1">${esc(x.excerpt)}</span>
        <i data-lucide="arrow-right" style="color:var(--tx-3);width:16px;height:16px"></i>
      </div>`).join('');
    refreshIcons();
  } catch {
    const rl2 = $('#relatedList');
    if (rl2) rl2.innerHTML = `<p class="text-muted small">${t('related.empty')}</p>`;
  }
}

function destroyChart(k) { if (charts[k]) { try { charts[k].destroy(); } catch {} delete charts[k]; } }

function baseOpts() {
  return {
    responsive:true, maintainAspectRatio:false,
    scales:{
      y:{ grid:{ color:'rgba(255,255,255,.05)' }, ticks:{ color:'#8DA88D', font:{size:11} } },
      x:{ grid:{ color:'rgba(255,255,255,.04)' }, ticks:{ color:'#8DA88D', font:{size:11}, maxTicksLimit:8 } }
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
          <div class="kpi-tile">
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
        backgroundColor:['#00C853','#8DA88D','#00E5CC','#39FF14'], borderWidth:2, borderColor:'#0e0c1a' }]},
      options:{ responsive:true, plugins:{ legend:{ position:'right', labels:{ color:'#8DA88D',boxWidth:12,font:{size:11} } } }, cutout:'62%' }
    });

    destroyChart('tt');
    const tot = d.totals||{};
    const ttEl = $('#totalsChart');
    if (ttEl) charts.tt = new Chart(ttEl, {
      type:'bar',
      data:{ labels:[t('dashboard.chart.tasks'), t('dashboard.chart.decisions'), t('dashboard.chart.conflicts')], datasets:[{
        data:[tot.tasks??0, tot.decisions??0, tot.conflicts??0],
        backgroundColor:['#39FF14','#00C853','#00E5CC'], borderRadius:8, borderWidth:0 }]},
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
    s.textContent = t('chat.sources') + ': ' + sources.slice(0,5).map(x => `seg ${x.segment_idx} (${x.score})`).join(' · ');
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
   AUTH — Login / Register / Logout / Google OAuth
   ============================================================ */
let _authModal = null;

function _getAuthModal() {
  if (!_authModal && window.bootstrap) {
    const el = document.getElementById('authModal');
    if (el) _authModal = new bootstrap.Modal(el, { backdrop: 'static' });
  }
  return _authModal;
}

function _switchAuthTab(tab) {
  $$('.auth-tab').forEach(b => b.classList.remove('active'));
  $(`#tab${tab[0].toUpperCase() + tab.slice(1)}`)?.classList.add('active');
  $('#loginForm')?.classList.toggle('hidden', tab !== 'login');
  $('#registerForm')?.classList.toggle('hidden', tab !== 'register');
}

function _continueAsGuest() {
  localStorage.setItem('audial_auth_dismissed', '1');
  _setAuth(null, null);
  _getAuthModal()?.hide();
  refreshAudios();
}

async function _doLogin(e) {
  e?.preventDefault();
  const errEl = $('#loginError');
  errEl?.classList.add('hidden');
  try {
    const r = await _fetch(`${API}/api/auth/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: $('#loginEmail')?.value || '', password: $('#loginPassword')?.value || '' }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Error');
    _setAuth(data.token, { email: data.email, display_name: data.display_name, role: data.role || 'user' });
    _getAuthModal()?.hide();
    refreshAudios(); refreshDashboard();
  } catch (err) {
    if (errEl) { errEl.textContent = err.message; errEl.classList.remove('hidden'); }
  }
}

let _pendingVerifyEmail = '';

async function _doRegister(e) {
  e?.preventDefault();
  const errEl = $('#registerError');
  if (errEl) errEl.classList.add('hidden');

  const pwd  = $('#regPassword')?.value || '';
  const pwd2 = $('#regPasswordConfirm')?.value || '';
  if (pwd !== pwd2) {
    if (errEl) { errEl.textContent = t('auth.passwords_mismatch'); errEl.classList.remove('hidden'); }
    return;
  }
  if (pwd.length < 6) {
    if (errEl) { errEl.textContent = t('auth.password_short'); errEl.classList.remove('hidden'); }
    return;
  }

  const email = $('#regEmail')?.value?.trim() || '';
  try {
    const r = await _fetch(`${API}/api/auth/register`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password: pwd, display_name: $('#regName')?.value?.trim() || '' }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Error');

    // Siempre mostramos el paso de verificación por código
    _pendingVerifyEmail = email;
    $('#registerForm')?.classList.add('hidden');
    $('#verifyCodeStep')?.classList.remove('hidden');
    $$('.auth-tab').forEach(b => b.classList.remove('active'));

    const descEl = $('#verifyCodeDesc');
    const devDisplay = $('#devCodeDisplay');
    const devCodeVal = $('#devCodeValue');
    if (data.email_sent) {
      if (descEl) descEl.textContent = t('auth.code_sent_email');
      devDisplay?.classList.add('hidden');
    } else {
      if (descEl) descEl.textContent = t('auth.code_screen');
      if (devDisplay && data.dev_code) {
        if (devCodeVal) devCodeVal.textContent = data.dev_code;
        devDisplay.classList.remove('hidden');
      }
    }
    $('#verifyCodeInput')?.focus();
  } catch (err) {
    if (errEl) { errEl.textContent = err.message; errEl.classList.remove('hidden'); }
  }
}

async function _doVerifyCode() {
  const code  = $('#verifyCodeInput')?.value?.trim() || '';
  const errEl = $('#verifyError');
  if (errEl) errEl.classList.add('hidden');
  if (!code || code.length !== 6) return;
  try {
    const r = await _fetch(`${API}/api/auth/verify-code`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: _pendingVerifyEmail, code }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || t('auth.code_invalid'));
    _setAuth(data.token, { email: data.email, display_name: data.display_name, is_verified: true });
    _getAuthModal()?.hide();
    refreshAudios(); refreshDashboard();
  } catch (err) {
    if (errEl) { errEl.textContent = err.message; errEl.classList.remove('hidden'); }
  }
}

function _doLogout() {
  _setAuth(null, null);
  localStorage.removeItem('audial_auth_dismissed');
  $('#userMenu')?.classList.add('hidden');
  refreshAudios(); refreshDashboard();
}

function _toggleUserMenu() {
  const menu = $('#userMenu');
  if (!menu) return;
  if (_authUser) {
    menu.classList.toggle('hidden');
    setTimeout(() => {
      const handler = ev => {
        if (!document.getElementById('userNavItem')?.contains(ev.target)) {
          menu.classList.add('hidden');
          document.removeEventListener('click', handler);
        }
      };
      document.addEventListener('click', handler);
    }, 50);
  } else {
    _getAuthModal()?.show();
  }
}

// Forgot password
async function _doForgotPassword() {
  const email = prompt(t('auth.enter_email'));
  if (!email) return;
  await _fetch(`${API}/api/auth/forgot-password`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.trim().toLowerCase() }),
  });
  alert(t('auth.reset_sent'));
}

// Reset password from URL token
async function _handleResetToken(token) {
  const pwd = prompt(t('auth.new_password_prompt'));
  if (!pwd || pwd.length < 6) { alert(t('auth.password_short')); return; }
  const r = await _fetch(`${API}/api/auth/reset-password`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, new_password: pwd }),
  });
  const data = await r.json();
  if (r.ok) { alert(t('auth.reset_ok')); }
  else { alert(data.detail || t('auth.reset_error')); }
  // Limpiar token de la URL
  history.replaceState({}, '', '/');
}

// Handle verified=1&token=... from email verification redirect
function _handleUrlParams() {
  const params = new URLSearchParams(location.search);
  if (params.get('verified') === '1') {
    const token = params.get('token');
    if (token) {
      // Decode basic user info from JWT payload (without verifying signature)
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        _setAuth(token, { email: payload.email || '', display_name: '', is_verified: true });
        history.replaceState({}, '', '/');
        refreshAudios(); refreshDashboard();
      } catch { history.replaceState({}, '', '/'); }
    }
  }
  const resetToken = params.get('reset_token');
  if (resetToken) _handleResetToken(resetToken);
}

// Google OAuth callback
window.handleGoogleCredential = async function(response) {
  try {
    const r = await _fetch(`${API}/api/auth/google`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential: response.credential }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Error Google auth');
    _setAuth(data.token, { email: data.email, display_name: data.display_name, role: data.role || 'user' });
    _getAuthModal()?.hide();
    refreshAudios(); refreshDashboard();
  } catch (err) {
    console.error('[Audial] Google auth error:', err);
    const errEl = $('#loginError');
    if (errEl) { errEl.textContent = err.message; errEl.classList.remove('hidden'); }
  }
};

function _initGoogleAuth() {
  // Google button only renders if GOOGLE_CLIENT_ID is configured
  const clientId = window.AUDIAL_GOOGLE_CLIENT_ID;
  if (!clientId || !window.google) return;
  ['googleSignInBtn', 'googleSignInBtnReg'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.parentElement?.classList.remove('hidden');
    google.accounts.id.initialize({ client_id: clientId, callback: window.handleGoogleCredential });
    google.accounts.id.renderButton(el, { theme: 'filled_black', size: 'large', width: 320 });
  });
}

/* ============================================================
   DYNAMIC TRANSLATION when lang changes on detail page
   ============================================================ */
async function translateAndRender(audioId, targetLang) {
  const panel = $('.tab-panel[data-tab="summary"]');
  if (panel) {
    const badge = document.createElement('div');
    badge.className = 'translating-badge';
    badge.id = 'translatingBadge';
    badge.innerHTML = `<span class="spinner-border text-accent"></span> ${t('auth.translating')}`;
    panel.insertBefore(badge, panel.firstChild);
  }

  try {
    const r = await fetch(`${API}/api/analysis/${audioId}?lang=${targetLang}`);
    if (!r.ok) return;
    const a = await r.json();
    window._lastAnalysis = a;

    // Actualizar título de la conversación con el idioma nuevo
    const titleText = (a.summary_short || '').slice(0, 50) + (a.summary_short?.length > 50 ? '…' : '');
    const titleEl = $('#detailTitle');
    if (titleEl && titleText) titleEl.textContent = titleText;

    safe(() => renderSummary(a));
    safe(() => renderEntities(a.entities));
    safe(() => renderTasks(a.tasks, a.decisions, a.questions));
    safe(() => renderSentiment(a.sentiment, a.conflicts));
    safe(() => renderTopics(a.topics, a.intents));
    safe(() => renderTimeline(a.timeline));
    safe(() => renderMetrics(a.metrics));
    safe(() => loadRelated(audioId));
    // Re-renderizar transcript traducido
    try {
      const tRes = await fetch(`${API}/api/analysis/${audioId}/transcript?lang=${targetLang}`);
      if (tRes.ok) { const tr = await tRes.json(); safe(() => renderTranscript(tr)); }
    } catch {}
    refreshIcons();
  } finally {
    $('#translatingBadge')?.remove();
  }
}

/* ============================================================
   ADMIN BD — integrado en el SPA (solo owner/admin)
   ============================================================ */
let _adminCurrentTable = '', _adminPage = 1, _adminCols = [], _adminRows = [], _adminEditRow = null, _adminPk = '';
const ADMIN_PAGE_SIZE = 50;

function _adminToken() { return _authToken || ''; }

async function adFetch(url, opts = {}) {
  // Usa _fetch para evitar el interceptor de auto-logout en 401
  // El admin usa el JWT del usuario logueado como X-Admin-Token
  opts.headers = { ...(opts.headers || {}), 'X-Admin-Token': _adminToken() };
  return _fetch(url, opts);
}

async function adminLoadOverview() {
  const r = await adFetch(`${API}/api/admin/stats`);
  if (!r.ok) return;
  const stats = await r.json();
  const icons = { users:'👤', audios:'🎙', jobs:'⚙️', transcripts:'📝', analyses:'🧠', embeddings_index:'🔍', roles:'🎖' };
  const grid = $('#adminStatsGrid');
  if (!grid) return;
  grid.innerHTML = Object.entries(stats).map(([k,v]) => `
    <div class="col-6 col-md-4 col-lg-3">
      <div class="kpi-tile" onclick="adminShowTable('${k}'); adminSwitchTab('tables')" style="cursor:pointer">
        <div class="kpi-icon"><span style="font-size:18px">${icons[k]||'📦'}</span></div>
        <div class="kpi-n">${v}</div>
        <div class="kpi-l">${k}</div>
      </div>
    </div>`).join('');
  // Also load table list
  const listR = await adFetch(`${API}/api/admin/tables`);
  const tables = await listR.json();
  const tlist = $('#adminTableList');
  if (tlist) tlist.innerHTML = tables.map(t => `
    <button class="admin-tbl-btn" onclick="adminShowTable('${t.table}'); adminSwitchTab('tables')">
      ${esc(t.table)} <span class="admin-tbl-count">${t.count}</span>
    </button>`).join('');
}

/* ── Utilidades del panel ── */
const _adminIsOwner = () => _authUser?.role === 'owner';
const ADM_ROLES = {
  1: { name: 'owner', icon: '👑', desc: 'Control total · único' },
  2: { name: 'admin', icon: '🔑', desc: 'Acceso al panel' },
  3: { name: 'user',  icon: '👤', desc: 'Usuario estándar' },
};
const ADM_ROLE_CHIP = {
  1: '<span class="role-chip owner">👑 owner</span>',
  2: '<span class="role-chip admin">🔑 admin</span>',
  3: '<span class="role-chip user">👤 user</span>',
};

function adminToast(msg, type = 'ok') {
  const wrap = $('#adminToasts'); if (!wrap) return;
  const el = document.createElement('div');
  el.className = `adm-toast ${type}`;
  el.textContent = msg;
  wrap.appendChild(el);
  setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 250); }, type === 'err' ? 4500 : 2600);
}

async function _adminErr(r, fallback) {
  const d = await r.json().catch(() => ({}));
  return typeof d.detail === 'string' ? d.detail : fallback;
}

async function adminCopy(text) {
  try { await navigator.clipboard.writeText(text); adminToast('Copiado al portapapeles'); }
  catch {
    const ta = document.createElement('textarea');
    ta.value = text; document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); adminToast('Copiado al portapapeles'); }
    catch { adminToast('No se pudo copiar', 'err'); }
    ta.remove();
  }
}

// Celda de contraseña: oculta por defecto, clic para mostrar, botón para copiar
function _adminSecret(v) {
  if (v === null || v === undefined || v === '')
    return '<span class="adm-null" title="Sin copia visible: aparecerá cuando el usuario inicie sesión">no disponible</span>';
  return `<span class="adm-secret-wrap">
    <span class="adm-secret" data-v="${esc(v)}" onclick="adminToggleSecret(this)" title="Clic para mostrar u ocultar">••••••••</span>
    <button type="button" class="adm-edit-btn" data-v="${esc(v)}" onclick="adminCopy(this.dataset.v)" title="Copiar"><i data-lucide="copy"></i></button>
  </span>`;
}

function adminToggleSecret(el) {
  const shown = el.classList.toggle('shown');
  el.textContent = shown ? el.dataset.v : '••••••••';
}

let _adminUsers = [];

async function adminLoadUsers() {
  const r = await adFetch(`${API}/api/admin/users`);
  if (!r.ok) return;
  _adminUsers = await r.json();
  const isOwner = _adminIsOwner();
  const pwTh = $('#adminPwTh'); if (pwTh) pwTh.style.display = isOwner ? '' : 'none';
  const tbody = $('#adminUserTableBody');
  if (!tbody) return;
  tbody.innerHTML = _adminUsers.map((u, i) => {
    const opts = [1,2,3].map(rid =>
      `<option value="${rid}" ${u.role_id===rid?'selected':''} ${rid===1&&!isOwner?'disabled':''}>${ADM_ROLES[rid].icon} ${ADM_ROLES[rid].name}</option>`
    ).join('');
    const pw = u.is_google ? '<span class="adm-null">Google</span>' : _adminSecret(u.password);
    return `<tr>
      <td>${esc(u.email)}</td>
      <td>${esc(u.display_name||'–')}</td>
      <td>${ADM_ROLE_CHIP[u.role_id]||esc(u.role_name)}</td>
      <td>${u.is_verified?'<span class="adm-yes">✓</span>':'<span class="adm-no">✗</span>'}</td>
      ${isOwner ? `<td>${pw}</td>` : ''}
      <td>${u.created_at?new Date(u.created_at).toLocaleDateString('es-ES'):'–'}</td>
      <td><select class="admin-role-sel" onchange="adminChangeRole('${esc(u.id)}',this.value)">${opts}</select></td>
      <td class="adm-actions">
        <button class="adm-edit-btn" onclick="adminOpenUserEdit(${i})" title="Editar usuario">✏</button>
        ${u.role_id!==1?`<button class="adm-edit-btn" onclick="adminDeleteUser(${i})" title="Eliminar">🗑</button>`:''}
      </td>
    </tr>`;
  }).join('') || `<tr><td colspan="8" style="text-align:center;color:var(--tx-3);padding:20px">Sin usuarios</td></tr>`;
  refreshIcons();
}

async function adminChangeRole(userId, newRoleId) {
  const r = await adFetch(`${API}/api/admin/users/${userId}/role`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role_id: parseInt(newRoleId) }),
  });
  if (r.ok) { adminToast('Rol actualizado'); adminLoadUsers(); adminLoadOverview(); }
  else { adminToast(await _adminErr(r, 'No se pudo cambiar el rol'), 'err'); adminLoadUsers(); }
}

async function adminDeleteUser(idx) {
  const u = _adminUsers[idx]; if (!u) return;
  if (!confirm(`¿Eliminar usuario ${u.email}?`)) return;
  const r = await adFetch(`${API}/api/admin/users/${u.id}`, { method: 'DELETE' });
  if (r.ok) { adminToast('Usuario eliminado'); adminLoadUsers(); adminLoadOverview(); }
  else adminToast(await _adminErr(r, 'Error eliminando usuario'), 'err');
}

async function adminShowTable(table) {
  _adminCurrentTable = table; _adminPage = 1;
  const srch = $('#adminTableSearch'); if (srch) srch.value = '';
  $$('.admin-tbl-btn').forEach(b => b.classList.toggle('active', b.textContent.trim().startsWith(table)));
  await _adminLoadTablePage();
  const title = $('#adminTableTitle'); if (title) title.textContent = `📋 ${table}`;
}

async function _adminLoadTablePage() {
  const r = await adFetch(`${API}/api/admin/tables/${_adminCurrentTable}?page=${_adminPage}&page_size=${ADMIN_PAGE_SIZE}`);
  if (!r.ok) return;
  const data = await r.json();
  _adminCols = data.columns; _adminRows = data.rows; _adminPk = _adminCols[0];
  const pi = $('#adminPageInfo');
  if (pi) pi.textContent = `${_adminPage}/${Math.ceil(data.total/ADMIN_PAGE_SIZE)||1} · ${data.total} reg.`;
  const prev = $('#adminPrevBtn'), next = $('#adminNextBtn');
  if (prev) prev.disabled = _adminPage <= 1;
  if (next) next.disabled = data.rows.length < ADMIN_PAGE_SIZE;
  _adminRenderTable(_adminCols, _adminRows);
}

function _adminRenderTable(cols, rows) {
  const thead = $('#adminTHead'), tbody = $('#adminTBody');
  if (!thead || !tbody) return;
  const secret = c => c === 'password' || c === 'hashed_password';
  thead.innerHTML = '<tr><th></th>' + cols.map(c=>`<th>${esc(c)}</th>`).join('') + '</tr>';
  tbody.innerHTML = rows.map(row => {
    const idx = _adminRows.indexOf(row);  // el índice real, también con la tabla filtrada
    return `<tr><td><button class="adm-edit-btn" onclick="adminOpenEdit(${idx})" title="Editar">✏</button></td>
     ${cols.map(c => c === 'password'
        ? `<td>${_adminSecret(row[c])}</td>`
        : `<td ${secret(c) ? '' : `title="${esc(row[c])}"`}>${_adminCell(row[c])}</td>`).join('')}</tr>`;
  }).join('') || '<tr><td colspan="99" style="text-align:center;color:var(--tx-3);padding:20px">Sin registros</td></tr>';
  refreshIcons();
}

function adminFilterTable() {
  const q = ($('#adminTableSearch')?.value||'').toLowerCase();
  _adminRenderTable(_adminCols, q ? _adminRows.filter(r=>Object.values(r).some(v=>String(v??'').toLowerCase().includes(q))) : _adminRows);
}

function adminChangePage(dir) { _adminPage = Math.max(1,_adminPage+dir); _adminLoadTablePage(); }

/* ── Editor de filas ──────────────────────────────────────────────────
   Se alimenta de (tabla, columnas, fila, pk) y lo usan tanto la vista Tablas
   como Usuarios y roles. Solo envía al servidor los campos modificados. */
let _adminEdit = null;   // { table, cols, row, pk, locked, dirty }
let _adminArmTimer = null;

function adminOpenEdit(idx) {
  const row = _adminRows[idx];
  if (row) _adminOpenEditor(_adminCurrentTable, _adminCols, row, _adminPk);
}

function adminOpenUserEdit(idx) {
  const u = _adminUsers[idx]; if (!u) return;
  const owner = _adminIsOwner();
  const row = { id: u.id, email: u.email, display_name: u.display_name, role_id: u.role_id,
                is_verified: u.is_verified ? 1 : 0, created_at: u.created_at, is_google: u.is_google };
  if (owner) row.password = u.password;
  const cols = ['id', 'email', 'display_name', ...(owner ? ['password'] : []), 'role_id', 'is_verified', 'created_at'];
  _adminOpenEditor('users', cols, row, 'id');
}

function _adminKind(col, val) {
  if (col === 'password') return 'password';
  if (col === 'hashed_password') return 'hash';
  if (_adminEdit.table === 'users' && col === 'role_id') return 'role';
  if (/^(is_|has_)/.test(col)) return 'bool';
  if (val !== null && typeof val === 'object') return 'json';
  const s = String(val ?? '');
  return (s.length > 80 || s.includes('\n')) ? 'long' : 'text';
}

function _adminField(col, val) {
  const e = _adminEdit, kind = _adminKind(col, val), ro = e.locked ? 'disabled' : '';
  const id = `aedit_${col}`, name = esc(col);
  const attrs = `id="${id}" data-col="${name}" data-kind="${kind}"`;
  const wrap = (inner, full = false, extra = '') =>
    `<div class="adm-field ${full ? 'full' : ''}"><label for="${id}">${name}${extra}</label>${inner}</div>`;

  switch (kind) {
    case 'bool':
      return wrap(`<label class="adm-switch"><input type="checkbox" ${attrs} ${val ? 'checked' : ''} ${ro}/>
        <span class="adm-switch-track"></span><span class="adm-switch-text">${val ? 'Sí' : 'No'}</span></label>`);
    case 'role':
      return wrap(`<input type="hidden" ${attrs} value="${esc(val)}"/>
        <div class="adm-role-grid">${[1,2,3].map(rid => {
          const r = ADM_ROLES[rid], off = e.locked || (rid === 1 && !_adminIsOwner());
          return `<button type="button" class="adm-role-card r${rid} ${Number(val) === rid ? 'selected' : ''}" ${off ? 'disabled' : ''}
                    onclick="adminPickRole(${rid})"><span class="ico">${r.icon}</span><b>${r.name}</b><small>${r.desc}</small></button>`;
        }).join('')}</div>`, true);
    case 'password': {
      if (e.row.is_google || e.row.hashed_password === '__google__')
        return `<div class="adm-field full"><label>${name}</label>
          <div class="adm-hint">Cuenta de Google: inicia sesión con Google y no tiene contraseña propia.</div></div>`;
      const has = val !== null && val !== undefined && val !== '';
      return wrap(`<div class="adm-input-group">
          <input class="adm-input mono" ${attrs} type="password" autocomplete="new-password" spellcheck="false"
                 value="${esc(val ?? '')}" placeholder="${has ? '' : 'No disponible · escribe una nueva para establecerla'}" ${ro}/>
          <button type="button" class="adm-icon-btn" onclick="adminPwToggle(this)" title="Mostrar u ocultar"><i data-lucide="eye"></i></button>
          <button type="button" class="adm-icon-btn" onclick="adminPwCopy()" title="Copiar"><i data-lucide="copy"></i></button>
          <button type="button" class="adm-icon-btn" onclick="adminPwGen()" title="Generar una aleatoria"><i data-lucide="refresh-cw"></i></button>
        </div>
        <div class="adm-hint">${has
          ? 'Contraseña actual en claro. Escribe otra para restablecerla (mínimo 6 caracteres).'
          : 'Aún no hay copia visible: aparecerá cuando el usuario inicie sesión, o al establecer una aquí.'}</div>`,
        true, ' <span class="adm-tag">solo owner</span>');
    }
    case 'hash':
      return wrap(`<input class="adm-input mono" id="${id}" value="${esc(val ?? '')}" readonly/>
        <div class="adm-hint">Hash de un solo sentido: no se puede revertir ni editar. Se regenera al cambiar la contraseña.</div>`, true);
    case 'json':
      return wrap(`<textarea class="adm-input" rows="6" ${attrs} spellcheck="false" ${ro}>\n${esc(JSON.stringify(val, null, 2))}</textarea>`, true, ' <span class="adm-tag">json</span>');
    case 'long':
      return wrap(`<textarea class="adm-input" rows="4" ${attrs} spellcheck="false" ${ro}>\n${esc(val)}</textarea>`, true);
    default: {
      const mono = /(_at|_exp|_id|token)$/.test(col) ? 'mono' : '';
      return wrap(`<input class="adm-input ${mono}" type="text" ${attrs} value="${esc(val ?? '')}"
        placeholder="${val === null || val === undefined ? 'NULL' : ''}" ${ro}/>`);
    }
  }
}

function _adminOpenEditor(table, cols, row, pk) {
  const modal = $('#adminEditModal'); if (!modal) return;
  const isUsers = table === 'users', owner = _adminIsOwner();
  const locked = isUsers && Number(row.role_id) === 1 && !owner;
  _adminEdit = { table, cols, row: { ...row }, pk, locked, dirty: false };
  const pkVal = row[pk];

  // Cabecera
  $('#adminEditAvatar').innerHTML = isUsers
    ? esc((row.display_name || row.email || '?').trim().charAt(0).toUpperCase())
    : '<i data-lucide="table-2"></i>';
  $('#adminEditTitle').textContent = isUsers ? (row.email || 'Usuario') : `Editar registro · ${table}`;
  $('#adminEditSub').innerHTML =
    (isUsers && ADM_ROLE_CHIP[row.role_id] ? ADM_ROLE_CHIP[row.role_id] : '') +
    `<span class="adm-pk">${esc(pk)}</span><code title="${esc(pkVal)}">${esc(pkVal)}</code>
     <button type="button" class="adm-icon-btn sm" data-v="${esc(pkVal)}" onclick="adminCopy(this.dataset.v)" title="Copiar"><i data-lucide="copy"></i></button>`;

  // Cuerpo: en usuarios, lo técnico queda plegado
  const technical = isUsers ? ['hashed_password', 'verification_token', 'reset_token', 'reset_token_exp', 'created_at'] : [];
  const main = cols.filter(c => c !== pk && !technical.includes(c));
  const tech = cols.filter(c => c !== pk && technical.includes(c));
  $('#adminEditBody').innerHTML =
    (locked ? '<div class="adm-banner">🔒 Solo el propietario puede modificar esta cuenta.</div>' : '') +
    `<div class="adm-grid">${main.map(c => _adminField(c, row[c])).join('')}</div>` +
    (tech.length ? `<details class="adm-advanced"><summary>Campos técnicos</summary>
       <div class="adm-grid">${tech.map(c => _adminField(c, row[c])).join('')}</div></details>` : '');

  // Pie
  const del = $('#adminDeleteBtn');
  del.onclick = adminDeleteRow;
  del.classList.toggle('hidden', locked || (isUsers && Number(row.role_id) === 1));
  _adminDisarm();
  _adminUpdateDirty();

  modal.classList.remove('hidden');
  refreshIcons();
  $('#adminEditBody .adm-input:not([readonly]):not([type=hidden])')?.focus({ preventScroll: true });
}

// Lee el formulario y devuelve solo los campos que han cambiado
function _adminCollect() {
  const e = _adminEdit, data = {};
  if (!e) return data;
  $$('#adminEditBody [data-col]').forEach(el => {
    const col = el.dataset.col, kind = el.dataset.kind, orig = e.row[col];
    let v, changed;
    if (kind === 'bool')          { v = el.checked ? 1 : 0;  changed = v !== (orig ? 1 : 0); }
    else if (kind === 'role')     { v = Number(el.value);    changed = v !== Number(orig); }
    else if (kind === 'password') { v = el.value;            changed = v !== '' && v !== (orig ?? ''); }
    else if (kind === 'json')     { v = el.value;            changed = v !== JSON.stringify(orig, null, 2); }
    else                          { v = el.value;            changed = v !== String(orig ?? ''); }
    el.closest('.adm-field')?.classList.toggle('dirty', changed);
    if (changed) data[col] = v;
  });
  return data;
}

function _adminUpdateDirty() {
  const e = _adminEdit; if (!e) return;
  const n = Object.keys(_adminCollect()).length;
  e.dirty = n > 0;
  $('#adminDirtyInfo').textContent = n ? `● ${n} cambio${n > 1 ? 's' : ''} sin guardar` : '';
  $('#adminSaveBtn').disabled = !n || e.locked;
}

function adminPickRole(rid) {
  const input = $('#aedit_role_id'); if (!input) return;
  input.value = rid;
  $$('#adminEditBody .adm-role-card').forEach(b => b.classList.toggle('selected', b.classList.contains(`r${rid}`)));
  _adminUpdateDirty();
}

function adminPwToggle(btn) {
  const input = $('#aedit_password'); if (!input) return;
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password';
  btn.innerHTML = `<i data-lucide="${show ? 'eye-off' : 'eye'}"></i>`;
  refreshIcons();
}

function adminPwCopy() {
  const v = $('#aedit_password')?.value;
  if (v) adminCopy(v); else adminToast('No hay contraseña que copiar', 'err');
}

function adminPwGen() {
  const input = $('#aedit_password'); if (!input) return;
  const abc = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  const buf = crypto.getRandomValues(new Uint32Array(14));
  input.value = Array.from(buf, n => abc[n % abc.length]).join('');
  input.type = 'text';
  input.dispatchEvent(new Event('input', { bubbles: true }));
}

async function adminSaveRow() {
  const e = _adminEdit; if (!e || e.locked) return;
  const data = _adminCollect();
  if (!Object.keys(data).length) { adminToast('No hay cambios que guardar'); return; }

  // Normalizar tipos: JSON válido, números como número
  for (const [col, v] of Object.entries(data)) {
    const orig = e.row[col];
    if (orig !== null && typeof orig === 'object') {
      try { data[col] = JSON.stringify(JSON.parse(v)); }
      catch { adminToast(`${col}: el JSON no es válido`, 'err'); return; }
    } else if (typeof orig === 'number' && typeof v === 'string' && col !== 'password') {
      data[col] = v.trim() === '' ? null : (isNaN(v) ? v : Number(v));
    }
  }
  if ('password' in data && data.password.length < 6) {
    adminToast('La contraseña debe tener al menos 6 caracteres', 'err'); return;
  }

  const btn = $('#adminSaveBtn'); btn.disabled = true;
  const r = await adFetch(`${API}/api/admin/tables/${e.table}/${encodeURIComponent(e.row[e.pk])}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ data }),
  });
  if (r.ok) {
    adminToast('Cambios guardados');
    adminCloseEdit(true);
    _adminAfterWrite(e.table);
  } else {
    adminToast(await _adminErr(r, 'No se pudo guardar'), 'err');
    btn.disabled = false;
  }
}

function _adminAfterWrite(table) {
  if (table === _adminCurrentTable) _adminLoadTablePage();
  if (table === 'users') adminLoadUsers();
  adminLoadOverview();
}

function _adminDisarm() {
  clearTimeout(_adminArmTimer);
  const del = $('#adminDeleteBtn'); if (!del) return;
  del.classList.remove('armed');
  del.innerHTML = '<i data-lucide="trash-2"></i> Eliminar';
  refreshIcons();
}

// Doble clic para borrar: el primero arma el botón, el segundo confirma
async function adminDeleteRow() {
  const e = _adminEdit, del = $('#adminDeleteBtn'); if (!e) return;
  if (!del.classList.contains('armed')) {
    del.classList.add('armed');
    del.textContent = '¿Seguro? Pulsa otra vez';
    _adminArmTimer = setTimeout(_adminDisarm, 3500);
    return;
  }
  const r = await adFetch(`${API}/api/admin/tables/${e.table}/${encodeURIComponent(e.row[e.pk])}`, { method: 'DELETE' });
  if (r.ok) { adminToast('Registro eliminado'); adminCloseEdit(true); _adminAfterWrite(e.table); }
  else { adminToast(await _adminErr(r, 'No se pudo eliminar'), 'err'); _adminDisarm(); }
}

function adminCloseEdit(force = false) {
  const modal = $('#adminEditModal');
  if (!modal || modal.classList.contains('hidden')) return;
  if (!force && _adminEdit?.dirty) {   // no perder cambios por un clic fuera o Esc
    const box = modal.querySelector('.adm-modal');
    box.classList.remove('shake'); void box.offsetWidth; box.classList.add('shake');
    adminToast('Hay cambios sin guardar. Usa Cancelar para descartarlos.');
    return;
  }
  modal.classList.add('hidden');
  $('#adminEditBody').innerHTML = '';   // fuera del DOM, también las contraseñas en claro
  _adminEdit = null;
  _adminDisarm();
}

async function adminRunSql() {
  const sql = $('#adminSqlEditor')?.value?.trim(); if (!sql) return;
  const res = $('#adminSqlResult'); if (!res) return;
  res.classList.remove('hidden');
  res.innerHTML = '<div class="sql-result-box"><div class="sql-result-info">Ejecutando…</div></div>';
  try {
    const r = await adFetch(`${API}/api/admin/sql`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sql }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail);
    if (d.type === 'select') {
      const info = `<div class="sql-result-info">${d.count} fila(s)</div>`;
      if (!d.rows.length) { res.innerHTML = `<div class="sql-result-box">${info}<div style="padding:12px;color:var(--tx-3)">Sin resultados</div></div>`; return; }
      const thead = '<tr>'+d.columns.map(c=>`<th>${esc(c)}</th>`).join('')+'</tr>';
      const tbody = d.rows.map(row=>'<tr>'+d.columns.map(c=>`<td>${_adminCell(row[c])}</td>`).join('')+'</tr>').join('');
      res.innerHTML = `<div class="sql-result-box">${info}<div style="overflow-x:auto"><table class="adm-table-inline">${thead}${tbody}</table></div></div>`;
    } else {
      res.innerHTML = `<div class="sql-result-box"><div class="sql-result-info">✓ ${d.rowcount} fila(s) afectada(s)</div></div>`;
      adminLoadOverview();
    }
  } catch(e) {
    res.innerHTML = `<div class="sql-result-box"><div class="sql-result-err">Error: ${esc(e.message)}</div></div>`;
  }
}

function adminClearSql() { const e=$('#adminSqlEditor'); if(e) e.value=''; const r=$('#adminSqlResult'); if(r) r.classList.add('hidden'); }
function adminSetSql(sql) { adminSwitchTab('sql'); const e=$('#adminSqlEditor'); if(e){ e.value=sql; e.focus(); } }

async function adminCleanGuests() {
  if (!confirm('¿Eliminar todos los audios de invitados expirados?')) return;
  adminSetSql("DELETE FROM audios WHERE user_id IS NULL AND expires_at IS NOT NULL AND expires_at < NOW()");
  await adminRunSql();
  adminLoadOverview();
}

function adminSwitchTab(tab) {
  $$('#adminSubTabs .tab-btn').forEach(b => b.classList.toggle('active', b.dataset.atab === tab));
  $$('.atab-panel').forEach(p => p.classList.toggle('active', p.dataset.atab === tab));
  if (tab === 'overview') adminLoadOverview();
  if (tab === 'users') adminLoadUsers();
  refreshIcons();
}

function _adminCell(v) {
  if (v===null||v===undefined) return '<span class="adm-null">NULL</span>';
  if (v===1||v===true)  return '<span class="adm-yes">✓</span>';
  if (v===0||v===false) return '<span class="adm-no">✗</span>';
  const s=String(v); return s.length>60?`<span title="${esc(s)}">${esc(s.slice(0,60))}…</span>`:esc(s);
}

// SQL editor keyboard shortcut
document.addEventListener('keydown', e => {
  if ((e.ctrlKey||e.metaKey) && e.key==='Enter' && document.activeElement?.id==='adminSqlEditor') {
    e.preventDefault(); adminRunSql();
  }
});

// Editor de filas: cambios en vivo, clic fuera, Esc y Ctrl+Enter
$('#adminEditBody')?.addEventListener('input', e => {
  if (e.target.type === 'checkbox' && e.target.closest('.adm-switch'))
    e.target.closest('.adm-switch').querySelector('.adm-switch-text').textContent = e.target.checked ? 'Sí' : 'No';
  _adminUpdateDirty();
});
$('#adminEditModal')?.addEventListener('mousedown', e => {
  if (e.target.id === 'adminEditModal') adminCloseEdit();
});
document.addEventListener('keydown', e => {
  if ($('#adminEditModal')?.classList.contains('hidden') ?? true) return;
  if (e.key === 'Escape') adminCloseEdit();
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); adminSaveRow(); }
});

// Admin sub-tabs
document.addEventListener('click', e => {
  const btn = e.target.closest('#adminSubTabs .tab-btn');
  if (btn?.dataset.atab) adminSwitchTab(btn.dataset.atab);
});

/* ============================================================
   ROLE REFRESH — sincroniza el rol del usuario con el servidor
   Necesario cuando se cambia el rol desde el admin panel
   ============================================================ */
async function refreshUserRole() {
  if (!_authToken) return;
  try {
    // Usar _fetch directamente para evitar el interceptor de 401 en esta llamada
    const r = await _fetch(`${API}/api/auth/me`, {
      headers: { 'Authorization': `Bearer ${_authToken}` }
    });
    if (!r.ok) return;
    const data = await r.json();

    if (!data.authenticated) {
      // Token inválido o usuario eliminado → cerrar sesión silenciosamente
      console.warn('[Audial] Sesión inválida (usuario no encontrado en BD), cerrando sesión');
      _setAuth(null, null);
      refreshAudios();
      refreshDashboard();
      return;
    }

    if (_authUser) {
      const oldRole = _authUser.role;
      _authUser.role = data.role || 'user';
      localStorage.setItem('audial_user', JSON.stringify(_authUser));
      if (oldRole !== data.role) {
        console.log(`[Audial] Rol actualizado: ${oldRole} → ${data.role}`);
        _updateUserNav();
      }
    }
  } catch (e) { console.warn('[Audial] refreshUserRole:', e); }
}

/* ============================================================
   BOOT — event listeners centralizados (sin onclick inline)
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  refreshIcons();
  _updateUserNav();

  // Auth modal close = continue as guest
  document.getElementById('authCloseBtn')?.addEventListener('click', _continueAsGuest);
  document.getElementById('authModal')?.addEventListener('hidden.bs.modal', () => {
    // If dismissed without logging in, treat as guest
    if (!_authToken) _continueAsGuest();
  });

  // Auth tabs
  document.getElementById('tabLogin')?.addEventListener('click', () => _switchAuthTab('login'));
  document.getElementById('tabRegister')?.addEventListener('click', () => _switchAuthTab('register'));

  // Login form
  document.getElementById('loginForm')?.addEventListener('submit', _doLogin);
  document.getElementById('loginSubmitBtn')?.addEventListener('click', _doLogin);

  // Register form
  document.getElementById('registerForm')?.addEventListener('submit', _doRegister);
  document.getElementById('registerSubmitBtn')?.addEventListener('click', _doRegister);

  // Verify code
  document.getElementById('verifySubmitBtn')?.addEventListener('click', _doVerifyCode);
  document.getElementById('verifyCodeInput')?.addEventListener('keydown', e => { if (e.key === 'Enter') _doVerifyCode(); });
  document.getElementById('resendCodeBtn')?.addEventListener('click', () => {
    $('#verifyCodeStep')?.classList.add('hidden');
    $('#registerForm')?.classList.remove('hidden');
    $$('.auth-tab').forEach((b,i) => b.classList.toggle('active', i === 1));
  });

  // Guest buttons
  document.getElementById('guestBtn')?.addEventListener('click', _continueAsGuest);
  document.getElementById('guestBtnReg')?.addEventListener('click', _continueAsGuest);

  // User nav button
  document.getElementById('userNavBtn')?.addEventListener('click', _toggleUserMenu);

  // Logout
  document.getElementById('logoutBtn')?.addEventListener('click', _doLogout);

  // Mobile navbar: backdrop + scroll lock + close on item click
  const _navCollapse = document.getElementById('navMain');
  if (_navCollapse) {
    const _backdrop = document.createElement('div');
    _backdrop.id = 'navBackdrop';
    _backdrop.style.cssText = [
      'display:none', 'position:fixed', 'inset:0',
      'background:rgba(0,0,0,.55)',
      'z-index:1019',  /* sticky-top = 1020, backdrop queda debajo del navbar */
    ].join(';');
    document.body.appendChild(_backdrop);

    _backdrop.addEventListener('click', _closeNavbar);

    _navCollapse.addEventListener('show.bs.collapse', () => {
      _backdrop.style.display = 'block';
      document.body.style.overflow = 'hidden';
    });
    _navCollapse.addEventListener('hide.bs.collapse', () => {
      _backdrop.style.display = 'none';
      document.body.style.overflow = '';
    });
  }

  // Rename modal
  document.getElementById('renameSubmitBtn')?.addEventListener('click', _submitRename);
  document.getElementById('renameInput')?.addEventListener('keydown', e => { if (e.key === 'Enter') _submitRename(); });

  // Lang switch buttons
  document.querySelector('[data-lang-btn="es"]')?.addEventListener('click', () => i18n.setLang('es'));
  document.querySelector('[data-lang-btn="en"]')?.addEventListener('click', () => i18n.setLang('en'));

  // Google OAuth (después de que cargue el script de Google)
  if (window.google) _initGoogleAuth();
  else document.querySelector('script[src*="accounts.google.com"]')
    ?.addEventListener('load', _initGoogleAuth);

  // Handle URL params (email verification, password reset)
  _handleUrlParams();

  // Forgot password link
  document.getElementById('forgotPasswordLink')?.addEventListener('click', e => {
    e.preventDefault(); _doForgotPassword();
  });

  // Show auth modal if not logged in and not dismissed
  const dismissed = localStorage.getItem('audial_auth_dismissed');
  if (!_authToken && !dismissed) {
    setTimeout(() => _getAuthModal()?.show(), 900);
  }

  refreshAudios();
  refreshDashboard();
  // Sincronizar rol desde servidor al arrancar (detecta usuarios eliminados o roles cambiados)
  refreshUserRole();
  setInterval(refreshDashboard, 300000); // cada 5 min
  setInterval(refreshUserRole, 180000);  // cada 3 min
});
