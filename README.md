**English** | [Українська](README.uk.md)

# InkForge

Automation toolkit that takes a weekly newspaper from raw text/photo files to
a print-ready PDF laid out in Adobe InDesign — in a few clicks instead of a
fully manual pass, while keeping the layout person able to fine-tune anything
by hand afterwards.

> **Status:** Level 1 (Content Checker) is done and tested. Level 2 (layout
> planning) has a complete, tested Python side (`inkforge-plan`); the InDesign
> ExtendScript executor handles geometric article-frame clustering, photo
> relink, headline-font alternation, and a page-specific special case (MIF
> page 1: main-article + storm-forecast slot) for the newspapers analyzed so
> far, but is still not verified against a real InDesign installation (see
> [extendscript/README.md](extendscript/README.md)). Level 3 (One-Click
> Launcher, FastAPI) now covers the full pipeline — check, plan, lay out in
> InDesign, and export a print-ready `PDF/X-1a` — as four independently
> confirmable steps; the two InDesign-COM steps are also unverified in a real
> environment.

## The problem

A small newspaper is laid out every week by hand in Adobe InDesign: the same
previous issue's `.indd` file is reused as a starting point, old text/photos
are manually replaced with new ones, and the print PDF is exported with a
fixed preset. This is repetitive but not simple to automate blindly — every
newspaper template has its own page structure, color rules, paragraph styles
and exceptions, and none of that was documented anywhere going in. InkForge
turns that tribal knowledge into versioned, testable configuration and code,
one validated step at a time, for **3 different newspaper templates**.

## Engineering highlights

- **Reverse-engineered IDML** (InDesign's zipped-XML interchange format) from
  real production files with no schema documentation available, to build a
  reliable paragraph-style → article-role mapping per newspaper.
- **Hypothesis-driven debugging of a real geometry bug**: leftover
  "pasteboard" content (never actually printed) was silently corrupting a
  page-content clustering algorithm; diagnosed via targeted bounding-box
  dumps and fixed with a strict page-membership check.
- **Config-driven architecture**: a single shared engine reads a per-newspaper
  YAML profile (`profiles/<id>.yaml`) — no newspaper-specific names, styles,
  or frame IDs are ever hardcoded in the shared code.
- **A small local FastAPI service** (`launcher/`) orchestrates the pipeline
  end to end and drives a desktop application (Adobe InDesign) via Windows
  COM automation — a real, if unconventional, backend-integration surface on
  top of the pure data-processing pieces.
- **Docs-first, incrementally shipped**: every capability lands as a small,
  independently reviewed pull request with its own commits and tests —
  architecture and requirements docs are updated alongside the code, not
  after the fact.
- **105 passing unit tests** (`pytest`) covering content parsing, layout
  planning, JSON plan serialization, and the Level 3 API (with a real,
  environment-honest test asserting the COM steps fail gracefully when
  InDesign isn't available, rather than mocking it away).

## Architecture — 4 levels of automation

| Level | What it does | Status |
|---|---|---|
| 0 | Fully manual baseline (today, before this project) | n/a |
| 1 | **Content Checker** — scans a weekly issue folder, matches text+photo files, computes word counts and photo metadata (size/DPI/color mode), reports problems, writes `manifest.json` | ✅ Done |
| 2 | **Auto-Layout** — Python planner turns `manifest.json` + a newspaper profile into `layout_plan.json`; an InDesign ExtendScript executor applies it (font preflight, running headers, geometric article-frame clustering, photo relink, headline-font alternation, and a page-specific special case for one newspaper's front page) | 🚧 In progress — all 3 profiled newspapers covered, real-InDesign verification pending |
| 3 | **One-Click Launcher** — local FastAPI web app driving Levels 1-2, plus (Windows-only) COM automation to run the InDesign executor and export a print-ready `PDF/X-1a`, without switching windows | 🚧 In progress — full pipeline wired, real-InDesign verification pending |
| 4 | Optional future extras: auto photo cropping, headline auto-balancing, batch layout for multiple newspapers, issue history/versioning | 💡 Future idea |

See [docs/architecture.md](docs/architecture.md) for the full breakdown,
including findings from analyzing real IDML samples across newspapers.

## Tech stack

- **Python** — content validation (`src/inkforge/content_checker`), layout
  planning (`src/inkforge/layout_engine`), and the Level 3 launcher
  (`src/inkforge/launcher`, FastAPI).
- **Adobe InDesign ExtendScript** — the actual in-InDesign layout automation
  and print-PDF export, because that is the most reliable way to reproduce
  real newspaper typesetting (CMYK, bleed, `PDF/X-1a:2001`).
- **pytest**, **PyYAML**, **python-docx**, **Pillow**, **FastAPI**,
  **pywin32** (Windows-only, for InDesign COM automation).

## Repository layout

```
docs/                      requirements, architecture, content-folder conventions
profiles/                  one YAML profile per newspaper (schema: profiles/schema.md)
src/inkforge/
  content_checker/         Level 1: scans an issue, builds manifest.json
  layout_engine/           Level 2 (Python side): manifest.json + profile -> layout_plan.json
  launcher/                Level 3: FastAPI app driving Levels 1-2 and InDesign
extendscript/              Level 2 (InDesign side): executor for layout_plan.json (in progress)
tests/                     pytest suite for the Python side
```

## Quick start

```bash
pip install -e ".[dev]"

# Level 1: scan an issue folder, write manifest.json
inkforge-check path/to/2026-W40_newspaper-x --newspaper "some_profile_id"

# Level 2: turn the manifest into a layout plan
inkforge-plan path/to/2026-W40_newspaper-x/manifest.json --profile some_profile_id

# Level 3: local one-click launcher (adds fastapi/uvicorn/pywin32)
pip install -e ".[launcher]"
inkforge-launcher
# -> opens a local page with 4 confirmable steps: check content, build the
#    layout plan, lay out in InDesign (COM), export a print-ready PDF (COM)

# run the test suite
pytest
```

## Documentation

The in-depth docs are written in Ukrainian, the working language of the
project and its intended end user:

- [docs/requirements.md](docs/requirements.md) — full collected requirements
  (content, typography, print, exception pages).
- [docs/architecture.md](docs/architecture.md) — the 4 automation levels, tech
  stack, findings from real IDML sample analysis, open questions.
- [docs/content-structure.md](docs/content-structure.md) — folder/file
  convention for a weekly issue.
- [Українська версія цього README](README.uk.md).

## License

[MIT](LICENSE)
