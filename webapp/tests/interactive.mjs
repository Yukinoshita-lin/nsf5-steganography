import { chromium } from "playwright-core";
import fs from "node:fs";

const URL = process.env.SITE_URL || "https://yukinoshita-lin.github.io/nsf5-steganography/";
const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium-browser",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].filter(Boolean);
const CHROME = CHROME_CANDIDATES.find((p) => fs.existsSync(p));
if (!CHROME) {
  console.error("No Chrome/Edge binary found; set CHROME_PATH");
  process.exit(2);
}

const errors = [];
const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
page.on("pageerror", (err) => errors.push(String(err)));

await page.goto(URL, { waitUntil: "networkidle" });

// 1) default Chinese
await page.waitForSelector("text=把文字藏进图片");

// 2) switch to English
await page.click("#lang-toggle");
await page.waitForSelector("text=Hide a message in an image");

// 3) LSB embed
await page.fill("#lsb-msg", "SECRET");
await page.click("#lsb-embed");
await page.waitForTimeout(120);
const lsbStats = await page.textContent("#lsb-stats");
if (!lsbStats.includes("changed pixels: ") || lsbStats.includes("changed pixels: 0")) {
  errors.push("LSB embed did not change pixels: " + lsbStats);
}

// 4) Hamming random + solve
await page.click("#ham-random");
await page.click("#ham-solve");
await page.waitForTimeout(60);
const hamInfo = await page.textContent("#ham-info");
if (!hamInfo.startsWith("s=")) errors.push("Hamming info missing: " + hamInfo);

// 5) Wet paper auto-play quick cycle then stop
await page.click("#wet-auto");
await page.waitForTimeout(1200);
await page.click("#wet-stop");
const wetInfo = await page.textContent("#wet-info");
if (!wetInfo.includes("m=")) errors.push("Wet demo did not run: " + wetInfo);

// 5b) keyboard support on interactive canvases
await page.focus("#ham-canvas");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("Space");
await page.focus("#wet-canvas");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("Space");

// 6) threshold slider
await page.$eval("#thr-slider", (el) => {
  el.value = "200";
  el.dispatchEvent(new Event("input", { bubbles: true }));
});
await page.waitForTimeout(60);
const thrStats = await page.textContent("#thr-stats");
if (!/FP=.*FN=/.test(thrStats)) errors.push("Threshold stats missing: " + thrStats);

// 7) payload slider
await page.$eval("#pay-slider", (el) => {
  el.value = "7";
  el.dispatchEvent(new Event("input", { bubbles: true }));
});
await page.waitForTimeout(120);
const scanNote = await page.textContent("#scan-note");
if (!scanNote.includes("ML=")) errors.push("Payload stats missing: " + scanNote);

// 8) mobile menu
await page.setViewportSize({ width: 390, height: 844 });
await page.reload({ waitUntil: "networkidle" });
const menuVisible = await page.locator("#menu-toggle").isVisible();
if (!menuVisible) errors.push("mobile menu button not visible");
await page.click("#menu-toggle");
if (!(await page.locator("#main-nav").evaluate((el) => el.classList.contains("open")))) {
  errors.push("mobile menu did not open");
}

console.log("INTERACTIVE_OK" + (errors.length ? " ERRORS:" + errors.length : ""));
errors.slice(0, 10).forEach((e) => console.log(" -", e.slice(0, 300)));
await browser.close();
process.exit(errors.length ? 1 : 0);
