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

学习手册正式版 (zh 6.1 万字 / 176 页, en 129 页) 以 `docs/src/*.docx` 为唯一
母本, 网页版与入库 PDF 都由它们生成。中英两本 DOCX 的章节集已对齐
(第 12 章 + 附录 A–F/H/J/K/L; 附录 G 已被附录 J 取代)。因此现在的规则是:

- `make web-convert` (DOCX → markdown) 是两本书的**常规再生成方式**;
  重生成后重跑 `python teaching/web/add_lang_switch.py`;
- en 的新章 (ch12/appF/H/J/K/L) 是 2026-10-05 用
  `F:\宣传片\handbook_build\inject_chapters.py` 从翻译稿注入 DOCX 的
  (克隆目标文档样式; en 网页图片命名 img109-117, 避开旧页面引用的
  img009-011), 之后 en 与 zh 一样整体重生成即可;
- 事实修正仍然走 `teaching/handbook_facts.py`: `--fix` 改 DOCX 源稿,
  `--fix --web` 连网页版 markdown 一起改, 改完 DOCX 后记得重导 PDF
  (`python teaching/export_handbook_pdf_word.py`) 并重新 web-convert;
- 两边的口径都由 CI 的 `handbook` job 守着: 陈旧结论必须消失、现口径必须出现
  (源图泄漏事故的 0.8946/85.3% 属于"事故语境豁免", 裸宣称仍然报红,
  见 handbook_facts.py 的 INCIDENT_ALLOW)。

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
