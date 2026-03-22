# Semantic Line Breaker — Implementation Plan & Specs

## Context

This tool solves a formatting conflict in academic writing workflows:

- **Writing/Editing (Overleaf, local editors):** One line per paragraph looks cleaner and is easier to read
- **Version Control (GitHub):** One sentence per line (semantic line breaking) makes diffs precise and reviewable

A bidirectional GitHub Action automates the conversion:
- **Overleaf/draft → main:** Paragraph format → sentence-per-line (for clean diffs)
- **main → overleaf-sync:** Sentence-per-line → paragraph format (for Overleaf readability)

---

## 1. Technology Stack

### Python + pysbd (Pragmatic Segmenter)

| Approach | Abbreviations | Math/LaTeX | Round-trip fidelity | Dependency weight |
|----------|:---:|:---:|:---:|:---:|
| Custom regex only | Poor | Manual | Perfect | Zero |
| Python + spaCy/NLTK | Good | Manual | Perfect | Heavy (model downloads) |
| **Python + pysbd** | **Excellent** | **Manual** | **Perfect** | **Light (~50KB)** |
| Pandoc AST (Lua filter) | Good | Native | **Poor** | Medium |

**Why pysbd:**
- Handles 100+ abbreviation edge cases out of the box (`e.g.`, `i.e.`, `et al.`, `Fig.`, `Eq.`, etc.)
- Lightweight, pure Python, no model downloads
- Fast `pip install` in CI (~2 seconds)

**Why not Pandoc AST:**
- Does not round-trip LaTeX faithfully — normalizes whitespace, rewrites citation syntax, can silently alter custom macros
- Lossy round-tripping is a dealbreaker for a formatting-only tool

### Three-layer architecture

1. **Protection:** Regex scanner replaces "no-break zones" (math, code, commands, abbreviations) with unique placeholders
2. **Tokenization:** `pysbd.Segmenter` splits remaining prose into sentences
3. **Reassembly:** Restore placeholders, join sentences with `\n`

---

## 2. Workflow Architecture

### Branch strategy (bidirectional)

```
  overleaf-sync                         main
  (one line per paragraph)              (one sentence per line)
  For Overleaf editing                  For GitHub diffs & review
        │                                   │
        │ push triggers Action              │ push triggers Action
        │ paragraph → semantic breaks       │ semantic breaks → paragraph
        ▼                                   ▼
      main                             overleaf-sync
```

| Branch | Format | Who writes | Consumed by |
|--------|--------|-----------|-------------|
| `overleaf-sync` / `draft` | Paragraph | Overleaf, or human writing in paragraph mode | Overleaf (pulls from here) |
| `main` | Sentence-per-line | Co-authors editing locally, PRs | GitHub diffs, code review |

**Two jobs in one workflow:**
1. **`split` job:** Triggered by push to `overleaf-sync`/`draft` → runs `--split` → commits to `main`
2. **`join` job:** Triggered by push to `main` → runs `--join` → commits to `overleaf-sync`

### Loop prevention (three layers)

1. **Branch filter:** Each job triggers only on its source branch and commits only to its target branch
2. **Path filter:** Trigger only when `.tex`/`.md`/`.qmd` files change (excluding `CLAUDE.md`, `README.md`, `.sty`, `.bib`, `AI Tools/`)
3. **Actor check:** `if: github.actor != 'semantic-linebreak-bot'` — bot commits on either branch won't re-trigger

### Merge conflict prevention

- Each direction does a replace-and-commit (not merge), so no three-way conflicts
- Convention: edit prose on `main` (local co-authors) or `overleaf-sync` (Overleaf), never both simultaneously on the same file

### Concurrency control

```yaml
concurrency:
  group: semantic-linebreak
  cancel-in-progress: false
```

Sequential processing ensures two rapid pushes don't collide.

---

## 3. Parser Design — Detailed Specs

### Block-level classification

Split file on blank lines (`\n\n`). Classify each block:

**PROTECTED blocks (preserved verbatim):**

| Pattern | File types |
|---------|-----------|
| `\begin{equation}`, `\begin{align}`, `\begin{gather}`, `\begin{multline}`, `\begin{eqnarray}` (and `*` variants) | .tex |
| `\[...\]`, `$$...$$` | .tex, .md, .qmd |
| `\begin{table}`, `\begin{figure}`, `\begin{tikzpicture}`, `\begin{verbatim}`, `\begin{lstlisting}` | .tex |
| `\begin{itemize}`, `\begin{enumerate}`, `\begin{description}` | .tex |
| Comment-only blocks (all lines start with `%`) | .tex |
| Pure LaTeX command blocks (all lines start with `\` or `%`) | .tex |
| YAML frontmatter (`---...---`) | .md, .qmd |
| Code fences (`` ``` ``) | .md, .qmd |
| Quarto div fences (`:::`) | .qmd |
| Markdown tables (`\|...\|`) | .md, .qmd |
| Markdown lists (`- `, `* `, `1. `) | .md, .qmd |

**PROSE blocks → process with split or join.**

### Inline protection (within prose blocks)

Before sentence tokenization, replace these with unique placeholders (order matters — larger patterns first):

1. **Inline math:** `$...$` (non-greedy, must not match `$$`)
   - Pattern: `(?<!\$)\$(?!\$)(?:[^$\\]|\\.)*\$(?!\$)`

2. **LaTeX commands with arguments:** `\command{...}`, `\command[...]{...}`
   - Pattern: `\\[a-zA-Z]+(?:\[[^\]]*\])*\{[^}]*\}`
   - Catches: `\textit{...}`, `\citet{...}`, `\citep{...}`, `\autoref{...}`, etc.

3. **Markdown citations:** `[@key]`, `[@key1; @key2]`, `[@key, p. 5]`
   - Pattern: `\[(?:@[^\]]+)\]`
   - Only for .md/.qmd files

4. **Domain abbreviations** (not already handled by pysbd):
   - `et al.`, `cf.`, `Eq.`, `Fig.`, `Tab.`, `Sec.`, `Ch.`, `No.`, `Vol.`, `pp.`, `p.`, `Ref.`, `Thm.`, `Prop.`, `Lem.`, `Cor.`, `Def.`, `Rem.`, `Assn.`

### Protection manager

```python
class ProtectionManager:
    def __init__(self):
        self.replacements = {}  # placeholder → original text

    def protect(self, text, pattern, flags=0):
        """Replace all matches with unique placeholders."""
        def replacer(match):
            key = f"__PROTECTED_{uuid.uuid4().hex[:12]}__"
            self.replacements[key] = match.group(0)
            return key
        return re.sub(pattern, replacer, text, flags=flags)

    def restore(self, text):
        """Restore all placeholders with original content."""
        for key, value in self.replacements.items():
            text = text.replace(key, value)
        return text
```

### Split mode (`--split`)

For each PROSE block:
1. Collapse existing line breaks within the block into spaces: `re.sub(r'\n(?!\n)', ' ', block)`
2. Normalize multiple spaces: `re.sub(r'  +', ' ', text)`
3. Protect inline spans with placeholders
4. Run `pysbd.Segmenter(language="en", clean=False).segment(text)`
5. Restore placeholders in each sentence
6. Join sentences with `\n`

### Join mode (`--join`)

For each PROSE block:
1. Collapse non-blank newlines into spaces: `re.sub(r'\n(?!\n)', ' ', block)`
2. Result: one line per paragraph

No NLP needed for join — it's purely mechanical.

### Mixed prose/environment blocks (.tex)

Some blocks contain interleaved prose and LaTeX environments. Handle with a line-level scanner:

```python
PROTECTED_ENVS = {
    'equation', 'equation*', 'align', 'align*', 'gather', 'gather*',
    'multline', 'multline*', 'eqnarray', 'eqnarray*',
    'table', 'table*', 'tabular', 'tabular*', 'figure', 'figure*',
    'tikzpicture', 'verbatim', 'lstlisting', 'minted',
    'itemize', 'enumerate', 'description',
    'proof', 'theorem', 'lemma', 'proposition', 'corollary',
    'definition', 'assumption', 'remark', 'example',
    'adjustwidth', 'threeparttable', 'subfigure',
}
```

Track `\begin{env}` / `\end{env}` nesting. Accumulate prose lines between environments, process them, and reassemble.

### Idempotency

Both modes are idempotent:
- `--split`: collapses lines first, then splits → same output regardless of input format
- `--join`: collapses lines → already-joined text is unchanged

### Round-trip stability

- `split → join → split` must equal `split`
- `join → split → join` must equal `join`

---

## 4. File Targeting

### `.linebreakfiles` (repo root)

A simple text file in the **consumer repo** (not this action repo) controls which files get processed:

```
# .linebreakfiles — files to apply semantic line breaking
# One path per line. Lines starting with # are comments.
# Glob patterns supported (e.g., slides/**/*.qmd)

manuscript/0_abstract.tex
manuscript/1_introduction.tex
manuscript/2_data.tex
manuscript/3_methods.tex
manuscript/4_results.tex
manuscript/5_discussion.tex
manuscript/7_appendix.tex
```

The same file list is used in both `--split` and `--join` directions.

### Files that should never be listed

- `manuscript/main.tex` — structural only (`\input`, `\section`)
- `manuscript/6_exhibits.tex` — table/figure inputs only
- `manuscript/preamble_code/*.sty` — LaTeX preamble, pure commands
- `manuscript/references.bib` — bibliography database
- `outputs/**`, `code/**`, `AI Tools/**` — not prose

---

## 5. GitHub Actions Workflow YAML (for consumer repos)

```yaml
name: Semantic Line Break

on:
  push:
    branches:
      - draft
      - overleaf-sync
    paths:
      - '**.tex'
      - '**.md'
      - '**.qmd'
      - '!CLAUDE.md'
      - '!README.md'
      - '!.github/**'
      - '!AI Tools/**'

permissions:
  contents: write

concurrency:
  group: semantic-linebreak-split
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
        run: git fetch origin ${{ github.ref_name }}

      - name: Get changed prose files
        id: changed
        run: |
          FILES=$(git diff --name-only main..origin/${{ github.ref_name }} -- \
            '*.tex' '*.md' '*.qmd' \
            ':!CLAUDE.md' ':!README.md' ':!*.sty' ':!*.bib' \
            ':!AI Tools/*' ':!.github/*' ':!outputs/*')
          echo "files=$FILES" >> $GITHUB_OUTPUT

      - name: Checkout prose files from source
        if: steps.changed.outputs.files != ''
        run: |
          for f in ${{ steps.changed.outputs.files }}; do
            git checkout origin/${{ github.ref_name }} -- "$f" 2>/dev/null || true
          done

      - name: Run semantic line breaker (split)
        if: steps.changed.outputs.files != ''
        uses: coadywing/semantic-linebreak-action@v1
        with:
          mode: split
          files: .linebreakfiles

      - name: Commit and push
        if: steps.changed.outputs.files != ''
        run: |
          git config user.name "semantic-linebreak-bot"
          git config user.email "bot@noreply"
          git add -A
          git diff --cached --quiet || \
            git commit -m "style: apply semantic line breaks

          Source: ${{ github.ref_name }} @ ${{ github.sha }}"
          git push origin main
```

A similar job handles the reverse (`main` → `overleaf-sync` with `--join`).

---

## 6. Repo Structure (this action repo)

```
semantic-linebreak-action/
├── CLAUDE.md                    # Instructions for Claude
├── action.yml                   # GitHub Action metadata
├── semantic_linebreak.py        # Main parser (~250 lines)
├── requirements.txt             # pysbd
├── tests/
│   ├── test_linebreak.py        # Pytest suite
│   └── fixtures/                # Test input/output files
│       ├── basic.tex
│       ├── math_heavy.tex
│       ├── abbreviations.tex
│       ├── quarto_doc.qmd
│       └── expected/           # Expected outputs for each fixture
├── .github/
│   └── workflows/
│       └── test.yml            # CI: run tests on PRs
└── README.md
```

---

## 7. Phased Implementation

### Phase 1: Core parser

Build `semantic_linebreak.py` with:
- `--split` and `--join` modes
- `--dry-run` flag (print to stdout, don't modify)
- `--files` flag (read file list from `.linebreakfiles`)
- Block classification for .tex, .md, .qmd
- Inline protection manager
- pysbd sentence segmentation

### Phase 2: Test suite

Build `tests/test_linebreak.py` with fixtures covering:
- Basic two-sentence paragraphs
- Abbreviations (`e.g.`, `et al.`, `Fig.`, `Eq.`)
- Inline math with periods
- Display math environments
- LaTeX commands with arguments
- Citations (LaTeX and Markdown)
- YAML frontmatter
- Code blocks
- Mixed prose/environment blocks
- Idempotency (split on already-split, join on already-joined)
- Round-trip stability

### Phase 3: GitHub Action packaging

Create `action.yml`:
```yaml
name: 'Semantic Line Breaker'
description: 'Convert between paragraph and sentence-per-line formatting'
inputs:
  mode:
    description: 'split or join'
    required: true
  files:
    description: 'Path to file listing target files (one per line)'
    required: false
    default: '.linebreakfiles'
runs:
  using: 'composite'
  steps:
    - run: pip install pysbd
      shell: bash
    - run: python ${{ github.action_path }}/semantic_linebreak.py --${{ inputs.mode }} --files ${{ inputs.files }}
      shell: bash
```

### Phase 4: CI for this repo

Create `.github/workflows/test.yml` to run pytest on PRs.

### Phase 5: Consumer repo integration

In the template repo (`coady-claude-workflow`), add:
- `.linebreakfiles`
- `.github/workflows/semantic-linebreak.yml` (referencing this action)

---

## 8. Verification Checklist

1. **Unit tests pass:** `pytest tests/ -v`
2. **Dry-run on fixtures:** `python semantic_linebreak.py --split tests/fixtures/basic.tex --dry-run`
3. **Idempotency:** Run split twice on same file → identical output
4. **Round-trip:** `split → join → split` stable; `join → split → join` stable
5. **End-to-end (split):** Push paragraph `.tex` to `overleaf-sync` → Action commits sentence-per-line to `main`
6. **End-to-end (join):** Push sentence-per-line `.tex` to `main` → Action commits paragraph format to `overleaf-sync`
7. **No-loop:** Bot commits on either branch do not re-trigger Actions

---

## 9. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Parser corrupts a .tex file | `--dry-run` mode; git history always has the original |
| Infinite Action loop | Three-layer prevention: branch filter, path filter, actor check |
| pysbd misses an abbreviation | Custom abbreviation list in protection layer; easy to extend |
| Merge conflicts | Replace-and-commit strategy, not merge |
| YAML frontmatter corrupted | Extracted and reattached verbatim, never tokenized |
| Display math split across paragraphs | Environment-aware scanner tracks `\begin`/`\end` nesting |
| Race condition on rapid pushes | `concurrency` group with `cancel-in-progress: false` |
