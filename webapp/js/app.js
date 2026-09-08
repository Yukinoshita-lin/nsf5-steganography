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
  hamFocus: 0,
  wetVals: [130, 129, 126, 133, 128, 124, 127],
  wetForceDry: new Array(7).fill(false),
  wetChanged: new Set(),
  wetFocus: 0,
  wetTimer: null,
  wetStop: false,
  scanData: null,
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
  renderWet();
  renderThreshold();
  renderScan();
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

/* ---------- Wet paper dry-position demo ---------- */
function wetDry(wetState, i) {
  const auto = Math.abs(wetState.wetVals[i] - 128) <= 1;
  return wetState.wetForceDry[i] ? true : !auto;
}

function wetRandom() {
  const rnd = mulberry32((Date.now() ^ 0x9e3779b9) >>> 0);
  const vals = [];
  for (let i = 0; i < 7; i++) {
    const v = 118 + Math.floor(rnd() * 20);
    vals.push(v);
  }
  state.wetVals = vals;
  state.wetForceDry = new Array(7).fill(false);
  state.wetChanged = new Set();
  renderWetCanvas();
  els("wet-info").textContent = "s=… · m=…";
}

function wetAutoStop() {
  state.wetStop = true;
  if (state.wetTimer) { clearTimeout(state.wetTimer); state.wetTimer = null; }
}

function wetAutoPlay() {
  wetAutoStop();
  state.wetStop = false;
  const step = () => {
    if (state.wetStop) return;
    wetRandom();
    state.wetTimer = setTimeout(() => {
      if (state.wetStop) return;
      wetSolve();
      state.wetTimer = setTimeout(step, 1500);
    }, 900);
  };
  step();
}

function wetSolve() {
  const p = 3, n = 7;
  const H = hammingMatrix(p);
  const s = new Array(p).fill(0);
  state.wetVals.forEach((v, j) => {
    const bit = v & 1;
    if (!bit) return;
    for (let r = 0; r < p; r++) s[r] ^= H[j][r];
  });
  const mBits = (els("wet-m").value || "101").split("").map(Number);
  const sVal = intLE(s);
  const mVal = parseInt(mBits.join(""), 2);
  const dVal = sVal ^ mVal;
  const dry = [];
  state.wetVals.forEach((_, j) => { if (wetDry(state, j)) dry.push(j); });
  state.wetChanged = new Set();
  let action;
  if (dVal === 0) {
    action = t("wet.ok") + " · d=0";
  } else {
    let hit = -1;
    for (const j of dry) {
      if (intLE(H[j]) === dVal) { hit = j; break; }
    }
    if (hit < 0) {
      outer:
      for (let a = 0; a < dry.length; a++) {
        for (let b = a + 1; b < dry.length; b++) {
          const ca = intLE(H[dry[a]]), cb = intLE(H[dry[b]]);
          if ((ca ^ cb) === dVal) {
            state.wetChanged.add(dry[a]);
            state.wetChanged.add(dry[b]);
            hit = dry[a];
            break outer;
          }
        }
      }
      if (hit < 0) action = t("wet.fail");
      else action = t("wet.ok");
    } else {
      state.wetChanged.add(hit);
      action = t("wet.ok");
    }
  }
  els("wet-info").textContent =
    "s=" + toBin(sVal, p) + " · m=" + mBits.join("") +
    " · d=" + toBin(dVal, p) + " → " + action;
  renderWetCanvas();
}

function renderWet() {
  const m = els("wet-m").value || "101";
  els("wet-m").value = m.length === 3 ? m : m.padStart(3, "0").slice(-3);
  renderWetCanvas();
}

function renderWetCanvas() {
  const canvas = els("wet-canvas");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const n = 7, cellW = 66, gap = 12;
  const startX = 24, y = 34, cellH = 84;
  ctx.font = "600 15px system-ui";
  for (let i = 0; i < n; i++) {
    const x = startX + i * (cellW + gap);
    const dry = wetDry(state, i);
    const changed = state.wetChanged.has(i);
    const v = state.wetVals[i];
    const xv = v - 128;
    ctx.fillStyle = dry ? "#e8f6ee" : "#fdecea";
    ctx.strokeStyle = changed ? "#ffb300" : (dry ? "#2e7d32" : "#c62828");
    ctx.lineWidth = changed ? 4 : 2;
    ctx.fillRect(x, y, cellW, cellH);
    ctx.strokeRect(x, y, cellW, cellH);
    ctx.textAlign = "center";
    ctx.fillStyle = "#12263a";
    ctx.fillText(String(v), x + cellW / 2, y + 34);
    ctx.fillStyle = dry ? "#2e7d32" : "#c62828";
    ctx.fillText(dry ? t("wet.dry") : t("wet.wet"), x + cellW / 2, y + 58);
    ctx.fillStyle = "#5b6b7a";
    ctx.font = "11px system-ui";
    ctx.fillText("xv=" + (xv >= 0 ? "+" : "") + xv, x + cellW / 2, y + 76);
    ctx.font = "600 15px system-ui";
    if (changed) ctx.fillText("▲", x + cellW / 2, y - 6);
  }
  const fx = startX + state.wetFocus * (cellW + gap);
  ctx.setLineDash([5, 4]);
  ctx.strokeStyle = "#2e74b5";
  ctx.lineWidth = 2;
  ctx.strokeRect(fx - 3, y - 3, cellW + 6, cellH + 6);
  ctx.setLineDash([]);
}

function wetClick(ev) {
  const canvas = els("wet-canvas");
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const mx = (ev.clientX - rect.left) * scaleX;
  const idx = Math.floor((mx - 24) / (66 + 12));
  if (idx >= 0 && idx < 7) {
    state.wetFocus = idx;
    state.wetForceDry[idx] = !state.wetForceDry[idx];
    state.wetChanged = new Set();
    renderWetCanvas();
  }
}

function wetKey(ev) {
  if (ev.key === "ArrowRight") { state.wetFocus = (state.wetFocus + 1) % 7; ev.preventDefault(); }
  else if (ev.key === "ArrowLeft") { state.wetFocus = (state.wetFocus - 1 + 7) % 7; ev.preventDefault(); }
  else if (ev.key === " " || ev.key === "Enter") {
    state.wetForceDry[state.wetFocus] = !state.wetForceDry[state.wetFocus];
    state.wetChanged = new Set();
    ev.preventDefault();
  } else return;
  renderWetCanvas();
}

/* ---------- ML threshold playground ---------- */
function gauss(x, mu, sigma) {
  return Math.exp(-((x - mu) ** 2) / (2 * sigma * sigma)) / (sigma * Math.sqrt(2 * Math.PI));
}

function normalCdf(x, mu, sigma) {
  const z = (x - mu) / (sigma * Math.SQRT2);
  const erf = (t) => {
    const sign = t < 0 ? -1 : 1;
    t = Math.abs(t);
    const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741;
    const a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
    const tt = 1 / (1 + p * t);
    const poly = (((((a5 * tt + a4) * tt) + a3) * tt + a2) * tt + a1) * tt;
    return sign * (1 - poly * Math.exp(-t * t));
  };
  return 0.5 * (1 + erf(z));
}

function renderThreshold() {
  const canvas = els("thr-canvas");
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  const xMin = -2.2, xMax = 4.4;
  const mapX = (x) => 50 + ((x - xMin) / (xMax - xMin)) * (W - 100);
  const mapY = (y) => H - 34 - (y / 0.46) * (H - 70);
  const clean = { mu: 0.45, sigma: 0.95, color: "#4c9be8" };
  const stego = { mu: 2.35, sigma: 0.95, color: "#ef6f9f" };
  const sliderVal = parseInt(els("thr-slider").value, 10);
  const thr = xMin + (sliderVal / 300) * (xMax - xMin);
  els("thr-note").textContent = "threshold = " + thr.toFixed(2);
  ctx.strokeStyle = "#c9d4e0";
  ctx.beginPath();
  ctx.moveTo(50, mapY(0)); ctx.lineTo(W - 50, mapY(0)); ctx.stroke();
  ctx.font = "11px system-ui";
  for (const m of [clean, stego]) {
    ctx.strokeStyle = m.color;
    ctx.lineWidth = 2.4;
    ctx.beginPath();
    for (let px = 0; px <= W - 100; px += 2) {
      const x = xMin + (px / (W - 100)) * (xMax - xMin);
      const y = gauss(x, m.mu, m.sigma);
      if (px === 0) ctx.moveTo(50 + px, mapY(y));
      else ctx.lineTo(50 + px, mapY(y));
    }
    ctx.stroke();
    ctx.fillStyle = m.color;
    ctx.fillText(m === clean ? (currentLang === "zh" ? "干净" : "clean")
      : (currentLang === "zh" ? "含密" : "stego"), mapX(m.mu) + 4, mapY(gauss(m.mu, m.mu, m.sigma)) - 6);
  }
  const tx = mapX(thr);
  ctx.strokeStyle = "#d32f2f"; ctx.lineWidth = 2.5;
  ctx.beginPath(); ctx.moveTo(tx, 24); ctx.lineTo(tx, H - 34); ctx.stroke();
  const fp = 1 - normalCdf(thr, clean.mu, clean.sigma);
  const fn = normalCdf(thr, stego.mu, stego.sigma);
  ctx.fillStyle = "rgba(239,111,159,.16)";
  ctx.beginPath();
  for (let px = Math.max(0, Math.floor(tx - 50)); px <= W - 50; px += 1) {
    const x = xMin + ((px - 50) / (W - 100)) * (xMax - xMin);
    const y = gauss(x, clean.mu, clean.sigma);
    if (px === Math.floor(tx - 50)) ctx.moveTo(50 + px, mapY(y));
    else ctx.lineTo(50 + px, mapY(y));
  }
  ctx.lineTo(W - 50, mapY(0)); ctx.lineTo(tx, mapY(0)); ctx.closePath();
  ctx.fill();
  els("thr-stats").textContent =
    "FP=" + (fp * 100).toFixed(1) + "% · FN=" + (fn * 100).toFixed(1) + "%";
}

/* ---------- Payload scan visualization ---------- */
const SCAN_FALLBACK = {
  densities: [0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35],
  chi2_pvalue: [0, 0, 0, 0, 0, 0, 0, 0],
  rs_rate: [22.25, 22.79, 23.39, 23.92, 24.43, 24.89, 25.48, 25.9],
  ml_proba: [5.33, 8.54, 23.28, 24.81, 34.49, 64.91, 74.53, 80.89],
};

function renderScan() {
  const data = state.scanData || SCAN_FALLBACK;
  const idx = Math.min(els("pay-slider").value, data.densities.length - 1);
  const canvas = els("scan-canvas");
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  const rows = [
    { key: "chi2_pvalue", max: 1, color: "#e08a00", label: t("pay.chi2") },
    { key: "rs_rate", max: 55, color: "#2e74b5", label: t("pay.rs") },
    { key: "ml_proba", max: 100, color: "#d63f6c", label: t("pay.ml") },
  ];
  const left = 78, right = W - 26, rowH = (H - 34) / rows.length;
  const xFor = (i) => left + (i / (data.densities.length - 1)) * (right - left);
  rows.forEach((row, r) => {
    const yTop = 14 + r * rowH;
    const yFor = (v) => yTop + rowH - 14 - (Math.min(Math.max(v, 0), row.max) / row.max) * (rowH - 28);
    ctx.strokeStyle = "#e6ecf3";
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(left, yTop + rowH - 14); ctx.lineTo(right, yTop + rowH - 14); ctx.stroke();
    ctx.fillStyle = "#5b6b7a";
    ctx.font = "600 12px system-ui";
    ctx.fillText(row.label, 4, yTop + rowH / 2);
    ctx.strokeStyle = row.color;
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    data.densities.forEach((_, i) => {
      const y = yFor(data[row.key][i]);
      if (i === 0) ctx.moveTo(xFor(i), y); else ctx.lineTo(xFor(i), y);
    });
    ctx.stroke();
    const vy = data[row.key][idx];
    ctx.fillStyle = row.color;
    ctx.beginPath(); ctx.arc(xFor(idx), yFor(vy), 5, 0, Math.PI * 2); ctx.fill();
    ctx.font = "11px system-ui";
    const val = row.key === "chi2_pvalue" ? vy.toFixed(2) : vy.toFixed(1) + "%";
    ctx.fillText(val, Math.min(xFor(idx) + 8, right - 34), yTop + rowH / 2 - 6);
  });
  ctx.strokeStyle = "#d32f2f";
  ctx.lineWidth = 1.4;
  ctx.setLineDash([5, 4]);
  ctx.beginPath();
  ctx.moveTo(xFor(idx), 14); ctx.lineTo(xFor(idx), H - 20);
  ctx.stroke();
  ctx.setLineDash([]);
  const d = data.densities[idx];
  els("pay-value").textContent = d.toFixed(2);
  els("scan-note").textContent =
    "d=" + d.toFixed(2) + " · chi2 p=" + data.chi2_pvalue[idx].toFixed(2) +
    " · RS=" + data.rs_rate[idx].toFixed(1) + "% · ML=" + data.ml_proba[idx].toFixed(1) + "%";
}

function loadScanData() {
  fetch("data/scan-demo.json")
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("http"))))
    .then((json) => { state.scanData = json; renderScan(); })
    .catch(() => { /* fallback array is already used */ });
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
  const fx = 16 + state.hamFocus * (cell + 8);
  ctx.setLineDash([5, 4]);
  ctx.strokeStyle = "#2e74b5";
  ctx.lineWidth = 2;
  ctx.strokeRect(fx - 4, 30, cell + 8, cell + 8);
  ctx.setLineDash([]);
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
    state.hamFocus = idx;
    state.hamX[idx] ^= 1;
    solveHamming();
  }
}

function hamKey(ev) {
  const n = state.hamX.length;
  if (ev.key === "ArrowRight" || ev.key === "ArrowDown") { state.hamFocus = (state.hamFocus + 1) % n; ev.preventDefault(); }
  else if (ev.key === "ArrowLeft" || ev.key === "ArrowUp") { state.hamFocus = (state.hamFocus - 1 + n) % n; ev.preventDefault(); }
  else if (ev.key === " " || ev.key === "Enter") { state.hamX[state.hamFocus] ^= 1; ev.preventDefault(); }
  else return;
  solveHamming();
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
  els("menu-toggle").addEventListener("click", () => {
    els("main-nav").classList.toggle("open");
  });
  document.querySelectorAll("#main-nav a").forEach((a) => {
    a.addEventListener("click", () => els("main-nav").classList.remove("open"));
  });
  const sections = ["lsb", "hamming", "wetpaper", "pipeline", "ml", "roadmap", "resources"];
  const spy = () => {
    let active = sections[0];
    for (const id of sections) {
      const el = document.getElementById(id);
      if (el && el.getBoundingClientRect().top <= 130) active = id;
    }
    document.querySelectorAll("#main-nav a").forEach((a) => {
      a.classList.toggle("active", a.getAttribute("href") === "#" + active);
    });
  };
  window.addEventListener("scroll", spy, { passive: true });
  els("lsb-embed").addEventListener("click", embedMessage);
  els("lsb-reset").addEventListener("click", resetDemo);
  els("bitplane").addEventListener("input", redrawLsb);
  els("ham-random").addEventListener("click", randomHamming);
  els("ham-solve").addEventListener("click", solveHamming);
  els("ham-p").addEventListener("change", () => { resizeHamming(); randomHamming(); });
  els("ham-m").addEventListener("change", () => { resizeHamming(); solveHamming(); });
  els("ham-canvas").addEventListener("click", hamClick);
  els("ham-canvas").addEventListener("keydown", hamKey);
  els("wet-random").addEventListener("click", wetRandom);
  els("wet-solve").addEventListener("click", wetSolve);
  els("wet-auto").addEventListener("click", wetAutoPlay);
  els("wet-stop").addEventListener("click", wetAutoStop);
  els("wet-m").addEventListener("change", wetSolve);
  els("wet-canvas").addEventListener("click", wetClick);
  els("wet-canvas").addEventListener("keydown", wetKey);
  els("thr-slider").addEventListener("input", renderThreshold);
  els("pay-slider").addEventListener("input", renderScan);
  applyLang();
  spy();
  loadScanData();
  document.querySelectorAll("main img").forEach((img) => {
    if (!img.closest(".hero-visual")) {
      img.loading = "lazy";
      img.decoding = "async";
    }
  });
}

document.addEventListener("DOMContentLoaded", init);
