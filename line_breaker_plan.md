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

### Two-pass block scanner

Naively splitting on blank lines (`\n\n`) fails when LaTeX environments contain internal blank lines — a `\begin{figure}...\end{figure}` with a blank line before `\caption{}` would be split into separate blocks, orphaning the `\end{figure}` and exposing the caption to sentence splitting.

**Pass 1 — Environment-aware grouping (line-level scan):**

Scan the file line by line, tracking `\begin{env}`/`\end{env}` nesting depth. While inside a protected environment (depth > 0), blank lines do NOT create block boundaries — all lines are accumulated into a single block. Only blank lines at nesting depth 0 create block boundaries.

Similarly, track fence state for code fences (`` ``` ``), Quarto divs (`:::`), and YAML frontmatter (`---`). While inside a fence, blank lines are absorbed into the current block.

```python
def scan_blocks(lines):
    """Split lines into blocks, respecting environment nesting."""
    blocks = []
    current = []
    env_depth = 0
    fence_open = False  # code fence, quarto div, or YAML frontmatter

    for line in lines:
        # Track \begin{} / \end{} nesting
        env_depth += count_begins(line) - count_ends(line)

        # Track fence state (```, :::, ---)
        if is_fence_toggle(line):
            fence_open = not fence_open

        if line.strip() == '' and env_depth == 0 and not fence_open:
            if current:
                blocks.append(current)
                current = []
            # Preserve blank lines as empty separator blocks
            blocks.append([line])
        else:
            current.append(line)

    if current:
        blocks.append(current)
    return blocks
```

**Pass 2 — Block classification:**

After grouping, classify each block:

**PROTECTED blocks (preserved verbatim):**

| Pattern | File types |
|---------|-----------|
| Any block containing `\begin{env}` where env is in PROTECTED_ENVS | .tex |
| `\[...\]`, `$$...$$` | .tex, .md, .qmd |
| Comment-only blocks (all lines start with `%`) | .tex |
| Pure LaTeX command blocks (all lines start with `\` or `%`) | .tex |
| YAML frontmatter (`---...---`) | .md, .qmd |
| Code fences (`` ``` ``) | .md, .qmd |
| Quarto div fences (`:::`) | .qmd |
| Markdown tables (`\|...\|`) | .md, .qmd |
| Markdown lists (`- `, `* `, `1. `) | .md, .qmd |

**PROSE blocks → process with split or join.**

This two-pass approach ensures that `\begin{figure}...\caption{...}...\end{figure}` is always a single protected block, regardless of internal blank lines.

### Inline protection (within prose blocks)

Before sentence tokenization, replace these with unique placeholders. Order matters — process from outermost structures inward so that nested constructs are captured as part of their parent:

1. **LaTeX commands with arguments (balanced-brace matching):**
   - Do NOT use a simple regex like `\\cmd\{[^}]*\}` — it fails on nested braces:
     ```
     \footnote{See \citet{smith2024} for details.}
     % Simple regex matches: \footnote{See \citet{smith2024}
     % Leaves orphaned:     } for details.}
     ```
   - Instead, use a custom function that counts brace depth:
     ```python
     def find_command_spans(text):
         """Find all \\command{...} spans, handling nested braces.

         Returns list of (start, end) tuples for each complete command.
         Handles: \\cmd{...}, \\cmd[...]{...}, \\cmd{...}{...}
         Also handles starred commands: \\section*{...}
         """
         spans = []
         i = 0
         while i < len(text):
             if text[i] == '\\' and i + 1 < len(text) and text[i + 1].isalpha():
                 start = i
                 # Skip command name
                 i += 1
                 while i < len(text) and text[i].isalpha():
                     i += 1
                 # Skip optional star (e.g., \section*{...})
                 if i < len(text) and text[i] == '*':
                     i += 1
                 # Consume optional [...] and required {...} groups
                 while i < len(text) and text[i] in ('[', '{'):
                     opener = text[i]
                     closer = ']' if opener == '[' else '}'
                     depth = 1
                     i += 1
                     while i < len(text) and depth > 0:
                         if text[i] == '\\' and i + 1 < len(text):
                             i += 2  # skip escaped char (\{, \}, \\, etc.)
                             continue
                         if text[i] == opener:
                             depth += 1
                         elif text[i] == closer:
                             depth -= 1
                         i += 1
                     # After closing, check for more [...]{...} groups
                 if i > start + 1:  # only record if we consumed more than just "\"
                     spans.append((start, i))
             else:
                 i += 1
         return spans
     ```
   - **Key details in the brace-tracking loop:**
     - Escape handling: if current char is `\`, skip it and the next char — this prevents `\{` and `\}` from affecting depth
     - Depth tracking uses the *matching* delimiter: inside `{...}`, `{` increments and `}` decrements; inside `[...]`, `[` increments and `]` decrements
     - After one group closes, the `while` loop checks for additional groups (e.g., `\cmd[opt]{arg1}{arg2}`)
   - This correctly handles: `\textbf{\textit{text.}}`, `\footnote{See \citet{smith2024}.}`, `\section*{Introduction}`, `\href{url}{text with \textbf{bold}.}`, `\rxObSevenNineEmw{}`

2. **Inline math:** `$...$` (non-greedy, must not match `$$`)
   - Pattern: `(?<!\$)\$(?!\$)(?:[^$\\]|\\.)*\$(?!\$)`
   - Applied after command protection, so math inside already-protected commands (like `\footnote{When $x > 0$...}`) is captured as part of the command span and not double-processed
   - Applied after line collapsing, so multi-line inline math (rare but possible) is already on one line

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
        """Replace all regex matches with unique placeholders."""
        def replacer(match):
            key = f"__PROTECTED_{uuid.uuid4().hex[:12]}__"
            self.replacements[key] = match.group(0)
            return key
        return re.sub(pattern, replacer, text, flags=flags)

    def protect_spans(self, text, spans):
        """Replace spans (from balanced-brace matcher) with placeholders.

        spans: list of (start, end) tuples, processed in reverse order
        so that indices remain valid after each replacement.
        """
        for start, end in sorted(spans, reverse=True):
            key = f"__PROTECTED_{uuid.uuid4().hex[:12]}__"
            self.replacements[key] = text[start:end]
            text = text[:start] + key + text[end:]
        return text

    def restore(self, text):
        """Restore all placeholders with original content.

        Iterates until stable, since protected spans may contain
        other placeholders (e.g., \\footnote{...\\citet{...}...}).
        """
        changed = True
        while changed:
            changed = False
            for key, value in self.replacements.items():
                if key in text:
                    text = text.replace(key, value)
                    changed = True
        return text
```

### Structural command lines

Lines that consist entirely of a LaTeX structural command must stay on their own line — they should never be collapsed into adjacent prose. These include:

- `\section{...}`, `\subsection{...}`, `\subsubsection{...}`, `\paragraph{...}` (including starred variants like `\section*{...}`)
- `\label{...}`, `\input{...}`, `\include{...}`
- `\maketitle`, `\tableofcontents`, `\newpage`, `\clearpage`
- `\begin{...}`, `\end{...}` (when at prose level, not inside a protected environment)

Detection: a line is a structural command line if `line.strip()` starts with `\` and either contains no prose text after the command, or is a sectioning command (which should stay on its own line even if followed by text on the same line). Must handle starred variants — match the command name followed by an optional `*` before `{`.

In split mode, structural command lines act as segment boundaries — they emit themselves as standalone lines and do not participate in sentence segmentation. Prose lines between them are collapsed and split normally.

### Inline comment handling

Lines like `This is prose. % this is a comment` are common in LaTeX. Before sentence segmentation:
1. Strip trailing `% comment` from each line (matching `\s*(?<!\\)%.*$`)
2. Run sentence segmentation on the prose
3. Re-attach comments to the line they came from

In join mode, comments complicate line collapsing — a line ending in `% comment` should not be joined with the next line (the `%` makes LaTeX ignore the newline, but joining would change semantics). Preserve lines with trailing comments as-is.

### Split mode (`--split`)

For each PROSE block:
1. Identify structural command lines and extract them as standalone segments
2. For remaining prose runs between structural lines:
   a. Collapse existing line breaks into spaces: `re.sub(r'\n(?!\n)', ' ', run)`
   b. Normalize multiple spaces: `re.sub(r'  +', ' ', text)`
   c. Strip and stash trailing LaTeX comments
   d. Protect inline spans with placeholders (balanced-brace matcher, then regex patterns)
   e. Run `pysbd.Segmenter(language="en", clean=False).segment(text)`
   f. Restore placeholders in each sentence
   g. Re-attach trailing comments
3. Reassemble: structural lines + split prose, joined with `\n`

### Join mode (`--join`)

For each PROSE block:
1. Identify structural command lines — keep on their own line
2. For remaining prose runs between structural lines:
   a. If any line has a trailing `%` comment, preserve that line as-is
   b. Otherwise collapse non-blank newlines into spaces: `re.sub(r'\n(?!\n)', ' ', run)`
3. Reassemble: structural lines + joined prose

No NLP needed for join — it's purely mechanical.

### Protected environments list

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
    'longtable', 'longtable*', 'landscape',
}
```

These are used by both the block scanner (Pass 1) and block classifier (Pass 2). Any block containing a `\begin{env}` where env is in this set is protected verbatim.

### File I/O conventions

- **Encoding:** Open all files as UTF-8 (`open(path, encoding='utf-8')`). If a file fails to decode, print a warning and skip it — do not crash or corrupt the file.
- **Trailing newline:** Preserve the file's original ending. If the file ended with `\n`, the output ends with `\n`. If not, don't add one.
- **Line endings:** Normalize to `\n` internally. On write, use `\n` (Unix line endings) — this is standard for git-tracked files.
- **Glob expansion:** When `--files` is used, each line in the file list is passed through `glob.glob()` so patterns like `slides/**/*.qmd` work. Lines starting with `#` are comments. Empty lines are skipped.
- **Missing files:** If a listed file does not exist, print a warning and skip it.

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

**Security note:** Never interpolate `${{ github.ref_name }}` or other GitHub context directly in `run:` blocks — a branch named `; rm -rf /` would execute. Always pass through environment variables.

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

      - name: Get changed prose files (intersected with .linebreakfiles)
        id: changed
        env:
          SOURCE_BRANCH: ${{ github.ref_name }}
        run: |
          # Get files changed on source branch
          CHANGED=$(git diff --name-only "main..origin/$SOURCE_BRANCH" -- \
            '*.tex' '*.md' '*.qmd' \
            ':!CLAUDE.md' ':!README.md' ':!*.sty' ':!*.bib' \
            ':!AI Tools/*' ':!.github/*' ':!outputs/*')

          # Intersect with .linebreakfiles — only process files that are
          # both changed AND listed in the file manifest
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
        uses: coadywing/semantic-linebreak-action@v1
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

A similar job handles the reverse (`main` → `overleaf-sync` with `--join`).

**Important:** Both directions share the same concurrency group (`semantic-linebreak`) so a split-triggered join (or vice versa) waits rather than racing.

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
- Display math environments with internal blank lines (the block scanner bug)
- Nested LaTeX commands (`\footnote{See \citet{smith2024}.}`, `\textbf{\textit{text.}}`)
- Structural command lines (`\section{}` stays on its own line)
- Trailing `%` comments on prose lines
- LaTeX commands with arguments
- Citations (LaTeX and Markdown)
- YAML frontmatter
- Code blocks
- Idempotency (split on already-split, join on already-joined)
- Round-trip stability
- Real-document smoke test (see below)

### Phase 2b: Integration tests on example manuscripts

The `example_manuscripts/` directory contains two complete academic papers for integration testing:

- **`example_manuscripts/infant_drug_tests/`** — Health economics paper with inverse propensity score weighting. Prose files are in `manuscript_for_journal/manuscript/` (00_abstract through 05_discussion).
- **`example_manuscripts/medicaid_glp/`** — Policy evaluation paper with stacked diff-in-diff design. Prose files are in `manuscript/` (00_abstract through 06_discussion).

**Prose-heavy files to test (sentence splitting candidates):**
```
example_manuscripts/infant_drug_tests/manuscript_for_journal/manuscript/00_abstract.tex
example_manuscripts/infant_drug_tests/manuscript_for_journal/manuscript/01_intro.tex
example_manuscripts/infant_drug_tests/manuscript_for_journal/manuscript/02_data.tex
example_manuscripts/infant_drug_tests/manuscript_for_journal/manuscript/03_methods.tex
example_manuscripts/infant_drug_tests/manuscript_for_journal/manuscript/04_results.tex
example_manuscripts/infant_drug_tests/manuscript_for_journal/manuscript/05_discussion.tex
example_manuscripts/medicaid_glp/manuscript/00_abstract.tex
example_manuscripts/medicaid_glp/manuscript/01_introduction.tex
example_manuscripts/medicaid_glp/manuscript/02_background.tex
example_manuscripts/medicaid_glp/manuscript/03_methods.tex
example_manuscripts/medicaid_glp/manuscript/04_data.tex
example_manuscripts/medicaid_glp/manuscript/05_results.tex
example_manuscripts/medicaid_glp/manuscript/06_discussion.tex
```

**Structural/exhibit files to exclude (but test graceful handling if accidentally included):**
```
example_manuscripts/infant_drug_tests/manuscript_for_journal/manuscript/06_figures_tables.tex
example_manuscripts/infant_drug_tests/manuscript_for_journal/manuscript/08_appendix_figures_tables.tex
example_manuscripts/medicaid_glp/manuscript/07_exhibits.tex
```

**Integration test procedure for each prose file:**
```bash
# 1. Split (paragraph → sentence-per-line)
python semantic_linebreak.py --split $FILE --dry-run > /tmp/split.tex

# 2. Verify idempotency (split again → same output)
python semantic_linebreak.py --split /tmp/split.tex --dry-run > /tmp/split2.tex
diff /tmp/split.tex /tmp/split2.tex  # must be empty

# 3. Round-trip (split → join → split → compare)
python semantic_linebreak.py --join /tmp/split.tex --dry-run > /tmp/joined.tex
python semantic_linebreak.py --split /tmp/joined.tex --dry-run > /tmp/split3.tex
diff /tmp/split.tex /tmp/split3.tex  # must be empty
```

These tests should be automated in `tests/test_linebreak.py` as parametrized pytest cases that iterate over all prose files. The example manuscripts are NOT copied into `tests/fixtures/` — they are referenced in-place from `example_manuscripts/`.

**What to look for in manual inspection of split output:**
- `\section*{...}` stays on its own line
- `\label{...}` stays on its own line
- `\footnote{...}` with nested citations is not broken mid-brace
- Custom result macros like `\rxObSevenNineEmw{}` are preserved intact
- Abbreviations (`e.g.`, `et al.`, `i.e.`) do not cause spurious line breaks
- Inline math like `$N = 140{,}562$` is not split
- Display math environments (align*, equation) are preserved verbatim
- Lines with trailing `%` comments are handled correctly

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
    - run: pip install pysbd==0.3.4
      shell: bash
    - run: python ${{ github.action_path }}/semantic_linebreak.py --${{ inputs.mode }} --files ${{ inputs.files }}
      shell: bash
```

Pin `pysbd` to a specific version — a breaking change in sentence splitting would silently alter output.

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
5. **Nested braces:** `\footnote{See \citet{smith2024} for details.}` preserved as one unit
6. **Environments with blank lines:** `\begin{figure}...\n\n...\caption{...}\n\end{figure}` stays intact
7. **Structural commands:** `\section{Intro}` stays on its own line, not merged with following prose
8. **Real-document smoke test:** Run the Phase 2b integration test procedure on all 13 prose files from both example manuscripts — idempotency and round-trip must pass on every file
9. **End-to-end (split):** Push paragraph `.tex` to `overleaf-sync` → Action commits sentence-per-line to `main`
10. **End-to-end (join):** Push sentence-per-line `.tex` to `main` → Action commits paragraph format to `overleaf-sync`
11. **No-loop:** Bot commits on either branch do not re-trigger Actions

---

## 9. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Parser corrupts a .tex file | `--dry-run` mode; git history always has the original |
| Infinite Action loop | Three-layer prevention: branch filter, path filter, actor check |
| pysbd misses an abbreviation | Custom abbreviation list in protection layer; easy to extend |
| Merge conflicts | Replace-and-commit strategy, not merge |
| YAML frontmatter corrupted | Extracted and reattached verbatim, never tokenized |
| Display math split across paragraphs | Environment-aware block scanner (Pass 1) keeps `\begin`/`\end` paired regardless of internal blank lines |
| Race condition on rapid pushes | Shared `concurrency` group across both directions with `cancel-in-progress: false` |
| Nested braces in `\footnote{}`, `\textbf{\textit{}}` | Balanced-brace matcher instead of regex; iterative placeholder restore |
| `\section{}` collapsed into prose | Structural command line detection; emitted as standalone segments |
| Shell injection in workflow YAML | All GitHub context passed through `env:` variables, never interpolated in `run:` |
| pysbd breaking change silently alters output | Version pinned in `requirements.txt` and `action.yml` |
| Non-UTF-8 encoded files | Explicit `encoding='utf-8'`; skip and warn on decode errors |
| Trailing `%` comments alter join semantics | Lines with trailing comments preserved as-is during join |
