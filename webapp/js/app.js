/* Interactive lab logic: i18n switching, LSB canvas, Hamming canvas, roadmap. */

/* ---------- tiny seeded PRNG for reproducible demo image ---------- */
function mulberry32(seed) {
  return function () {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let z = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    z = (z + Math.imul(z ^ (z >>> 7), 61 | z)) ^ z;
    return ((z ^ (z >>> 14)) >>> 0) / 4294967296;
  };
}

/* ---------- state ---------- */
const state = {
  cover: null,       // Uint8Array original gray
  stego: null,       // Uint8Array with hidden message (or null)
  size: 200,
  hamX: [0, 1, 0, 1, 1, 0, 1],
  hamP: 3,
  hamHighlight: -1,
  hamChanged: false,
};

const els = (id) => document.getElementById(id);

/* ---------- language ---------- */
function applyLang() {
  document.documentElement.lang = currentLang === "zh" ? "zh-CN" : "en";
  els("lang-toggle").textContent = currentLang === "zh" ? "EN" : "中文";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.dataset.i18n;
    const value = t(key);
    node.innerHTML = String(value).replace(/\n/g, "<br>");
  });
  document.querySelectorAll("img[data-src-zh]").forEach((img) => {
    img.src = currentLang === "zh" ? img.dataset.srcZh : img.dataset.srcEn;
  });
  renderRoadmap();
  refreshLsbStats();
  renderHamming();
}

/* ---------- image generation ---------- */
function makeDemoImage() {
  const n = state.size;
  const rnd = mulberry32(20260908);
  const data = new Uint8Array(n * n);
  for (let y = 0; y < n; y++) {
    for (let x = 0; x < n; x++) {
      const gradient = 70 + x * 0.5 + y * 0.35;
      const cloud = Math.sin(x / 22) * 12 + Math.cos(y / 30) * 10;
      data[y * n + x] = Math.max(0, Math.min(255, gradient + cloud + (rnd() - 0.5) * 14));
    }
  }
  return data;
}

function drawGray(canvas, data) {
  const n = state.size;
  const ctx = canvas.getContext("2d");
  const img = ctx.createImageData(n, n);
  for (let i = 0; i < n * n; i++) {
    const v = data[i];
    img.data[i * 4] = v; img.data[i * 4 + 1] = v; img.data[i * 4 + 2] = v;
    img.data[i * 4 + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
}

function textToBits(text) {
  const bytes = [];
  for (let i = 0; i < text.length; i++) bytes.push(text.charCodeAt(i) & 0xff);
  const bits = [];
  for (let i = 0; i < 16; i++) bits.push((bytes.length >> i) & 1);
  bytes.forEach((b) => {
    for (let i = 0; i < 8; i++) bits.push((b >> i) & 1);
  });
  return bits;
}

function embedMessage() {
  const msg = els("lsb-msg").value || "Hi";
  const bits = textToBits(msg.slice(0, 24));
  state.stego = state.cover.slice();
  let changed = 0;
  const limit = Math.min(bits.length, state.stego.length);
  for (let i = 0; i < limit; i++) {
    const old = state.stego[i] & 1;
    const next = bits[i];
    if (old !== next) changed++;
    state.stego[i] = (state.stego[i] & 0xfe) | next;
  }
  state.embedChanged = changed;
  els("bitplane").value = "-1";
  els("bitplane-note").textContent = t("lsb.note0");
  redrawLsb();
}

function resetDemo() {
  state.stego = null;
  state.embedChanged = 0;
  els("lsb-msg").value = "Hello nsF5!";
  els("bitplane").value = "-1";
  els("bitplane-note").textContent = t("lsb.note0");
  redrawLsb();
}

function redrawLsb() {
  const plane = parseInt(els("bitplane").value, 10);
  const source = state.stego || state.cover;
  if (plane < 0) {
    drawGray(els("lsb-canvas"), source);
  } else {
    const n = state.size;
    const out = new Uint8Array(n * n);
    for (let i = 0; i < n * n; i++) out[i] = ((source[i] >> plane) & 1) * 255;
    drawGray(els("lsb-canvas"), out);
  }
  refreshLsbStats();
}

function refreshLsbStats() {
  const n = state.size;
  const data = state.stego || state.cover;
  let ones = 0;
  for (let i = 0; i < n * n; i++) ones += data[i] & 1;
  els("lsb-stats").textContent = t("stats")
    .replace("{p}", (ones / (n * n) * 100).toFixed(1) + "%")
    .replace("{c}", String(state.embedChanged || 0));
}

/* ---------- Hamming demo ---------- */
function hammingMatrix(p) {
  const n = (1 << p) - 1;
  const H = [];
  for (let j = 1; j <= n; j++) {
    const col = [];
    for (let r = 0; r < p; r++) col.push((j >> r) & 1);
    H.push(col);
  }
  return H;
}

function syndromeBits(x) {
  const p = state.hamP;
  const H = hammingMatrix(p);
  const s = new Array(p).fill(0);
  x.forEach((bit, j) => {
    if (!bit) return;
    for (let r = 0; r < p; r++) s[r] ^= H[j][r];
  });
  return s;
}

function bitsToInt(bits) { return bits.reduce((a, b) => a * 2 + b, 0); }
function intLE(bits) { return bits.reduce((a, b, i) => a + b * (1 << i), 0); }
function toBin(v, p) { return v.toString(2).padStart(p, "0"); }
function fmt(bits) { return toBin(intLE(bits), bits.length); }

function resizeHamming() {
  state.hamP = parseInt(els("ham-p").value, 10);
  const n = (1 << state.hamP) - 1;
  while (state.hamX.length < n) state.hamX.push(0);
  state.hamX = state.hamX.slice(0, n);
  const m = els("ham-m").value.replace(/[^01]/g, "").slice(-state.hamP).padStart(state.hamP, "0");
  els("ham-m").value = m;
}

function solveHamming() {
  resizeHamming();
  const p = state.hamP;
  const mBits = els("ham-m").value.split("").map(Number);
  const sBits = syndromeBits(state.hamX);
  const sVal = intLE(sBits);
  const mVal = parseInt(mBits.join(""), 2);
  const dVal = sVal ^ mVal;
  const n = (1 << p) - 1;
  state.hamChanged = false;
  let info;
  if (dVal === 0) {
    state.hamHighlight = -1;
    info = t("hamNoChange");
  } else {
    state.hamHighlight = dVal - 1;
    state.hamChanged = true;
    info = t("hamFlip").replace("{n}", String(dVal));
  }
  els("ham-info").textContent = t("hamInfo")
    .replace("{s}", toBin(sVal, p)).replace("{m}", mBits.join(""))
    .replace("{d}", toBin(dVal, p))
    .replace("{action}", info);
  renderHammingCanvas();
}

function randomHamming() {
  resizeHamming();
  const rnd = mulberry32(Date.now() & 0xffffffff);
  state.hamX = state.hamX.map(() => (rnd() > 0.5 ? 1 : 0));
  state.hamHighlight = -1;
  solveHamming();
}

function renderHamming() {
  solveHamming();
}

function renderHammingCanvas() {
  const canvas = els("ham-canvas");
  const ctx = canvas.getContext("2d");
  const n = state.hamX.length;
  const cell = Math.min(72, (canvas.width - 30) / n);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.font = "600 15px system-ui";
  for (let i = 0; i < n; i++) {
    const x = 16 + i * (cell + 8);
    const y = 34;
    const highlight = i === state.hamHighlight && state.hamChanged;
    ctx.fillStyle = highlight ? "#ffd54f" : state.hamX[i] ? "#2e7d32" : "#eceff1";
    ctx.strokeStyle = highlight ? "#c62828" : "#90a4ae";
    ctx.lineWidth = highlight ? 3 : 1;
    ctx.fillRect(x, y, cell, cell);
    ctx.strokeRect(x, y, cell, cell);
    ctx.fillStyle = highlight || state.hamX[i] ? "#ffffff" : "#37474f";
    ctx.textAlign = "center";
    ctx.fillText(String(state.hamX[i]), x + cell / 2, y + cell / 2 + 5);
    ctx.fillStyle = "#78909c";
    ctx.font = "10px system-ui";
    ctx.fillText(String(i + 1), x + cell / 2, y + cell + 16);
    ctx.font = "600 15px system-ui";
  }
  els("ham-caption").textContent = t("ham.caption");
}

function hamClick(ev) {
  const canvas = els("ham-canvas");
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const mx = (ev.clientX - rect.left) * scaleX;
  const n = state.hamX.length;
  const cell = Math.min(72, (canvas.width - 30) / n);
  const idx = Math.floor((mx - 16) / (cell + 8));
  if (idx >= 0 && idx < n) {
    state.hamX[idx] ^= 1;
    solveHamming();
  }
}

/* ---------- roadmap ---------- */
function renderRoadmap() {
  const list = els("roadmap-list");
  list.innerHTML = "";
  t("roadmap").forEach(([week, topic, action]) => {
    const li = document.createElement("li");
    const b = document.createElement("b");
    b.textContent = week + " · " + topic;
    const span = document.createElement("span");
    span.textContent = action;
    li.append(b, span);
    list.appendChild(li);
  });
}

/* ---------- wire events ---------- */
function init() {
  state.cover = makeDemoImage();
  state.stego = null;
  els("lang-toggle").addEventListener("click", () => {
    currentLang = currentLang === "zh" ? "en" : "zh";
    localStorage.setItem("nsf5-lang", currentLang);
    applyLang();
  });
  els("lsb-embed").addEventListener("click", embedMessage);
  els("lsb-reset").addEventListener("click", resetDemo);
  els("bitplane").addEventListener("input", redrawLsb);
  els("ham-random").addEventListener("click", randomHamming);
  els("ham-solve").addEventListener("click", solveHamming);
  els("ham-p").addEventListener("change", () => { resizeHamming(); randomHamming(); });
  els("ham-m").addEventListener("change", () => { resizeHamming(); solveHamming(); });
  els("ham-canvas").addEventListener("click", hamClick);
  applyLang();
}

document.addEventListener("DOMContentLoaded", init);
