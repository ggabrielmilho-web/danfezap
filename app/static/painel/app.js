/**
 * DanfeZap — Painel
 * Helpers compartilhados entre login.html e pro.html.
 *
 * Sessão: localStorage 'dfz_session' = { token, usuario_id, tipo }
 */

const SESSION_KEY = 'dfz_session';

function getSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function setSession(data) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(data));
}

function clearSession() {
  localStorage.removeItem(SESSION_KEY);
}

/**
 * Fetch autenticado. Injeta Bearer token e trata 401 limpando sessão.
 * Retorna o Response (ainda não consumido) pra caller decidir json/blob.
 */
async function apiFetch(url, opts = {}) {
  const session = getSession();
  const headers = new Headers(opts.headers || {});
  if (session && session.token) {
    headers.set('Authorization', 'Bearer ' + session.token);
  }
  if (!headers.has('Content-Type') && opts.body && typeof opts.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }

  const res = await fetch(url, { ...opts, headers });

  if (res.status === 401) {
    clearSession();
    // Não loopa: só redireciona se não estiver já na tela de login (index)
    const path = location.pathname;
    if (!(path === '/painel/' || path === '/painel/index.html')) {
      location.href = '/painel/';
    }
  }
  return res;
}

/**
 * Baixa um arquivo via fetch autenticado (não dá pra Bearer em <a href>).
 * Dispara o download programaticamente.
 */
async function downloadBlob(url, filename) {
  const res = await apiFetch(url);
  if (!res.ok) {
    let msg = 'Falha ao baixar arquivo';
    try {
      const j = await res.json();
      msg = j.detail || msg;
    } catch {}
    throw new Error(msg);
  }
  const blob = await res.blob();
  const objUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(objUrl), 1500);
}

/**
 * Exige sessão; se não tiver, redireciona pra login.
 */
function exigirSessao() {
  const s = getSession();
  if (!s || !s.token) {
    location.href = '/painel/';
    return null;
  }
  return s;
}

function formatarData(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function mascararChave(chave) {
  if (!chave || chave.length < 8) return chave || '';
  return '…' + chave.slice(-8);
}
