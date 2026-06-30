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

// FIFA-style 3-letter codes — shown where space is tight (e.g. the knockout bracket).
const TEAM_CODES = {
  "United States": "USA", "USA": "USA", "Canada": "CAN", "Mexico": "MEX", "Panama": "PAN",
  "Honduras": "HON", "Costa Rica": "CRC", "El Salvador": "SLV", "Jamaica": "JAM",
  "Trinidad and Tobago": "TRI", "Guatemala": "GUA", "Haiti": "HAI",
  "Curaçao": "CUW", "Curacao": "CUW", "Cuba": "CUB",
  "Brazil": "BRA", "Argentina": "ARG", "Uruguay": "URU", "Colombia": "COL", "Ecuador": "ECU",
  "Chile": "CHI", "Paraguay": "PAR", "Bolivia": "BOL", "Venezuela": "VEN", "Peru": "PER",
  "France": "FRA", "Germany": "GER", "Spain": "ESP", "Portugal": "POR", "England": "ENG",
  "Netherlands": "NED", "Belgium": "BEL", "Italy": "ITA", "Switzerland": "SUI", "Croatia": "CRO",
  "Denmark": "DEN", "Austria": "AUT", "Czech Republic": "CZE", "Czechia": "CZE", "Serbia": "SRB",
  "Scotland": "SCO", "Turkey": "TUR", "Slovakia": "SVK", "Hungary": "HUN", "Poland": "POL",
  "Slovenia": "SVN", "Albania": "ALB", "Romania": "ROU", "Georgia": "GEO", "Ukraine": "UKR",
  "Wales": "WAL", "Greece": "GRE", "Sweden": "SWE", "Norway": "NOR", "Finland": "FIN",
  "Iceland": "ISL", "Bosnia and Herzegovina": "BIH", "Bosnia-Herzegovina": "BIH", "Bosnia": "BIH",
  "North Macedonia": "MKD", "Montenegro": "MNE", "Kosovo": "KOS", "Bulgaria": "BUL",
  "Ireland": "IRL", "Northern Ireland": "NIR", "Latvia": "LVA", "Lithuania": "LTU",
  "Estonia": "EST", "Armenia": "ARM", "Azerbaijan": "AZE", "Kazakhstan": "KAZ",
  "Luxembourg": "LUX", "Cyprus": "CYP", "Faroe Islands": "FRO", "Russia": "RUS",
  "Morocco": "MAR", "Senegal": "SEN", "Nigeria": "NGA", "Egypt": "EGY",
  "Côte d'Ivoire": "CIV", "Ivory Coast": "CIV", "Cote d'Ivoire": "CIV", "Côte D'Ivoire": "CIV",
  "Cameroon": "CMR", "Ghana": "GHA", "Tunisia": "TUN", "Algeria": "ALG", "South Africa": "RSA",
  "Mali": "MLI", "DR Congo": "COD", "Congo DR": "COD", "Democratic Republic of Congo": "COD",
  "Congo, DR": "COD", "Tanzania": "TAN", "Zimbabwe": "ZIM", "Zambia": "ZAM", "Kenya": "KEN",
  "Uganda": "UGA", "Ethiopia": "ETH", "Angola": "ANG", "Libya": "LBY", "Sudan": "SDN",
  "Mozambique": "MOZ", "Benin": "BEN", "Guinea": "GUI", "Cape Verde": "CPV",
  "Cape Verde Islands": "CPV", "Gambia": "GAM",
  "Japan": "JPN", "South Korea": "KOR", "Korea Republic": "KOR", "Korea DPR": "PRK",
  "North Korea": "PRK", "Australia": "AUS", "Iran": "IRN", "Saudi Arabia": "KSA", "Iraq": "IRQ",
  "Jordan": "JOR", "Qatar": "QAT", "Uzbekistan": "UZB", "Bahrain": "BHR", "China": "CHN",
  "China PR": "CHN", "United Arab Emirates": "UAE", "Kuwait": "KUW", "Oman": "OMA",
  "Palestine": "PLE", "Lebanon": "LBN", "Syria": "SYR", "Pakistan": "PAK", "Indonesia": "IDN",
  "Thailand": "THA", "Vietnam": "VIE", "Philippines": "PHI", "Malaysia": "MAS", "India": "IND",
  "Tajikistan": "TJK", "Kyrgyzstan": "KGZ", "Turkmenistan": "TKM",
  "New Zealand": "NZL", "Fiji": "FIJ", "Papua New Guinea": "PNG", "Solomon Islands": "SOL",
};

// Short code for tight UIs; falls back to the first 3 letters for anything unmapped.
function getTeamCode(teamName) {
  if (!teamName || teamName === "TBD") return "TBD";
  return TEAM_CODES[teamName] || teamName.slice(0, 3).toUpperCase();
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
  t.querySelector(".chat-toast-text").textContent = _mediaUrl(msg.content) ? _mediaLabel(msg.content) : (msg.content || "");
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

// A chat message is "media" (rendered inline) if its whole content is an image
// URL we trust: an https Giphy URL, or one of our own uploads under /uploads/.
function _mediaUrl(content) {
  const s = (content || "").trim();
  if (!s || /\s/.test(s)) return null;
  if (s.startsWith("/uploads/")) return s;
  try {
    const u = new URL(s);
    if (u.protocol === "https:" && (u.hostname === "giphy.com" || u.hostname.endsWith(".giphy.com"))) return s;
  } catch (_) {}
  return null;
}
function _mediaLabel(content) { const s = content || ""; return (s.includes("giphy.com") || /\.gif(\?|$)/i.test(s)) ? "🖼 GIF" : "🖼 Image"; }

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
    const qtext = m.reply_to_content
      ? (_mediaUrl(m.reply_to_content) ? _mediaLabel(m.reply_to_content) : escHtml(_clip(m.reply_to_content, 80)))
      : "";
    const quote = m.reply_to_name
      ? `<div class="chat-quote"><span class="chat-quote-name">${escHtml(m.reply_to_name)}</span><span class="chat-quote-text">${qtext}</span></div>`
      : "";
    const media = _mediaUrl(m.content);
    const body = media ? `<img class="chat-gif" src="${escHtml(media)}" alt="" loading="lazy">` : escHtml(m.content);
    return `<div class="chat-msg ${mine}">
      <span class="chat-name">${escHtml(m.display_name)}</span>
      <div class="chat-row">
        <div class="chat-text${media ? " has-gif" : ""}">${quote}${body}</div>
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
  const info = _mediaUrl(_chatReplyTo.content) ? _mediaLabel(_chatReplyTo.content) : escHtml(_clip(_chatReplyTo.content, 60));
  bar.innerHTML =
    `<span class="chat-reply-info">↩ <b>${escHtml(_chatReplyTo.name)}</b> · ${info}</span>` +
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

// Upload a GIF/image file from the device and post it as a chat message.
async function uploadAndSend(file) {
  const { user, sig } = getAuth();
  if (!user || !sig || !file) return;
  const fd = new FormData();
  fd.append("file", file);
  let res;
  try {
    res = await fetch(`/api/chat/upload?user=${encodeURIComponent(user)}&sig=${encodeURIComponent(sig)}`, { method: "POST", body: fd });
  } catch (_) { return; }
  if (!res.ok) {
    let d = {}; try { d = await res.json(); } catch (_) {}
    alert(d.detail || "Upload failed.");
    return;
  }
  const { url } = await res.json();
  const reply_to = _chatReplyTo ? _chatReplyTo.id : null;
  clearReply();
  _chatForceBottom = true;
  await apiFetch(`/api/chat?user=${encodeURIComponent(user)}&sig=${encodeURIComponent(sig)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content: url, reply_to }),
  }).catch(() => {});
  await loadChat();
}

// ── GIF picker (Giphy, via the /api/gifs proxy; hidden when no key configured) ──
let _gifTimer = null;

function toggleGifPicker() {
  const p = document.getElementById("chat-gif-picker");
  if (!p) return;
  const show = p.classList.contains("hidden");
  p.classList.toggle("hidden", !show);
  if (show) {
    const s = document.getElementById("gif-search");
    s.value = ""; s.focus();
    searchGifs("");
  }
}

async function searchGifs(q) {
  const res = document.getElementById("gif-results");
  if (!res) return;
  res.innerHTML = `<div class="gif-note">Loading…</div>`;
  let data;
  try { data = await (await fetch(`/api/gifs?q=${encodeURIComponent(q)}`)).json(); } catch (_) { data = null; }
  if (!data || !data.enabled) { res.innerHTML = `<div class="gif-note">GIF search isn't set up.</div>`; return; }
  if (!data.gifs.length) { res.innerHTML = `<div class="gif-note">No GIFs found.</div>`; return; }
  res.innerHTML = data.gifs
    .map(g => `<img class="gif-thumb" src="${escHtml(g.preview)}" data-send="${escHtml(g.send)}" alt="GIF" loading="lazy">`)
    .join("");
  res.querySelectorAll(".gif-thumb").forEach(img => img.addEventListener("click", () => sendGif(img.dataset.send)));
}

async function sendGif(url) {
  const { user, sig } = getAuth();
  if (!user || !sig || !url) return;
  document.getElementById("chat-gif-picker")?.classList.add("hidden");
  const reply_to = _chatReplyTo ? _chatReplyTo.id : null;
  clearReply();
  _chatForceBottom = true;
  await apiFetch(`/api/chat?user=${encodeURIComponent(user)}&sig=${encodeURIComponent(sig)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content: url, reply_to }),
  }).catch(() => {});
  await loadChat();
}

async function _initGifPicker(inputRow) {
  if (!inputRow) return;
  let enabled = false;
  try { enabled = !!(await (await fetch("/api/gifs")).json()).enabled; } catch (_) {}
  if (!enabled) return;   // no Giphy key → no GIF button, chat unchanged
  const sendBtn = inputRow.querySelector(".chat-send");
  if (sendBtn && !inputRow.querySelector(".chat-gif-btn")) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "chat-gif-btn"; b.textContent = "GIF"; b.title = "Send a GIF";
    b.addEventListener("click", toggleGifPicker);
    inputRow.insertBefore(b, sendBtn);
  }
  if (!document.getElementById("chat-gif-picker")) {
    const p = document.createElement("div");
    p.id = "chat-gif-picker";
    p.className = "chat-gif-picker hidden";
    p.innerHTML = `<input id="gif-search" class="gif-search" type="text" placeholder="Search GIFs…"><div id="gif-results" class="gif-results"></div>`;
    inputRow.parentNode.insertBefore(p, inputRow);
    p.querySelector("#gif-search").addEventListener("input", e => {
      clearTimeout(_gifTimer);
      const q = e.target.value;
      _gifTimer = setTimeout(() => searchGifs(q), 350);
    });
  }
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
  if (inputRow && !inputRow.querySelector(".chat-attach-btn")) {
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = "image/gif,image/png,image/jpeg,image/webp";
    fileInput.style.display = "none";
    fileInput.addEventListener("change", () => { if (fileInput.files[0]) { uploadAndSend(fileInput.files[0]); fileInput.value = ""; } });
    const attach = document.createElement("button");
    attach.type = "button"; attach.className = "chat-attach-btn"; attach.textContent = "📎"; attach.title = "Upload a GIF or image";
    attach.addEventListener("click", () => fileInput.click());
    inputRow.insertBefore(attach, inputRow.querySelector(".chat-send"));
    inputRow.appendChild(fileInput);
  }
  document.getElementById("chat-input")?.addEventListener("keydown", e => { if (e.key === "Enter") sendMessage(); });

  const { user, sig } = getAuth();
  if (!user || !sig) {
    document.getElementById("chat-input-row")?.classList.add("hidden");
    document.getElementById("chat-readonly-note")?.classList.remove("hidden");
  }
  _initGifPicker(inputRow);
  loadChat();
  setInterval(loadChat, 4_000);
}
initChat();
