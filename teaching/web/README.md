# Bilingual Handbook Website (Jupyter Book)

Convert the DOCX handbooks to Jupyter Book Markdown, then build a static site
that can be hosted on GitHub Pages.

## Regenerate Markdown from DOCX

```bash
# Chinese
python teaching/web/docx2md.py \
  --docx "thesis/学习手册-从零读懂nsF5隐写项目.docx" \
  --out teaching/web/zh --lang zh

# English
python teaching/web/docx2md.py \
  --docx "thesis/Learning-Handbook-From-Zero-to-nsF5-Steganography.docx" \
  --out teaching/web/en --lang en
```

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
├── index.html        # redirect to /zh/intro.html
├── zh/               # Chinese handbook
└── en/               # English handbook
```

Deployment note: this workflow is triggered whenever `teaching/web/**` changes.
Enable GitHub Pages with **Source: GitHub Actions** in the repository settings.
