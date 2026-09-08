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

const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const failures = [];

for (const width of [1440, 390]) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(URL, { waitUntil: "networkidle" });
  const report = await page.evaluate(() => {
    const overflow = document.documentElement.scrollWidth - window.innerWidth;
    const images = [...document.images].map((img) => ({
      src: img.getAttribute("src"),
      broken: img.complete && img.naturalWidth === 0,
      noAlt: !img.hasAttribute("alt") || img.getAttribute("alt") === "",
    }));
    return {
      overflow,
      broken: images.filter((i) => i.broken).map((i) => i.src),
      noAlt: images.filter((i) => i.noAlt).map((i) => i.src),
      imageCount: images.length,
    };
  });
  if (report.overflow > 1) failures.push(`width ${width}: horizontal overflow ${report.overflow}px`);
  if (report.broken.length) failures.push(`width ${width}: broken images ${report.broken.join(",")}`);
  if (report.noAlt.length) failures.push(`width ${width}: images missing alt ${report.noAlt.join(",")}`);
  if (errors.length) failures.push(`width ${width}: console errors ${errors.slice(0, 3).join(" | ")}`);
  console.log(`layout ${width}px ok: images=${report.imageCount} overflow=${report.overflow}`);
  await page.close();
}

await browser.close();
if (failures.length) {
  console.error("LAYOUT_ISSUES");
  failures.slice(0, 12).forEach((f) => console.error(" -", f));
  process.exit(1);
}
console.log("LAYOUT_OK");
