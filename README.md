# Semantic Line Breaker

A Python tool and GitHub Action that converts between paragraph format and one-sentence-per-line format for academic documents (LaTeX, Markdown, Quarto).

**The problem:** Academic writing tools want different formatting. Overleaf and most editors expect one paragraph per line. But GitHub diffs work best with one sentence per line — changing a single word in a paragraph-formatted file flags the *entire* paragraph as changed, making code review nearly impossible.

**The solution:** This tool automatically converts between the two formats, so you can edit in paragraph mode (Overleaf) and review in sentence-per-line mode (GitHub).

| Mode | Input | Output | Use case |
|------|-------|--------|----------|
| `--split` | One paragraph per line | One sentence per line | Clean git diffs |
| `--join` | One sentence per line | One paragraph per line | Overleaf readability |

## Setup for your research repo

You don't copy any files from this repo. Your research project just needs two files:

**1. Create `.linebreakfiles` in your repo root** — list the prose files to convert:

```
manuscript/0_abstract.tex
manuscript/1_introduction.tex
manuscript/2_data.tex
manuscript/3_methods.tex
manuscript/4_results.tex
manuscript/5_discussion.tex
```

**2. Create `.github/workflows/semantic-linebreak.yml`** — the workflow that calls this action. Copy the full YAML from the [workflow setup section](#step-3-add-the-workflow-yaml) below.

That's it. The workflow references this action remotely via `uses: coadywing/line_breaker@main` — GitHub Actions pulls everything it needs at runtime. Nothing gets installed in your repo.

### What happens after setup

1. **You edit in Overleaf** → Overleaf pushes to `overleaf-sync` branch → the Action automatically splits to sentence-per-line on `main`
2. **A co-author opens a PR against `main`** → clean diffs, one sentence per line → after merge, the Action joins back to paragraphs on `overleaf-sync` → Overleaf pulls the update

You never run `semantic_linebreak.py` yourself unless you want to preview changes locally with `--dry-run`.

## Quick start: local CLI

```bash
pip install pysbd

# Split: paragraph → sentence-per-line (dry run, just prints)
python semantic_linebreak.py --split manuscript/intro.tex --dry-run

# Split: modify the file in-place
python semantic_linebreak.py --split manuscript/intro.tex

# Join: sentence-per-line → paragraph
python semantic_linebreak.py --join manuscript/intro.tex

# Process multiple files listed in a manifest
python semantic_linebreak.py --split --files .linebreakfiles
```

## Setting up automated conversion with GitHub Actions

The real power of this tool is automating the conversion so that Overleaf and GitHub always stay in sync. Here's how to set it up for a research project.

### How it works

You maintain two branches:

```
  overleaf-sync                         main
  (paragraph format)                    (sentence-per-line format)
  For Overleaf editing                  For GitHub diffs & review
        │                                   │
        │  push triggers Action             │  push triggers Action
        │  paragraph → split                │  split → paragraph
        ▼                                   ▼
      main                             overleaf-sync
```

| Branch | Format | Who writes here | Purpose |
|--------|--------|-----------------|---------|
| `overleaf-sync` | Paragraph | Overleaf, anyone writing in paragraph mode | Syncs with Overleaf |
| `main` | Sentence-per-line | Co-authors editing locally, pull requests | Clean GitHub diffs |

When you push to `overleaf-sync` (e.g., Overleaf syncs edits), the Action automatically splits the prose into sentence-per-line format and commits to `main`. When you push to `main` (e.g., a co-author merges a PR), the Action joins sentences into paragraphs and commits to `overleaf-sync`.

### Step 1: Add this action repo as a dependency

No installation needed. Your workflow YAML will reference this action directly from GitHub.

### Step 2: Create `.linebreakfiles` in your repo root

List the prose files that should be converted. One path per line. Lines starting with `#` are comments. Glob patterns are supported.

```
# .linebreakfiles — files to apply semantic line breaking
# Only list prose-heavy files. Do NOT list structural files,
# exhibit files, .sty, .bib, or code.

manuscript/0_abstract.tex
manuscript/1_introduction.tex
manuscript/2_data.tex
manuscript/3_methods.tex
manuscript/4_results.tex
manuscript/5_discussion.tex
manuscript/7_appendix.tex
```

**Files to exclude** (never list these):
- `main.tex` — typically just `\input{}` and `\section{}` commands
- Exhibit/figure/table files — mostly LaTeX environments, not prose
- `.sty` / `.bib` files — preamble and bibliography, not prose
- `outputs/`, `code/` directories — not prose

### Step 3: Add the workflow YAML

Create `.github/workflows/semantic-linebreak.yml` in your repo:

```yaml
name: Semantic Line Break

on:
  push:
    branches:
      - overleaf-sync
    paths:
      - '**.tex'
      - '**.md'
      - '**.qmd'
      - '!CLAUDE.md'
      - '!README.md'
      - '!.github/**'

permissions:
  contents: write

concurrency:
  group: semantic-linebreak
  cancel-in-progress: false

jobs:
  split:
    runs-on: ubuntu-latest
    if: github.actor != 'semantic-linebreak-bot'
    steps:
      - name: Checkout main
        uses: actions/checkout@v4
        with:
          ref: main
          fetch-depth: 0

      - name: Fetch source branch
        env:
          SOURCE_BRANCH: ${{ github.ref_name }}
        run: git fetch origin "$SOURCE_BRANCH"

      - name: Get changed prose files
        id: changed
        env:
          SOURCE_BRANCH: ${{ github.ref_name }}
        run: |
          CHANGED=$(git diff --name-only "main..origin/$SOURCE_BRANCH" -- \
            '*.tex' '*.md' '*.qmd' \
            ':!CLAUDE.md' ':!README.md' ':!*.sty' ':!*.bib' \
            ':!.github/*' ':!outputs/*')

          if [ -f .linebreakfiles ]; then
            LISTED=$(grep -v '^#' .linebreakfiles | grep -v '^$')
            FILES=$(comm -12 <(echo "$CHANGED" | sort) <(echo "$LISTED" | sort))
          else
            FILES="$CHANGED"
          fi

          echo "files<<EOF" >> $GITHUB_OUTPUT
          echo "$FILES" >> $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT

      - name: Checkout prose files from source
        if: steps.changed.outputs.files != ''
        env:
          SOURCE_BRANCH: ${{ github.ref_name }}
        run: |
          echo "${{ steps.changed.outputs.files }}" | while IFS= read -r f; do
            [ -n "$f" ] && git checkout "origin/$SOURCE_BRANCH" -- "$f" 2>/dev/null || true
          done

      - name: Run semantic line breaker (split)
        if: steps.changed.outputs.files != ''
        uses: coadywing/line_breaker@main
        with:
          mode: split
          files: .linebreakfiles

      - name: Commit and push
        if: steps.changed.outputs.files != ''
        env:
          SOURCE_BRANCH: ${{ github.ref_name }}
          SOURCE_SHA: ${{ github.sha }}
        run: |
          git config user.name "semantic-linebreak-bot"
          git config user.email "bot@noreply"
          git add -A
          git diff --cached --quiet || \
            git commit -m "style: apply semantic line breaks

          Source: $SOURCE_BRANCH @ $SOURCE_SHA"
          git push origin main
```

To also sync the reverse direction (`main` → `overleaf-sync`), add a second job in the same file that triggers on `main` pushes and runs with `mode: join`. Use the same concurrency group so both directions queue instead of racing.

### Step 4: Connect Overleaf

Use [Overleaf's GitHub integration](https://www.overleaf.com/learn/how-to/GitHub_Synchronization) to sync your Overleaf project with the `overleaf-sync` branch. When you edit in Overleaf and push to GitHub, the Action automatically converts to sentence-per-line on `main`.

### Loop prevention

The workflow has three layers of protection against infinite loops:

1. **Branch filter:** Each job only triggers on its source branch
2. **Path filter:** Only triggers when `.tex`/`.md`/`.qmd` files change
3. **Actor check:** Commits by `semantic-linebreak-bot` never re-trigger the Action

## What the parser handles

The parser is designed for real academic manuscripts. It correctly handles:

- **Abbreviations:** `e.g.`, `i.e.`, `et al.`, `cf.`, `vs.`, `Fig.`, `Eq.`, `Tab.`, `Sec.` — these do not cause spurious line breaks
- **Inline math:** `$N = 140{,}562$`, `$\beta = 3.14$` — periods inside math are not sentence boundaries
- **Display math environments:** `\begin{equation}...\end{equation}`, `\begin{align*}...\end{align*}` — preserved verbatim
- **Nested LaTeX commands:** `\footnote{See \citet{smith2024} for details.}` — balanced-brace matching captures the full span
- **Structural commands:** `\section{Introduction}`, `\label{sec:intro}` — stay on their own line, never collapsed into prose
- **Trailing comments:** `This is prose. % a comment` — comment stripped before segmentation, re-attached after
- **Citations:** `\citep{...}`, `\citet{...}`, `[@key, p. 5]` — protected from splitting
- **Figures/tables with blank lines:** `\begin{figure}...\n\n\caption{...}\end{figure}` — the entire environment stays as one block
- **YAML frontmatter and code blocks:** Never touched
- **Custom macros:** `\rxObSevenNineEmw{}` and similar — preserved intact

### Idempotency and round-trip stability

Both modes are idempotent: running `--split` on already-split text produces identical output. Running `--join` on already-joined text produces identical output.

Round-trips are stable: `split → join → split` equals `split`. `join → split → join` equals `join`.

## Using the CLI locally

You don't need the GitHub Action to use this tool. You can run it locally on any file:

```bash
# Install
pip install pysbd

# Preview what split would do (no file modification)
python semantic_linebreak.py --split manuscript/intro.tex --dry-run

# Split in-place
python semantic_linebreak.py --split manuscript/intro.tex

# Join in-place
python semantic_linebreak.py --join manuscript/intro.tex

# Process all files in your manifest
python semantic_linebreak.py --split --files .linebreakfiles --dry-run
```

## Development

```bash
pip install pysbd pytest
pytest tests/ -v
```

The test suite includes 79 tests covering edge cases, idempotency, round-trip stability, and integration tests on two real academic manuscripts.
