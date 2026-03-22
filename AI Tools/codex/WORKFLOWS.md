# Codex Workflows

These workflows translate the recurring Claude toolkit tasks into Codex-style operating procedures.

## 1. Build Workflow

Use for multi-file code or writing tasks.

1. Read current project guidance and inspect the worktree.
2. Draft a short implementation plan.
3. Make the requested changes.
4. Run verification commands.
5. Review the changed files with the relevant agent lens.
6. Fix the highest-severity issues.
7. Re-run verification.
8. Report what changed, what was verified, and what remains.

## 2. Run The R Pipeline

Default command:

```bash
Rscript code/main.r
```

Checks:
- exit code is zero
- expected files exist in `outputs/tables/`, `outputs/figures/`, and relevant `temp_data/` locations
- created files have non-zero size
- warnings and errors are summarized

If a single script is being tested:

```bash
Rscript code/<script_name>.r
```

## 3. Compile The Paper

Preferred command from project root:

```bash
latexmk -pdf manuscript/main.tex
```

Fallback:

```bash
pdflatex -interaction=nonstopmode manuscript/main.tex
biber main
pdflatex -interaction=nonstopmode manuscript/main.tex
pdflatex -interaction=nonstopmode manuscript/main.tex
```

Checks:
- exit code
- undefined references or citations
- overfull hbox warnings
- generated PDF exists and has non-zero size

## 4. Proofread A Document

Use on `.tex`, `.qmd`, or `.md`.

Review for:
- grammar and typos
- consistency of notation and citations
- overflow or slide-density risks
- awkward or under-supported academic claims

Save results to:

```text
quality_reports/[filename]_proofread_report.md
```

## 5. Review An R Script

Use on modified `.r` files after implementation.

Review for:
- path and package discipline
- data.table usage
- defensive assertions
- figure style
- domain correctness
- professional polish

Save results to:

```text
quality_reports/[script_name]_r_review.md
```

## 6. Review A Manuscript

Use the domain-reviewer lens when manuscripts or slides make substantive causal or econometric claims.

Focus on:
- identification assumptions
- estimation and inference
- citation fidelity
- code-theory alignment
- logic from evidence to conclusion

## 7. Validate Bibliography

Check:
- citation keys used in `.tex` and `.qmd`
- keys present in `manuscript/references.bib` or the bibliography file declared in Quarto YAML
- unused entries
- malformed or incomplete entries

Treat missing keys as critical.

## 8. Commit Workflow

Before commit:
- inspect `git status`
- inspect `git diff --stat` and relevant diffs
- verify the project or changed artifacts

Then:
- stage intended files
- write a concise commit message focused on why
- do not stage secrets or local junk

## 9. Session Logging

For substantial work, save:
- plans to `quality_reports/plans/`
- session summaries to `quality_reports/session_logs/`

The goal is continuity across sessions, not exhaustive journaling.
