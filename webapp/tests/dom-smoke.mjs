/* Lightweight DOM smoke test (no browser): load index.html, run i18n.js and
 * app.js in linkedom, and assert the new hierarchy + FAQ rendered without errors.
 * Used when the real Chrome/Playwright pipe is unavailable in a sandbox. */
import { parseHTML } from "linkedom";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const root = path.resolve(import.meta.dirname, "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const { window } = parseHTML(html);

// minimal browser globals used by the scripts
window.localStorage = { getItem: () => null, setItem: () => {} };
window.fetch = () => Promise.reject(new Error("no network"));
window.matchMedia = window.matchMedia || (() => ({ matches: false, addListener() {}, removeListener() {} }));

const sandbox = { window, document: window.document, location: { search: "" }, URLSearchParams };
['localStorage', 'fetch', 'setTimeout', 'clearTimeout'].forEach((g) => {
  if (window[g] === undefined) sandbox[g] = globalThis[g];
  window[g] = window[g] === undefined ? globalThis[g] : window[g];
});
sandbox.localStorage = window.localStorage;
sandbox.fetch = window.fetch;
sandbox.matchMedia = window.matchMedia;
vm.createContext(sandbox);

// linkedom has no canvas rasterizer: stub getContext/getBoundingClientRect so
// the app's draw/render calls no-op instead of throwing on null.
const noopCtx = new Proxy({}, {
  get: (_t, prop) => {
    if (prop === "createImageData") {
      return (w, h) => ({ width: w, height: h, data: new Uint8ClampedArray(w * h * 4) });
    }
    if (prop === "getImageData") {
      return (x, y, w, h) => ({ width: w, height: h, data: new Uint8ClampedArray(w * h * 4) });
    }
    return () => {};
  },
  set: () => true,
});
window.HTMLCanvasElement.prototype.getContext = () => noopCtx;
window.HTMLCanvasElement.prototype.getBoundingClientRect = () => ({ left: 0, top: 0, width: 300, height: 300 });
window.HTMLElement.prototype.getBoundingClientRect = () => ({ left: 0, top: 0, width: 300, height: 300 });

const errors = [];
window.addEventListener?.("error", (e) => errors.push(String(e?.error || e)));

// include i18n.js (defines I18N, t, currentLang, applyLang is in app.js) then app.js
const i18n = fs.readFileSync(path.join(root, "js", "i18n.js"), "utf8");
const app = fs.readFileSync(path.join(root, "js", "app.js"), "utf8");
vm.runInContext(i18n + "\n;this.__I18N = I18N;\n", sandbox);
// stub t/currentLang available, then run app.js which registers DOMContentLoaded listener
// linkedom fires DOMContentLoaded on parse; manually invoke init()
vm.runInContext(app, sandbox);
// fire DOMContentLoaded if the listener exists
if (typeof sandbox.document.dispatchEvent === "function") {
  try { sandbox.document.dispatchEvent(new sandbox.window.Event("DOMContentLoaded")); } catch (e) { errors.push("DOMContentLoaded: " + String(e)); }
} else if (typeof sandbox.init === "function") {
  sandbox.init();
}

const doc = sandbox.document;
const check = (name, cond) => {
  if (!cond) errors.push("FAIL: " + name);
  else console.log("ok:", name);
};

const faqItems = doc.querySelectorAll("#faq-list .faq-item").length;
check("faq has 8 items", faqItems === 8);

const quizItems = doc.querySelectorAll("#quiz-box .quiz-item").length;
check("self-test quiz has 7 items", quizItems === 7);
const quizScore = doc.querySelector("#quiz-score-val");
check("quiz score element present", !!quizScore && quizScore.textContent.includes("7"));
const quizNav = doc.querySelector("#main-nav a[href=\"#quiz\"]");
check("quiz nav link present", !!quizNav);

const contentsParts = doc.querySelectorAll("#contents .contents-part").length;
check("contents map has 4 parts", contentsParts === 4);

const partTags = doc.querySelectorAll(".part-tag").length;
check("section part tags rendered", partTags >= 7);

const layerChips = doc.querySelectorAll("#layer-chips .plane-chip").length;
check("layer explorer chips rendered", layerChips === 8);

const faqBox = doc.querySelector("#faq-list");
check("faq-list present", !!faqBox);

// embed + decode round-trip through the LSB lab
const msgInput = doc.querySelector("#lsb-msg");
const embedBtn = doc.querySelector("#lsb-embed");
const decodeBtn = doc.querySelector("#lsb-decode");
const decodeNote = doc.querySelector("#lsb-decode-note");
const maskCaption = doc.querySelector("#lsb-mask-caption");
const detectNote = doc.querySelector("#lsb-detect-note");
const maskIdleText = maskCaption.textContent;   // idle wording before embed

msgInput.value = "RoundTrip!";
embedBtn.click();
decodeBtn.click();
const decoded = decodeNote.textContent;
check("lsb embed+decode round-trip recovers message", decoded.includes("RoundTrip!"));
check("decode note elem present", !!decodeNote);

// changed-pixel mask + real-time chi2/RS detector (only fires after embed)
check("detector note popped after embed", detectNote.textContent.includes("RS Gn"));
check("mask caption updated after embed", /\d/.test(maskCaption.textContent) && maskCaption.textContent !== maskIdleText);

// nsF5 comparison lab: syndrome + decrement + wet pixels, with round-trip
const nfMsg = doc.querySelector("#nf-msg");
const nfMethod = doc.querySelector("#nf-method");
const nfEmbedBtn = doc.querySelector("#nf-embed");
const nfDecodeBtn = doc.querySelector("#nf-decode");
const nfNote = doc.querySelector("#nf-note");
const nfReport = doc.querySelector("#nf-report");
const nfDetect = doc.querySelector("#nf-detect");
check("nsf5 nav link present", !!doc.querySelector('#main-nav a[href="#nsf5"]'));
check("nsf5 in contents map", !!doc.querySelector('#contents a[href="#nsf5"]'));
check("quiz in contents map", !!doc.querySelector('#contents a[href="#quiz"]'));
check("part5 i18n key resolves", doc.querySelector('#quiz .part-tag').textContent !== "part5");

// linkedom select.value is read-only: use the default-selected nsf5 option for the
// UI path, and call the algorithm directly for the naive-LSB comparison.
nfMsg.value = "RoundTrip!";
nfEmbedBtn.click();
check("nsf5 report rendered with efficiency + PSNR", /bit/.test(nfReport.textContent) && /PSNR/.test(nfReport.textContent));
check("nsf5 report exposes data hooks", nfReport.dataset.method === "nsf5" && Number(nfReport.dataset.changed) > 0);
nfDecodeBtn.click();
check("nsf5 decode round-trip recovers message", nfNote.textContent.includes("RoundTrip!"));
check("nsf5 detector note popped", nfDetect.textContent.includes("RS Gn"));
const nfChanged = Number(nfReport.dataset.changed);

// naive LSB on the same message must change MORE pixels than nsF5 (higher efficiency)
const bitsRt = sandbox.textToBits("RoundTrip!");
const resLsb = sandbox.nfEmbedLsb(sandbox.makeDemoImage(), bitsRt);
check("naive lsb report via direct call", resLsb.changed > 0);
check("nsf5 changes fewer pixels than naive lsb", nfChanged < resLsb.changed);
const backLsb = sandbox.bitsToText(sandbox.nfDecodeBits(resLsb.out, "lsb", 3, bitsRt.length));
check("naive lsb decode round-trip recovers message", backLsb === "RoundTrip!");

// algorithm-level invariants: wet pixels (127/128/129) never carry a change,
// every change is on a dry position, and the block round-trips. The target m is
// picked to differ from the block's initial syndrome so a change MUST happen
// (the wet solver path is exercised whenever the suggested column is wet).
const wetHit = (() => {
  if (!sandbox.nfEmbedNsf5 || !sandbox.nfDecodeBits) return "hooks missing";
  const eq = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);
  const cover = new Uint8Array([130, 128, 132, 129, 134, 127, 136]);
  const n = 7, H = sandbox.hammingMatrix(3);
  const perm = sandbox.nfPermutedIndices(7, 20260912);
  const xl = Array.from({ length: n }, (_, j) => cover[perm[j]] & 1);
  const s = sandbox.syndromeOf(H, xl);
  const bits = s.map((b, r) => (r === 0 ? b ^ 1 : b)); // force d != 0
  const res = sandbox.nfEmbedNsf5(cover, bits, 3);
  for (let i = 0; i < cover.length; i++) {
    const wet = Math.abs(cover[i] - 128) <= 1;
    if (wet && res.mark[i]) return "wet pixel modified";
    if (wet && res.out[i] !== cover[i]) return "wet pixel value changed";
    if (!wet && res.mark[i] && Math.abs(res.out[i] - cover[i]) !== 1) return "non-decrement change";
  }
  if (res.changed === 0) return "no change embedded";
  const back = sandbox.nfDecodeBits(res.out, "nsf5", 3, 3);
  return eq(back, bits) ? "ok" : "round-trip broken";
})();
check("nsf5 wet pixels untouched + dry-only decrements + round-trip", wetHit === "ok");

console.log("\nSMOKE " + (errors.length ? "FAILED (" + errors.length + ")" : "OK"));
errors.slice(0, 20).forEach((e) => console.log(" -", e));
process.exit(errors.length ? 1 : 0);
