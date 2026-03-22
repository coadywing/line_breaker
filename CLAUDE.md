# CLAUDE.md — Semantic Line Breaker

## What This Project Is

A Python tool and GitHub Action that converts between two text formatting styles for academic documents (LaTeX, Markdown, Quarto):

- **Split mode (`--split`):** Paragraph format → one sentence per line (for clean git diffs)
- **Join mode (`--join`):** One sentence per line → paragraph format (for Overleaf/editor readability)

This is packaged as a **reusable GitHub Action** so any academic paper repo can reference it.

## Architecture

Three-layer design:

1. **Protection layer:** Identifies "no-break zones" (math environments, code blocks, YAML frontmatter, LaTeX commands, citations) and replaces them with unique placeholders
2. **Tokenization layer:** `pysbd.Segmenter` (Pragmatic Segmenter) splits prose at true sentence boundaries, handling abbreviations like `e.g.`, `i.e.`, `et al.`, `Fig.`, `Eq.` correctly
3. **Reassembly layer:** Restore placeholders, output one sentence per line (`--split`) or one paragraph per line (`--join`)

### Two-pass block scanner

**Pass 1 — Environment-aware grouping:** Scans line by line, tracking `\begin{}`/`\end{}` nesting depth. Blank lines inside environments do NOT create block boundaries — this ensures `\begin{figure}...\caption{}...\end{figure}` with internal blank lines stays as one block.

**Pass 2 — Block classification:** Each block is classified as **PROTECTED** (preserved verbatim) or **PROSE** (sentence-split or joined).

**Protected blocks:**
- Any block containing `\begin{env}` where env is in the protected set (equation, align, table, figure, tikzpicture, verbatim, itemize, enumerate, lstlisting, etc.)
- Display math: `$$...$$`, `\[...\]`
- Comment-only blocks (lines starting with `%`)
- Pure LaTeX command blocks (all lines start with `\` or `%`)
- YAML frontmatter (`---`), code fences (`` ``` ``), Quarto div fences (`:::`)
- Markdown tables, lists

### Structural command lines

Lines consisting entirely of a LaTeX structural command (`\section{}`, `\label{}`, `\input{}`, etc.) stay on their own line — never collapsed into adjacent prose.

### Inline protection (within prose blocks)
- Inline math: `$...$` (not `$$`)
- LaTeX commands with args: balanced-brace matcher handles nesting (e.g., `\footnote{See \citet{smith2024}.}`)
- Markdown citations: `[@key, p. 5]`
- Domain abbreviations: `et al.`, `cf.`, `Eq.`, `Fig.`, `Tab.`, `Sec.`, `No.`, `Vol.`, `pp.`, `Ref.`
- Trailing `%` comments: stripped before segmentation, re-attached after

## Key Files

| File | Purpose |
|------|---------|
| `semantic_linebreak.py` | Main parser — all logic lives here |
| `action.yml` | GitHub Action metadata (inputs, runs config) |
| `requirements.txt` | Python deps: `pysbd` |
| `tests/test_linebreak.py` | Pytest suite |
| `tests/fixtures/` | Input files and expected outputs for tests |

## CLI Interface

```bash
# Split: paragraph → sentence-per-line
python semantic_linebreak.py --split manuscript/intro.tex

# Join: sentence-per-line → paragraph
python semantic_linebreak.py --join manuscript/intro.tex

# Dry run (print to stdout, don't modify file)
python semantic_linebreak.py --split manuscript/intro.tex --dry-run

# Process multiple files listed in a config file
python semantic_linebreak.py --split --files .linebreakfiles
```

## How Consumer Repos Use This Action

A research paper repo adds two things:

1. **`.linebreakfiles`** at repo root — one file path per line:
   ```
   manuscript/0_abstract.tex
   manuscript/1_introduction.tex
   manuscript/2_data.tex
   ```

2. **`.github/workflows/semantic-linebreak.yml`** referencing this action:
   ```yaml
   uses: coadywing/semantic-linebreak-action@v1
   with:
     mode: split  # or join
     files: .linebreakfiles
   ```

## Development Commands

```bash
# Install deps
pip install pysbd pytest

# Run tests
pytest tests/ -v

# Run on a test fixture
python semantic_linebreak.py --split tests/fixtures/basic.tex --dry-run
```

## Critical Edge Cases to Handle

1. **Abbreviations:** `e.g.`, `i.e.`, `et al.`, `cf.`, `vs.`, `Prof.`, `Eq.`, `Fig.` — must NOT cause a line break
2. **Inline math with periods:** `$x = 3.14$` or `$y = mx + b$.` — period inside or after math is not a sentence boundary
3. **Display math environments:** `\begin{equation}...\end{equation}`, `\begin{align}...\end{align}` — preserve verbatim, never split
4. **Environments with internal blank lines:** `\begin{figure}...\n\n\caption{...}\n\end{figure}` must stay as one protected block
5. **Nested LaTeX commands:** `\footnote{See \citet{smith2024} for details.}` — balanced-brace matcher must capture the entire span
6. **Structural commands:** `\section{Introduction}` must stay on its own line, never collapsed with adjacent prose
7. **Trailing comments:** `This is prose. % a comment` — comment stripped before segmentation, re-attached after
8. **Citations:** `\citep{smith2024}`, `\citet{smith2024}`, `[@smith2024, p. 5]` — protect from splitting
9. **Code blocks and YAML:** Never touch content inside fences or frontmatter
10. **Idempotency:** Running `--split` on already-split text must produce identical output. Same for `--join`.
11. **Round-trip stability:** `split → join → split` must equal `split`. `join → split → join` must equal `join`.

## Conventions

- Pure Python, no external deps beyond `pysbd`
- All tests in `tests/` using pytest
- Test fixtures: put input files in `tests/fixtures/`, expected outputs in `tests/fixtures/expected/`
- The parser modifies files in-place unless `--dry-run` is passed
