const API_BASE = window.API_BASE || "";

// ISO 3166-1 alpha-2 codes for flagcdn.com  (/w80/{code}.png)
const FLAG_CODES = {
  // North & Central America
  "United States": "us", "USA": "us",
  "Canada": "ca",
  "Mexico": "mx",
  "Panama": "pa",
  "Honduras": "hn",
  "Costa Rica": "cr",
  "El Salvador": "sv",
  "Jamaica": "jm",
  "Trinidad and Tobago": "tt",
  "Guatemala": "gt",
  "Haiti": "ht",
  "Curaçao": "cw", "Curacao": "cw",
  "Cuba": "cu",
  // South America
  "Brazil": "br",
  "Argentina": "ar",
  "Uruguay": "uy",
  "Colombia": "co",
  "Ecuador": "ec",
  "Chile": "cl",
  "Paraguay": "py",
  "Bolivia": "bo",
  "Venezuela": "ve",
  "Peru": "pe",
  // Europe
  "France": "fr",
  "Germany": "de",
  "Spain": "es",
  "Portugal": "pt",
  "England": "gb-eng",
  "Netherlands": "nl",
  "Belgium": "be",
  "Italy": "it",
  "Switzerland": "ch",
  "Croatia": "hr",
  "Denmark": "dk",
  "Austria": "at",
  "Czech Republic": "cz", "Czechia": "cz",
  "Serbia": "rs",
  "Scotland": "gb-sct",
  "Turkey": "tr",
  "Slovakia": "sk",
  "Hungary": "hu",
  "Poland": "pl",
  "Slovenia": "si",
  "Albania": "al",
  "Romania": "ro",
  "Georgia": "ge",
  "Ukraine": "ua",
  "Wales": "gb-wls",
  "Greece": "gr",
  "Sweden": "se",
  "Norway": "no",
  "Finland": "fi",
  "Iceland": "is",
  "Bosnia and Herzegovina": "ba", "Bosnia-Herzegovina": "ba", "Bosnia": "ba",
  "North Macedonia": "mk",
  "Montenegro": "me",
  "Kosovo": "xk",
  "Bulgaria": "bg",
  "Ireland": "ie",
  "Northern Ireland": "gb-nir",
  "Latvia": "lv",
  "Lithuania": "lt",
  "Estonia": "ee",
  "Armenia": "am",
  "Azerbaijan": "az",
  "Kazakhstan": "kz",
  "Luxembourg": "lu",
  "Cyprus": "cy",
  "Faroe Islands": "fo",
  "Russia": "ru",
  // Africa
  "Morocco": "ma",
  "Senegal": "sn",
  "Nigeria": "ng",
  "Egypt": "eg",
  "Côte d'Ivoire": "ci", "Ivory Coast": "ci", "Cote d'Ivoire": "ci", "Côte D'Ivoire": "ci",
  "Cameroon": "cm",
  "Ghana": "gh",
  "Tunisia": "tn",
  "Algeria": "dz",
  "South Africa": "za",
  "Mali": "ml",
  "DR Congo": "cd", "Congo DR": "cd", "Democratic Republic of Congo": "cd", "Congo, DR": "cd",
  "Tanzania": "tz",
  "Zimbabwe": "zw",
  "Zambia": "zm",
  "Kenya": "ke",
  "Uganda": "ug",
  "Ethiopia": "et",
  "Angola": "ao",
  "Libya": "ly",
  "Sudan": "sd",
  "Mozambique": "mz",
  "Benin": "bj",
  "Guinea": "gn",
  "Cape Verde": "cv", "Cape Verde Islands": "cv",
  "Gambia": "gm",
  // Asia
  "Japan": "jp",
  "South Korea": "kr", "Korea Republic": "kr", "Korea DPR": "kp", "North Korea": "kp",
  "Australia": "au",
  "Iran": "ir",
  "Saudi Arabia": "sa",
  "Iraq": "iq",
  "Jordan": "jo",
  "Qatar": "qa",
  "Uzbekistan": "uz",
  "Bahrain": "bh",
  "China": "cn", "China PR": "cn",
  "United Arab Emirates": "ae",
  "Kuwait": "kw",
  "Oman": "om",
  "Palestine": "ps",
  "Lebanon": "lb",
  "Syria": "sy",
  "Pakistan": "pk",
  "Indonesia": "id",
  "Thailand": "th",
  "Vietnam": "vn",
  "Philippines": "ph",
  "Malaysia": "my",
  "India": "in",
  "Tajikistan": "tj",
  "Kyrgyzstan": "kg",
  "Turkmenistan": "tm",
  // Oceania
  "New Zealand": "nz",
  "Fiji": "fj",
  "Papua New Guinea": "pg",
  "Solomon Islands": "sb",
};

function getFlagUrl(teamName) {
  const code = FLAG_CODES[teamName];
  return code ? `https://flagcdn.com/w160/${code}.png` : null;
}

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
  if (resp.status === 204) return null;   // no body (e.g. DELETE)
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

// ── Smack-talk toast: small popup for new chat messages while the widget is closed ──
let _chatToastTimer = null;
let _chatToastHideTimer = null;

function _ensureChatToast() {
  let t = document.getElementById("chat-toast");
  if (!t) {
    t = document.createElement("div");
    t.id = "chat-toast";
    t.className = "chat-toast hidden";
    t.innerHTML =
      `<span class="chat-toast-icon">💬</span>` +
      `<div class="chat-toast-body">` +
        `<span class="chat-toast-name"></span>` +
        `<span class="chat-toast-text"></span>` +
      `</div>`;
    t.addEventListener("click", () => {
      const icon = document.getElementById("chat-toggle-icon");
      const isOpen = icon && icon.textContent.trim() === "▼";
      if (!isOpen && typeof toggleChat === "function") toggleChat();
      hideChatToast();
    });
    document.body.appendChild(t);
  }
  return t;
}

function showChatToast(msg) {
  if (!msg) return;
  const t = _ensureChatToast();
  if (_chatToastHideTimer) { clearTimeout(_chatToastHideTimer); _chatToastHideTimer = null; }
  t.querySelector(".chat-toast-name").textContent = msg.display_name || "New message";
  t.querySelector(".chat-toast-text").textContent = msg.content || "";
  t.classList.remove("hidden");
  void t.offsetWidth;            // reflow so the slide-in transition runs
  t.classList.add("show");
  if (_chatToastTimer) clearTimeout(_chatToastTimer);
  _chatToastTimer = setTimeout(hideChatToast, 5000);
}

function hideChatToast() {
  const t = document.getElementById("chat-toast");
  if (!t) return;
  t.classList.remove("show");
  if (_chatToastTimer) { clearTimeout(_chatToastTimer); _chatToastTimer = null; }
  if (_chatToastHideTimer) clearTimeout(_chatToastHideTimer);
  _chatToastHideTimer = setTimeout(() => { t.classList.add("hidden"); _chatToastHideTimer = null; }, 220);
}

// ── Smack-talk chat (shared by every page that includes the widget) ──────────
let _chatOpen = false, _chatLastSeen = 0, _chatPrimed = false, _chatMsgs = [], _chatReplyTo = null, _chatForceBottom = true;

function _clip(s, n) { s = String(s || ""); return s.length > n ? s.slice(0, n - 1) + "…" : s; }

async function loadChat() {
  const msgs = await apiFetch("/api/chat").catch(() => []);
  _chatMsgs = msgs;
  renderChat(msgs);

  const latestId = msgs.length ? msgs[msgs.length - 1].id : 0;
  if (!_chatPrimed) { _chatLastSeen = latestId; _chatPrimed = true; return; }  // seed baseline
  if (_chatOpen) { _chatLastSeen = latestId; return; }                          // reading live

  const { user } = getAuth();
  const unread = msgs.filter(m => m.id > _chatLastSeen && m.username !== user);
  if (unread.length) {
    const dot = document.getElementById("chat-unread");
    dot.textContent = "●"; dot.classList.remove("hidden");
    showChatToast(unread[unread.length - 1]);
  }
}

function renderChat(msgs) {
  const el = document.getElementById("chat-messages");
  if (!el) return;
  const { user } = getAuth();
  // Only auto-scroll to the newest message if the reader is already near the
  // bottom — otherwise polling would yank them down while scrolling history.
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
  const prevTop = el.scrollTop;
  el.innerHTML = msgs.map(m => {
    const mine = m.username === user ? "mine" : "";
    const quote = m.reply_to_name
      ? `<div class="chat-quote"><span class="chat-quote-name">${escHtml(m.reply_to_name)}</span><span class="chat-quote-text">${escHtml(_clip(m.reply_to_content, 80))}</span></div>`
      : "";
    return `<div class="chat-msg ${mine}">
      <span class="chat-name">${escHtml(m.display_name)}</span>
      <div class="chat-row">
        <div class="chat-text">${quote}${escHtml(m.content)}</div>
        <button class="chat-reply-btn" title="Reply" onclick="setReply(${m.id})">↩</button>
      </div>
    </div>`;
  }).join("");
  el.scrollTop = (_chatForceBottom || atBottom) ? el.scrollHeight : prevTop;
  _chatForceBottom = false;
}

function toggleChat() {
  _chatOpen = !_chatOpen;
  document.getElementById("chat-body").style.display = _chatOpen ? "flex" : "none";
  document.getElementById("chat-toggle-icon").textContent = _chatOpen ? "▼" : "▲";
  document.getElementById("chat-unread").classList.add("hidden");
  hideChatToast();
  if (_chatOpen) { _chatForceBottom = true; loadChat(); }  // jump to latest on open
}

function setReply(id) {
  const m = _chatMsgs.find(x => x.id === id);
  if (!m) return;
  _chatReplyTo = { id: m.id, name: m.display_name, content: m.content };
  _renderReplyBar();
  document.getElementById("chat-input")?.focus();
}
function clearReply() { _chatReplyTo = null; _renderReplyBar(); }
function _renderReplyBar() {
  const bar = document.getElementById("chat-reply-bar");
  if (!bar) return;
  if (!_chatReplyTo) { bar.classList.add("hidden"); bar.innerHTML = ""; return; }
  bar.classList.remove("hidden");
  bar.innerHTML =
    `<span class="chat-reply-info">↩ <b>${escHtml(_chatReplyTo.name)}</b> · ${escHtml(_clip(_chatReplyTo.content, 60))}</span>` +
    `<button class="chat-reply-cancel" title="Cancel" onclick="clearReply()">✕</button>`;
}

async function sendMessage() {
  const { user, sig } = getAuth();
  if (!user || !sig) return;
  const input = document.getElementById("chat-input");
  const content = input.value.trim();
  if (!content) return;
  input.value = "";
  const reply_to = _chatReplyTo ? _chatReplyTo.id : null;
  clearReply();
  await apiFetch(`/api/chat?user=${encodeURIComponent(user)}&sig=${encodeURIComponent(sig)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, reply_to }),
  }).catch(() => {});
  _chatForceBottom = true;   // show your own message even if you'd scrolled up
  await loadChat();
}

function initChat() {
  if (!document.getElementById("chat-widget")) return;  // page has no chat widget (e.g. bracket)
  const inputRow = document.getElementById("chat-input-row");
  if (inputRow && !document.getElementById("chat-reply-bar")) {
    const bar = document.createElement("div");
    bar.id = "chat-reply-bar";
    bar.className = "chat-reply-bar hidden";
    inputRow.parentNode.insertBefore(bar, inputRow);   // sits just above the input
  }
  document.getElementById("chat-input")?.addEventListener("keydown", e => { if (e.key === "Enter") sendMessage(); });

  const { user, sig } = getAuth();
  if (!user || !sig) {
    document.getElementById("chat-input-row")?.classList.add("hidden");
    document.getElementById("chat-readonly-note")?.classList.remove("hidden");
  }
  loadChat();
  setInterval(loadChat, 4_000);
}
initChat();
