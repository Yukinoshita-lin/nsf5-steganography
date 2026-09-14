/**
 * 无障碍自动审计 (axe-core) —— 2026-09-14 新增。
 *
 * 背景: 站点里有 28 处手写的 aria-/role/skip-link, 但**没有任何自动检查**。
 * 手写的东西最容易在后续改版里悄悄退化, 而这是教学站点 —— 学生里本来就有
 * 需要屏幕阅读器或以键盘操作为主的人。
 *
 * 判定规则: 只对 serious / critical 级别的违规判失败 (minor/moderate 会打印
 * 但不阻断 CI), 因为它们大多是真实内容问题, 需要逐条判断而不是机械修。
 * 例外清单见 ALLOW: 每条都要写清为什么可以接受。
 */
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
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

// 允许的违规 (rule id -> 原因)。当前为空: 一旦出现就说明是新增问题。
const ALLOW = new Map([]);
const BLOCKING = new Set(["serious", "critical"]);

const axePath = path.join(HERE, "node_modules", "axe-core", "axe.min.js");
if (!fs.existsSync(axePath)) {
  console.error("axe-core 未安装: 在 webapp/tests 下跑 `npm ci`");
  process.exit(2);
}
const axeSource = fs.readFileSync(axePath, "utf8");

const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const failures = [];
const notes = [];

for (const width of [1440, 390]) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  await page.goto(URL, { waitUntil: "networkidle" });
  await page.addScriptTag({ content: axeSource });
  const result = await page.evaluate(async () => {
    return await window.axe.run(document, {
      resultTypes: ["violations"],
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
    });
  });
  for (const v of result.violations) {
    const targets = v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(", ");
    const line = `[${v.impact}] ${v.id} @${width}px: ${v.help} (${v.nodes.length} 处; 例: ${targets})`;
    if (ALLOW.has(v.id)) {
      notes.push(`${line} —— 已列入例外: ${ALLOW.get(v.id)}`);
    } else if (BLOCKING.has(v.impact)) {
      failures.push(line);
    } else {
      notes.push(line);
    }
  }
  console.log(`a11y ${width}px: ${result.violations.length} 类违规 ` +
              `(${result.passes.length} 项通过)`);
  await page.close();
}

await browser.close();
for (const n of notes.slice(0, 10)) console.log("  note:", n);
if (failures.length) {
  console.error("A11Y_FAILED");
  failures.slice(0, 12).forEach((f) => console.error(" -", f));
  process.exit(1);
}
console.log("A11Y_OK");
