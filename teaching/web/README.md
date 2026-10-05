# Bilingual Handbook Website (Jupyter Book)

Convert the DOCX handbooks to Jupyter Book Markdown, then build a static site
that can be hosted on GitHub Pages.

## Regenerate Markdown from DOCX

```bash
# Chinese
python teaching/web/docx2md.py \
  --docx "docs/src/学习手册-从零读懂nsF5隐写项目.docx" \
  --out teaching/web/zh --lang zh

# English
python teaching/web/docx2md.py \
  --docx "docs/src/Learning-Handbook-From-Zero-to-nsF5-Steganography.docx" \
  --out teaching/web/en --lang en
```

> 源稿 `docs/src/*.docx` 不入库（见 `.gitignore`）；`content/*.md` 与
> `assets/*` 是入库产物。2026-09-14 之前源稿放在 `thesis/` 下，该目录与
> 全部论文稿已从项目中删除。

## content/ 的再生成口径 (2026-10-05 更新)

2026-09-14 审计时的情形是"入库 content/ 比 DOCX 丰富", 但 2026-10-05 起关系
已经反转: 学习手册**正式版** (6.1 万字 / 171 页 / 91 图, 第 1½ 章、第 12 章、
附录 J/K/L 均为新增) 以 `docs/src/学习手册-从零读懂nsF5隐写项目.docx` 为唯一
母本, 网页版与入库 PDF 都由它生成。因此现在的规则是:

- `make web-convert` (DOCX → markdown) 是网页版 zh 的**常规再生成方式**;
  重生成后重跑 `python teaching/web/add_lang_switch.py`;
- 网页独有内容只剩一页: `zh/content/appF.md` (6–12 个月深入自学路线图,
  导读 0.3 引用它, DOCX 里没有对应章节)。**重生成会把它删掉**, 需要手工
  放回 (连同它引用的 `assets/roadmap.png`); 旧附录 G 已被正式版附录 J
  (章末练习提示与答案) 取代, 不再保留;
- 事实修正仍然走 `teaching/handbook_facts.py`: `--fix` 改 DOCX 源稿,
  `--fix --web` 连网页版 markdown 一起改, 改完 DOCX 后记得重导 PDF
  (`python teaching/export_handbook_pdf_word.py`) 并重新 web-convert;
- 两边的口径都由 CI 的 `handbook` job 守着: 陈旧结论必须消失、现口径必须出现
  (正式版把 0.8946/85.3% 源图泄漏事故当教学案例引用, 事实校验器为此引入了
  "事故语境豁免" —— 裸宣称仍然报红, 见 handbook_facts.py 的 INCIDENT_ALLOW)。

## 手动执行 notebook

```bash
python teaching/run_notebooks.py            # 10 本全跑（约 1 分钟）
python teaching/run_notebooks.py --only 03  # 只跑某一本
```

CI 的 `notebooks` job 会先校验 `notebooks/` 与 `teaching/build_notebooks.py`
生成结果一致，再逐本执行 —— 03 号笔记本"让学员嵌入 5000 字符而封面图只有 3494
字节容量"的坏例子就是这样被发现的。

The converter keeps headings, numbered/bulleted lists, tables, callout boxes,
code fences, and embedded images. Commit the generated `content/*.md` and
`assets/*` files so the Pages build does not need Word files.

## Build Locally

```bash
pip install -r teaching/web/requirements.txt
jupyter-book build teaching/web/zh
jupyter-book build teaching/web/en
```

Open `teaching/web/{zh,en}/_build/html/index.html`.

## Deploy

`.github/workflows/pages.yml` builds both books, merges them into one static
site (`/zh/` and `/en/` with a root redirect), and publishes it to GitHub
Pages on every push to `main` that touches `teaching/web/**`.

Site structure:

```text
site/
├── index.html        # interactive bilingual learning lab (webapp/)
├── zh/               # Chinese handbook (Jupyter Book)
└── en/               # English handbook (Jupyter Book)
```

Live URLs after deployment:

- Interactive lab: `https://yukinoshita-lin.github.io/nsf5-steganography/`
- Chinese: `https://yukinoshita-lin.github.io/nsf5-steganography/zh/content/intro.html`
- English: `https://yukinoshita-lin.github.io/nsf5-steganography/en/content/intro.html`

Deployment note: this workflow is triggered whenever `teaching/web/**` changes.
Enable GitHub Pages with **Source: GitHub Actions** in the repository settings.
