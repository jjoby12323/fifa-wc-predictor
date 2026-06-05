const API_BASE = window.API_BASE || "";

function getAuth() {
  const params = new URLSearchParams(window.location.search);
  return { user: params.get("user"), sig: params.get("sig") };
}

async function apiFetch(path, options = {}) {
  const resp = await fetch(API_BASE + path, options);
  if (!resp.ok) {
    let msg = `Error ${resp.status}`;
    try {
      const body = await resp.json();
      msg = body.detail || msg;
    } catch (_) {}
    throw new Error(msg);
  }
  return resp.json();
}

function showError(msg) {
  const el = document.getElementById("error-banner");
  if (!el) return;
  el.textContent = msg;
  el.classList.remove("hidden");
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
