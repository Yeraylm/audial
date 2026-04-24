/* ============================================================
   Audial · config.js
   API base URL — se puede sobreescribir via variable de entorno
   en el proceso de build de Netlify: AUDIAL_API_URL
   ============================================================ */

// En desarrollo: mismo origen (el servidor FastAPI sirve el frontend).
// En Netlify: apunta al backend en Render/Railway via proxy redirect.
window.AUDIAL_API = window.AUDIAL_API || '';

/* Session ID — multi-usuario ligero via localStorage.
   Cada navegador/dispositivo tiene su propio espacio de datos. */
(function initSession() {
  let sid = localStorage.getItem('audial_session');
  if (!sid) {
    sid = crypto.randomUUID();
    localStorage.setItem('audial_session', sid);
  }
  window.AUDIAL_SESSION = sid;
})();
