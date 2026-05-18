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

/**
 * Extrai dados estruturados de uma chave NFe de 44 dígitos.
 *
 * Layout oficial (Manual NFe):
 *   pos 0-1   UF (2)
 *   pos 2-5   AAMM emissão (4)
 *   pos 6-19  CNPJ emitente (14)
 *   pos 20-21 Modelo (2)
 *   pos 22-24 Série (3)
 *   pos 25-33 Número da NF (9)
 *   pos 34    Tipo emissão (1)
 *   pos 35-42 Código numérico (8)
 *   pos 43    DV (1)
 *
 * Retorna null se a chave não tem 44 dígitos.
 */
function dadosChaveNFe(chave) {
  if (!chave || !/^\d{44}$/.test(chave)) return null;
  return {
    uf: chave.substring(0, 2),
    aamm: chave.substring(2, 6),
    cnpj: chave.substring(6, 20),
    modelo: chave.substring(20, 22),
    serie: parseInt(chave.substring(22, 25), 10),
    numero: parseInt(chave.substring(25, 34), 10),
  };
}
