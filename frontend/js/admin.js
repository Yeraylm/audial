/* ============================================================
   Audial Admin Panel · admin.js
   ============================================================ */

const API = location.origin;
let ADMIN_TOKEN = sessionStorage.getItem('audial_admin_token') || '';
let _currentTable = '';
let _currentPage  = 1;
let _currentCols  = [];
let _currentRows  = [];
let _editingRow   = null;
let _pkCol        = '';
const PAGE_SIZE = 50;

// ── auth ─────────────────────────────────────────────────────────────
if (ADMIN_TOKEN) showPanel();

async function doAdminLogin() {
  const secret = document.getElementById('adminSecret').value.trim();
  const errEl  = document.getElementById('loginErr');
  errEl.classList.add('hidden');
  try {
    const r = await fetch(`${API}/api/admin/auth`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ secret }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'Clave incorrecta');
    ADMIN_TOKEN = secret;
    sessionStorage.setItem('audial_admin_token', secret);
    showPanel();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.remove('hidden');
  }
}
document.getElementById('adminSecret')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') doAdminLogin();
});

function showPanel() {
  document.getElementById('loginScreen').classList.add('hidden');
  document.getElementById('adminPanel').classList.remove('hidden');
  loadSidebar();
  loadOverview();
}

function doLogout() {
  sessionStorage.removeItem('audial_admin_token');
  ADMIN_TOKEN = '';
  location.reload();
}

// ── fetch helper ─────────────────────────────────────────────────────
async function adFetch(url, opts = {}) {
  opts.headers = { ...(opts.headers || {}), 'X-Admin-Token': ADMIN_TOKEN };
  const r = await fetch(url, opts);
  if (r.status === 403) { doLogout(); throw new Error('Sesión expirada'); }
  return r;
}

// ── sidebar ──────────────────────────────────────────────────────────
async function loadSidebar() {
  const list = document.getElementById('tableList');
  const r = await adFetch(`${API}/api/admin/tables`);
  const tables = await r.json();
  const dbUrl = tables.length ? 'SQLite · ' + tables.length + ' tablas' : 'sin datos';
  document.getElementById('sidebarDbUrl').textContent = dbUrl;
  list.innerHTML = tables.map(t => `
    <button class="adm-table-btn" onclick="showTable('${t.table}')">
      ${t.table}
      <span class="adm-table-count">${t.count}</span>
    </button>`).join('');
}

// ── overview ─────────────────────────────────────────────────────────
async function loadOverview() {
  showView('viewOverview');
  const r = await adFetch(`${API}/api/admin/stats`);
  const stats = await r.json();
  const icons = { users:'👤', audios:'🎙', jobs:'⚙️', transcripts:'📝', analyses:'🧠', embeddings_index:'🔍' };
  document.getElementById('statsGrid').innerHTML = Object.entries(stats).map(([k,v]) => `
    <div class="stat-card" onclick="showTable('${k}')">
      <div class="n">${v}</div>
      <div class="l">${icons[k] || '📦'} ${k}</div>
    </div>`).join('');
}

// ── table browser ─────────────────────────────────────────────────────
async function showTable(table) {
  _currentTable = table;
  _currentPage  = 1;
  document.getElementById('tableSearch').value = '';
  $$('.adm-table-btn').forEach(b => b.classList.remove('active'));
  $$('.adm-table-btn').forEach(b => { if (b.textContent.trim().startsWith(table)) b.classList.add('active'); });
  await loadTablePage();
  showView('viewTable');
}

async function loadTablePage() {
  const r = await adFetch(`${API}/api/admin/tables/${_currentTable}?page=${_currentPage}&page_size=${PAGE_SIZE}`);
  if (!r.ok) { alert('Error cargando tabla'); return; }
  const data = await r.json();
  _currentCols = data.columns;
  _currentRows = data.rows;
  _pkCol       = _currentCols[0]; // primer campo como PK por convención

  document.getElementById('tableViewTitle').textContent = `📋 ${data.table}`;
  document.getElementById('tableViewMeta').textContent  = `${data.total} registros · página ${_currentPage}`;
  document.getElementById('pageInfo').textContent = `${_currentPage} / ${Math.ceil(data.total / PAGE_SIZE) || 1}`;
  document.getElementById('prevPageBtn').disabled = _currentPage <= 1;
  document.getElementById('nextPageBtn').disabled = data.rows.length < PAGE_SIZE;

  renderTable(_currentCols, _currentRows);
}

function renderTable(cols, rows) {
  document.getElementById('mainTableHead').innerHTML =
    '<tr>' + ['', ...cols].map(c => `<th>${c}</th>`).join('') + '</tr>';
  document.getElementById('mainTableBody').innerHTML = rows.map((row, idx) =>
    `<tr>
      <td><button class="edit-row-btn" onclick="openEditModal(${idx})">✏</button></td>
      ${cols.map(c => `<td title="${esc(row[c])}">${cellVal(row[c])}</td>`).join('')}
    </tr>`
  ).join('') || '<tr><td colspan="99" style="text-align:center;color:#5A7A5A;padding:24px">Sin registros</td></tr>';
}

function filterTable() {
  const q = document.getElementById('tableSearch').value.toLowerCase();
  if (!q) { renderTable(_currentCols, _currentRows); return; }
  const filtered = _currentRows.filter(row =>
    Object.values(row).some(v => String(v ?? '').toLowerCase().includes(q))
  );
  renderTable(_currentCols, filtered);
}

function changePage(dir) {
  _currentPage = Math.max(1, _currentPage + dir);
  loadTablePage();
}

function cellVal(v) {
  if (v === null || v === undefined) return '<span class="td-null">NULL</span>';
  if (v === 1 || v === true)  return '<span class="td-bool-yes">✓</span>';
  if (v === 0 || v === false) return '<span class="td-bool-no">✗</span>';
  const s = String(v);
  if (s.length > 60) return `<span title="${esc(s)}">${esc(s.slice(0,60))}…</span>`;
  return esc(s);
}

// ── edit modal ────────────────────────────────────────────────────────
function openEditModal(rowIdx) {
  _editingRow = { ..._currentRows[rowIdx] };
  const pkVal = _editingRow[_pkCol];
  document.getElementById('editModalTitle').textContent = `Editar · ${_pkCol} = ${pkVal}`;
  document.getElementById('editModalBody').innerHTML = _currentCols.map(col => {
    const isPk = col === _pkCol;
    const val  = _editingRow[col] ?? '';
    const longText = String(val).length > 80;
    const field    = longText
      ? `<textarea rows="4" id="edit_${col}" ${isPk ? 'readonly' : ''}>${esc(String(val))}</textarea>`
      : `<input type="text" id="edit_${col}" value="${esc(String(val))}" ${isPk ? 'readonly' : ''}/>`;
    return `<div class="adm-field ${isPk ? 'pk-field' : ''}"><label>${col}${isPk ? ' (PK)' : ''}</label>${field}</div>`;
  }).join('');

  document.getElementById('deleteRowBtn').onclick = () => deleteRow(pkVal);
  document.getElementById('editModal').classList.remove('hidden');
}

function closeEditModal() {
  document.getElementById('editModal').classList.add('hidden');
  _editingRow = null;
}

async function saveRow() {
  if (!_editingRow) return;
  const pkVal = _editingRow[_pkCol];
  const data  = {};
  _currentCols.forEach(col => {
    if (col === _pkCol) return;
    const el = document.getElementById(`edit_${col}`);
    if (el) data[col] = el.value;
  });
  const r = await adFetch(`${API}/api/admin/tables/${_currentTable}/${pkVal}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data }),
  });
  if (r.ok) { closeEditModal(); loadTablePage(); loadSidebar(); }
  else { const d = await r.json(); alert('Error: ' + (d.detail || 'desconocido')); }
}

async function deleteRow(pkVal) {
  if (!confirm(`¿Eliminar registro ${_pkCol} = ${pkVal}? Esta acción no se puede deshacer.`)) return;
  const r = await adFetch(`${API}/api/admin/tables/${_currentTable}/${pkVal}`, { method: 'DELETE' });
  if (r.ok) { closeEditModal(); loadTablePage(); loadSidebar(); }
  else alert('Error eliminando');
}

// ── SQL editor ────────────────────────────────────────────────────────
function showSqlEditor() { showView('viewSql'); }
function clearSql() { document.getElementById('sqlEditor').value = ''; document.getElementById('sqlResult').classList.add('hidden'); }
function setSql(sql) { showSqlEditor(); document.getElementById('sqlEditor').value = sql; }

async function runSql() {
  const sql = document.getElementById('sqlEditor').value.trim();
  if (!sql) return;
  const resEl = document.getElementById('sqlResult');
  resEl.classList.remove('hidden');
  resEl.innerHTML = '<div class="sql-result-info">Ejecutando…</div>';
  try {
    const r = await adFetch(`${API}/api/admin/sql`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail);
    if (d.type === 'select') {
      const infoHtml = `<div class="sql-result-info">${d.count} fila(s) devuelta(s)</div>`;
      if (!d.rows.length) { resEl.innerHTML = infoHtml + '<div style="padding:12px 16px;color:#5A7A5A">Sin resultados</div>'; return; }
      const thead = '<tr>' + d.columns.map(c => `<th>${c}</th>`).join('') + '</tr>';
      const tbody = d.rows.map(row => '<tr>' + d.columns.map(c => `<td>${cellVal(row[c])}</td>`).join('') + '</tr>').join('');
      resEl.innerHTML = infoHtml + '<div style="overflow-x:auto"><table class="adm-table">' + thead + tbody + '</table></div>';
    } else {
      resEl.innerHTML = `<div class="sql-result-info">✓ ${d.rowcount} fila(s) afectada(s)</div>`;
      loadSidebar();
    }
  } catch (e) {
    resEl.innerHTML = `<div class="sql-result-error">Error: ${esc(e.message)}</div>`;
  }
}

document.getElementById('sqlEditor')?.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); runSql(); }
});

// ── misc ─────────────────────────────────────────────────────────────
function showView(id) {
  document.querySelectorAll('.adm-view').forEach(v => v.classList.remove('active'));
  document.getElementById(id)?.classList.add('active');
}

async function confirmDeleteGuest() {
  if (!confirm('¿Eliminar todos los audios de invitados expirados? Los archivos de disco también se eliminarán.')) return;
  const sql = "DELETE FROM audios WHERE user_id IS NULL AND expires_at IS NOT NULL AND expires_at < datetime('now')";
  setSql(sql);
  await runSql();
  loadSidebar();
}

function $$(sel) { return Array.from(document.querySelectorAll(sel)); }
function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
