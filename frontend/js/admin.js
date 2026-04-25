/* ============================================================
   Audial Admin Panel · admin.js v2
   Auth por rol (owner/admin) + gestión de usuarios y roles
   ============================================================ */

const API = location.origin;
let ADMIN_TOKEN = sessionStorage.getItem('audial_admin_token') || '';
let ADMIN_ROLE  = sessionStorage.getItem('audial_admin_role')  || '';
let _currentTable = '', _currentPage = 1, _currentCols = [], _currentRows = [], _editingRow = null, _pkCol = '';
const PAGE_SIZE = 50;

// ── Init ──────────────────────────────────────────────────────────────
if (ADMIN_TOKEN) showPanel();

function switchLoginTab(tab) {
  document.getElementById('ltabUser')?.classList.toggle('active', tab === 'user');
  document.getElementById('ltabSecret')?.classList.toggle('active', tab === 'secret');
  document.getElementById('loginUser')?.classList.toggle('hidden', tab !== 'user');
  document.getElementById('loginSecret')?.classList.toggle('hidden', tab !== 'secret');
}

async function doAdminLogin() {
  const errEl = document.getElementById('loginErr');
  errEl.classList.add('hidden');

  const isSecretTab = !document.getElementById('loginSecret')?.classList.contains('hidden');
  const body = isSecretTab
    ? { secret: document.getElementById('adminSecret')?.value?.trim() }
    : { email: document.getElementById('adminEmail')?.value?.trim(),
        password: document.getElementById('adminPass')?.value };

  try {
    const r = await fetch(`${API}/api/admin/auth`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'Acceso denegado');
    ADMIN_TOKEN = d.token;
    ADMIN_ROLE  = d.role;
    sessionStorage.setItem('audial_admin_token', ADMIN_TOKEN);
    sessionStorage.setItem('audial_admin_role',  ADMIN_ROLE);
    showPanel();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.remove('hidden');
  }
}

['adminEmail','adminPass','adminSecret'].forEach(id => {
  document.getElementById(id)?.addEventListener('keydown', e => { if (e.key === 'Enter') doAdminLogin(); });
});

function showPanel() {
  document.getElementById('loginScreen').classList.add('hidden');
  document.getElementById('adminPanel').classList.remove('hidden');
  loadSidebar();
  loadOverview();
}

function doLogout() {
  sessionStorage.removeItem('audial_admin_token');
  sessionStorage.removeItem('audial_admin_role');
  ADMIN_TOKEN = ''; ADMIN_ROLE = '';
  location.reload();
}

// ── Fetch helper ──────────────────────────────────────────────────────
async function adFetch(url, opts = {}) {
  opts.headers = { ...(opts.headers || {}), 'X-Admin-Token': ADMIN_TOKEN };
  const r = await fetch(url, opts);
  if (r.status === 403) { doLogout(); throw new Error('Sesión expirada'); }
  return r;
}

// ── Sidebar ───────────────────────────────────────────────────────────
async function loadSidebar() {
  const r = await adFetch(`${API}/api/admin/tables`);
  const tables = await r.json();
  document.getElementById('sidebarInfo').textContent = `${ADMIN_ROLE} · ${tables.length} tablas`;
  document.getElementById('tableList').innerHTML = tables.map(t => `
    <button class="adm-table-btn" onclick="showTable('${t.table}')">
      ${t.table} <span class="adm-table-count">${t.count}</span>
    </button>`).join('');
}

// ── Overview ──────────────────────────────────────────────────────────
async function loadOverview() {
  showView('viewOverview');
  setBtnActive(null);
  const r = await adFetch(`${API}/api/admin/stats`);
  const stats = await r.json();
  const icons = { users:'👤', audios:'🎙', jobs:'⚙️', transcripts:'📝', analyses:'🧠', embeddings_index:'🔍', roles:'🎖' };
  document.getElementById('statsGrid').innerHTML = Object.entries(stats).map(([k,v]) => `
    <div class="stat-card" onclick="${k==='users'?'showUsersView()':k==='roles'?`showTable('roles')`:`showTable('${k}')`}">
      <div class="n">${v}</div>
      <div class="l">${icons[k]||'📦'} ${k}</div>
    </div>`).join('');
}

// ── Users + roles ─────────────────────────────────────────────────────
const ROLE_NAMES = { 1:'owner', 2:'admin', 3:'user' };
const ROLE_LABELS = {
  1:'<span class="role-badge owner">👑 owner</span>',
  2:'<span class="role-badge admin">🔑 admin</span>',
  3:'<span class="role-badge user">👤 user</span>',
};

async function showUsersView() {
  showView('viewUsers');
  setBtnActive('showUsersView()');
  await loadUsers();
}

async function loadUsers() {
  const r = await adFetch(`${API}/api/admin/users`);
  const users = await r.json();
  const isOwner = ADMIN_ROLE === 'owner';

  document.getElementById('userTableBody').innerHTML = users.map(u => {
    const opts = [1,2,3].map(rid =>
      `<option value="${rid}" ${u.role_id===rid?'selected':''}
        ${rid===1&&!isOwner?'disabled':''}>
        ${rid===1?'👑 owner':rid===2?'🔑 admin':'👤 user'}
      </option>`).join('');
    return `<tr>
      <td>${esc(u.email)}</td>
      <td>${esc(u.display_name||'–')}</td>
      <td>${ROLE_LABELS[u.role_id]||u.role_name}</td>
      <td>${u.is_verified?'<span style="color:#39FF14">✓</span>':'<span style="color:#5A7A5A">✗</span>'}</td>
      <td>${u.created_at?new Date(u.created_at).toLocaleDateString('es-ES'):'–'}</td>
      <td>
        <select class="role-select" onchange="changeUserRole('${u.id}', this.value)">${opts}</select>
      </td>
      <td>
        ${u.role_id!==1?`<button class="edit-row-btn" onclick="deleteUser('${u.id}','${esc(u.email)}')" title="Eliminar usuario">🗑</button>`:''}
      </td>
    </tr>`;
  }).join('') || '<tr><td colspan="7" style="text-align:center;color:#5A7A5A;padding:20px">Sin usuarios</td></tr>';
}

async function changeUserRole(userId, newRoleId) {
  const r = await adFetch(`${API}/api/admin/users/${userId}/role`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role_id: parseInt(newRoleId) }),
  });
  if (r.ok) {
    await loadUsers();
    await loadSidebar();
  } else {
    const d = await r.json();
    alert('Error: ' + (d.detail || 'No se pudo cambiar el rol'));
    await loadUsers(); // revert UI
  }
}

async function deleteUser(userId, email) {
  if (!confirm(`¿Eliminar usuario ${email}? Sus audios registrados no se eliminarán.`)) return;
  const r = await adFetch(`${API}/api/admin/users/${userId}`, { method: 'DELETE' });
  if (r.ok) { await loadUsers(); await loadSidebar(); }
  else { const d = await r.json(); alert('Error: ' + (d.detail || 'No se pudo eliminar')); }
}

// ── Table browser ──────────────────────────────────────────────────────
async function showTable(table) {
  _currentTable = table; _currentPage = 1;
  const srch = document.getElementById('tableSearch');
  if (srch) srch.value = '';
  $$('.adm-table-btn').forEach(b => b.classList.remove('active'));
  $$('.adm-table-btn').forEach(b => { if (b.textContent.trim().startsWith(table)) b.classList.add('active'); });
  await loadTablePage();
  showView('viewTable');
}

async function loadTablePage() {
  const r = await adFetch(`${API}/api/admin/tables/${_currentTable}?page=${_currentPage}&page_size=${PAGE_SIZE}`);
  if (!r.ok) return;
  const data = await r.json();
  _currentCols = data.columns; _currentRows = data.rows;
  _pkCol = _currentCols[0];
  document.getElementById('tableViewTitle').textContent = `📋 ${data.table}`;
  document.getElementById('tableViewMeta').textContent  = `${data.total} registros · pág. ${_currentPage}`;
  document.getElementById('pageInfo').textContent = `${_currentPage}/${Math.ceil(data.total/PAGE_SIZE)||1}`;
  document.getElementById('prevPageBtn').disabled = _currentPage <= 1;
  document.getElementById('nextPageBtn').disabled = data.rows.length < PAGE_SIZE;
  renderTable(_currentCols, _currentRows);
}

function renderTable(cols, rows) {
  document.getElementById('mainTableHead').innerHTML = '<tr><th></th>' + cols.map(c=>`<th>${c}</th>`).join('') + '</tr>';
  document.getElementById('mainTableBody').innerHTML = rows.map((row,idx)=>
    `<tr><td><button class="edit-row-btn" onclick="openEditModal(${idx})">✏</button></td>
     ${cols.map(c=>`<td title="${esc(row[c])}">${cellVal(row[c])}</td>`).join('')}</tr>`
  ).join('') || '<tr><td colspan="99" style="text-align:center;color:#5A7A5A;padding:24px">Sin datos</td></tr>';
}

function filterTable() {
  const q = document.getElementById('tableSearch')?.value?.toLowerCase() || '';
  renderTable(_currentCols, q ? _currentRows.filter(r=>Object.values(r).some(v=>String(v??'').toLowerCase().includes(q))) : _currentRows);
}

function changePage(dir) { _currentPage = Math.max(1,_currentPage+dir); loadTablePage(); }

// ── Edit modal ─────────────────────────────────────────────────────────
function openEditModal(idx) {
  _editingRow = {..._currentRows[idx]};
  const pkVal = _editingRow[_pkCol];
  document.getElementById('editModalTitle').textContent = `✏ ${_pkCol} = ${pkVal}`;
  document.getElementById('editModalBody').innerHTML = _currentCols.map(col => {
    const isPk = col === _pkCol;
    const val  = _editingRow[col] ?? '';
    const long = String(val).length > 80;
    const field = long
      ? `<textarea rows="3" id="edit_${col}" ${isPk?'readonly':''}>${esc(String(val))}</textarea>`
      : `<input type="text" id="edit_${col}" value="${esc(String(val))}" ${isPk?'readonly':''}/>`
    return `<div class="adm-field ${isPk?'pk-field':''}"><label>${col}${isPk?' (PK)':''}</label>${field}</div>`;
  }).join('');
  document.getElementById('deleteRowBtn').onclick = () => deleteRow(pkVal);
  document.getElementById('editModal').classList.remove('hidden');
}

function closeEditModal() { document.getElementById('editModal').classList.add('hidden'); _editingRow = null; }

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
  else { const d = await r.json(); alert('Error: ' + (d.detail||'desconocido')); }
}

async function deleteRow(pkVal) {
  if (!confirm(`¿Eliminar ${_pkCol} = ${pkVal}?`)) return;
  const r = await adFetch(`${API}/api/admin/tables/${_currentTable}/${pkVal}`, { method:'DELETE' });
  if (r.ok) { closeEditModal(); loadTablePage(); loadSidebar(); }
  else alert('Error eliminando');
}

// ── SQL editor ─────────────────────────────────────────────────────────
function showSqlEditor() { showView('viewSql'); setBtnActive('showSqlEditor()'); }
function clearSql() { document.getElementById('sqlEditor').value=''; document.getElementById('sqlResult').classList.add('hidden'); }
function setSql(sql) { showSqlEditor(); document.getElementById('sqlEditor').value=sql; }

async function runSql() {
  const sql = document.getElementById('sqlEditor')?.value?.trim();
  if (!sql) return;
  const resEl = document.getElementById('sqlResult');
  resEl.classList.remove('hidden');
  resEl.innerHTML = '<div class="sql-result-info">Ejecutando…</div>';
  try {
    const r = await adFetch(`${API}/api/admin/sql`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ sql }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail);
    if (d.type === 'select') {
      const info = `<div class="sql-result-info">${d.count} fila(s) devuelta(s)</div>`;
      if (!d.rows.length) { resEl.innerHTML = info+'<div style="padding:12px 16px;color:#5A7A5A">Sin resultados</div>'; return; }
      const thead = '<tr>'+d.columns.map(c=>`<th>${c}</th>`).join('')+'</tr>';
      const tbody = d.rows.map(row=>'<tr>'+d.columns.map(c=>`<td>${cellVal(row[c])}</td>`).join('')+'</tr>').join('');
      resEl.innerHTML = info+'<div style="overflow-x:auto"><table class="adm-table">'+thead+tbody+'</table></div>';
    } else {
      resEl.innerHTML = `<div class="sql-result-info">✓ ${d.rowcount} fila(s) afectada(s)</div>`;
      loadSidebar();
    }
  } catch(e) {
    resEl.innerHTML = `<div class="sql-result-error">Error: ${esc(e.message)}</div>`;
  }
}

document.getElementById('sqlEditor')?.addEventListener('keydown', e => {
  if ((e.ctrlKey||e.metaKey) && e.key==='Enter') { e.preventDefault(); runSql(); }
});

// ── Misc ───────────────────────────────────────────────────────────────
async function confirmDeleteGuest() {
  if (!confirm('¿Eliminar todos los audios de invitados expirados (expires_at < ahora)?')) return;
  setSql("DELETE FROM audios WHERE user_id IS NULL AND expires_at IS NOT NULL AND expires_at < datetime('now')");
  await runSql(); loadSidebar();
}

function showView(id) {
  document.querySelectorAll('.adm-view').forEach(v=>v.classList.remove('active'));
  document.getElementById(id)?.classList.add('active');
}

function setBtnActive(fn) {
  $$('.adm-table-btn, .adm-sql-btn').forEach(b=>b.classList.remove('active'));
}

function $$(sel) { return Array.from(document.querySelectorAll(sel)); }
function esc(s) { return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function cellVal(v) {
  if (v===null||v===undefined) return '<span class="td-null">NULL</span>';
  if (v===1||v===true)  return '<span class="td-bool-yes">✓</span>';
  if (v===0||v===false) return '<span class="td-bool-no">✗</span>';
  const s=String(v); if(s.length>60) return `<span title="${esc(s)}">${esc(s.slice(0,60))}…</span>`;
  return esc(s);
}
