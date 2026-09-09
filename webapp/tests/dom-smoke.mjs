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

console.log("\nSMOKE " + (errors.length ? "FAILED (" + errors.length + ")" : "OK"));
errors.slice(0, 20).forEach((e) => console.log(" -", e));
process.exit(errors.length ? 1 : 0);
