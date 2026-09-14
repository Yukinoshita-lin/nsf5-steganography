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

## ⚠ 不要用 `make web-convert` 覆盖已入库的 content/

2026-09-14 审计实测：**入库的 `content/*.md` 比 `docs/src/*.docx` 内容丰富得多**
（例如 `zh/content/ch07.md` 有 190 行，而当前 DOCX 只能生成 78 行）。也就是说
网页手册在某个时间点被扩充过，而 DOCX 没有同步。

因此：

- 网页手册的**事实修正**请改 `teaching/handbook_facts.py` 的 `WEB` 表，然后跑
  `python teaching/handbook_facts.py --fix --web`（它直接在 markdown 上做替换，
  不会重新生成、不会删内容）；
- `make web-convert`（DOCX → markdown）**只用于**从 DOCX 初始化一个全新的
  content 目录，或在你确认要放弃网页版增量时使用；
- 两边的口径都由 CI 的 `handbook` job 守着：陈旧结论必须消失、现口径必须出现。

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
