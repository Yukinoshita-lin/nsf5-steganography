# Appendix H - Command-Line Tool and Installed Build (v1.9.0)

<!-- lang-switch -->
> [🌐 中文版](https://yukinoshita-lin.github.io/nsf5-steganography/zh/content/appH.html)



The main handbook teaches the algorithms "from the Python code outwards". Since v1.8 the project also ships two ways to complete the whole workflow **without writing a single line of code**: the graphical interface (see Ch. 2 and Ch. 10) and the command-line tool `nsf5stego`. This appendix is a quick reference for installing and using both; the commands work in Windows PowerShell and in Linux/macOS terminals alike.

> **Version note |** This appendix is updated for **v1.9.0** (2026-10). On top of the v1.8 commands `embed / extract / analyze / gui`, v1.9.0 adds the **JPEG compressed domain (`--jpeg`)** and **one-command re-runs of an experiment record (`repro`)**. Existing pixel-domain usage is unaffected.

## H.1 Three ways to install

| Form | Who it is for | How to install | Where output lands |
| --- | --- | --- | --- |
| **Windows installer** (recommended for end users) | No Python, just want the app | Download `nsf5stego-setup-<version>.exe` from `Releases` (https://github.com/Yukinoshita-lin/nsf5-steganography/releases/latest) and double-click (Simplified-Chinese wizard, per-user, no admin rights) | `%APPDATA%\nsf5stego\output` |
| **Portable zip** | No installation, carry it around | `nsf5stego-portable-<version>-win64.zip` from the same Release; unzip and run | The unzipped folder |
| **Source / PyPI** | Reading the code, scripting, CI | Source: `pip install -e .`; PyPI: `pip install nsf5stego` (1.9.0 published) | The current working directory |

Installer highlights:

- Start menu (desktop shortcut optional) → **nsF5 隐写工具**; double-clicking opens the GUI, and **no Python is required**;

- Ticking "add to user PATH" in the wizard makes the `nsf5stego` command available (reopen the terminal); uninstalling removes it from PATH again;

- If SmartScreen warns on first launch, choose "Run anyway" — the project is not code-signed.

> **Watch out |** The project supports Python 3.9, but the **JPEG compressed domain depends on the companion project [`yccstego`](https://github.com/Yukinoshita-lin/yccstego), which requires Python >= 3.10**. That dependency is installed automatically via an environment marker; when it is missing, `jpegstego.available()` is `False` and `--jpeg` reports a readable install hint, while **the pixel-domain features are completely unaffected** (the same degradation pattern as a missing `lightgbm` for ML judgment).

## H.2 Subcommand quick reference

```text
v = 200
nsf5stego --help                    # overview; --version prints the version
nsf5stego embed   cover.png -m "secret text" -p passphrase -o stego.png
nsf5stego extract stego.png -p passphrase
nsf5stego analyze stego.png --sensitivity 宽松 --json
nsf5stego repro   experiment.json -m "secret text"
nsf5stego gui                       # GUI (identical to python src/gui.py)
```

| Subcommand | What it does | Key options |
| --- | --- | --- |
| `embed <cover>` | Embed text into an image | `-m/--message` (stdin if omitted), `-o/--out`, `--jpeg`, `--quality` (1-100, default 85, `--jpeg` only), `--json` (export the experiment record), `--method {nsF5,matrix}`, `--hamming-p {1..6}` (default 3), `-p/--password` |
| `extract <stego>` | Decode the text back | `--jpeg`, `--method`, `--hamming-p`, `-p/--password` |
| `analyze <image...>` | Blind steganalysis (chi-square + RS [+ ML]) | `--jpeg`, `-s/--sensitivity {严格,均衡,宽松}` (default 均衡), `--json` |
| `repro <record.json>` | Re-run from an experiment record and verify item by item | `-m/--message`, `-c/--cover`, `-p/--password`, `-o/--out` |
| `gui` | Launch the GUI (tkinter) | — |

Three semantics worth knowing:

- **`--method` and `--hamming-p` apply to the pixel domain only**; the JPEG compressed domain is always nsF5 and does not accept them;

- **`analyze` expands wildcards itself** (the Windows shell does not), so `nsf5stego analyze *.png` works on all three platforms; an unreadable image in a batch is recorded as an `error` item and the rest still run, with an overall non-zero exit;

- **The shape of `--json` under `analyze`**: a single image prints an object, several images print an array of objects (each carrying an `image` key), so scripts can parse it reliably.

## H.3 Pixel domain vs JPEG compressed domain: the domain must match

```text
v = 200
# Pixel domain (default): flips LSBs of gray pixels, writes PNG
nsf5stego embed cover.png -m "secret" -o stego.png
nsf5stego extract stego.png
 
# JPEG compressed domain (v1.9.0): embeds in quantized DCT coefficients, writes a standard .jpg
nsf5stego embed cover.png --jpeg -m "secret" --quality 85
nsf5stego extract cover_stego.jpg --jpeg     # your embed used --jpeg, so decode needs it too
 
# Blind analysis: with --jpeg the main signal is the |c|=1 coefficient fingerprint (ML is unavailable there)
nsf5stego analyze stego.png
nsf5stego analyze cover_stego.jpg --jpeg
```

> **Watch out |** In the compressed domain the payload lives in the **quantized coefficients of the JPEG bitstream**, so the stego `.jpg` must be stored and transferred byte-for-byte — **re-encoding it with any tool destroys the payload**. The pixel domain is the opposite: PNG/BMP are lossless, so bit planes never shift.

Decoding must match embedding in **four respects**: **domain (whether `--jpeg` was used), method (`--method`), Hamming parameter p, and passphrase**. When they disagree the output is not the original text; the CLI exits with a non-zero code and says so instead of printing replacement characters.

## H.4 Experiment records and one-command re-runs (v1.9.0)

Every embed can export an **experiment record**: `embed --json` (or "export experiment record" in the GUI) prints parameters, image hashes and modification statistics as JSON with schema `nsf5stego.experiment/1`. The record **contains no plaintext**, so a re-run needs the original text again.

```text
v = 200
nsf5stego embed cover.png -m "secret" --json > experiment_20261003.json
nsf5stego repro experiment_20261003.json -m "secret"   # re-run and verify item by item
```

The verification strength of `repro` depends on the domain:

- the **pixel domain** is always **byte-deterministic**;

- the **JPEG domain** is byte-deterministic too when the `yccstego` version matches, and automatically falls back to **round-trip verification** (extraction must agree) when the version recorded in the record differs — older records stay compatible.

The passphrase is recorded **only as present/absent, never its content**, so `repro` needs you to pass it again (`-p`).

## H.5 Exit codes and common errors

| Exit code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | Runtime failure: capacity exceeded / passphrase or parameters mismatched / unreadable image |
| `2` | Argument error (argument-parsing layer) |

Scripts can judge success straight from the exit code. The three mistakes newcomers hit most:

1. **Decoding with `--jpeg` after embedding without it** (or the reverse) — the domains disagree, so nothing decodes;

2. **A mismatched p or passphrase** — the output is invalid text; the CLI exits non-zero with a hint;

3. **Using `--jpeg` on Python 3.9** — `yccstego` is missing; the error carries an install hint, and installing it or switching to the pixel domain fixes it.

## H.6 The GUI: the whole loop in one minute

The GUI loads a demo cover on first launch, and a guidance bar at the top tracks your progress and always tells you where to click next: press **"Embed and save"** (watch the modified-pixel count and the output path) → tick **"Show diff"** to zoom in on which pixels changed → press **"Decode / extract"** to confirm the text comes back intact. The whole loop takes under a minute; only then go back to the matching chapter to understand why it works.

The GUI and the CLI share one set of parameter semantics (domain / method / p / passphrase); the CLI entry point is `src/cli.py`, while the algorithm core is still `ns5_core.py`.

To go further: the command line only runs the workflow — **the principles behind the options** are still in the main text. Domains and bit planes are in Ch. 1, JPEG and DCT in Ch. 1½, matrix embedding and wet paper in Ch. 4 and 5, and the design of experiment records in Ch. 9.
