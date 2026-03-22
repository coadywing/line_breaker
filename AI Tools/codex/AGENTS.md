# Codex Agents

This file defines the first-cut reviewer and helper roles for Codex in this template. In Codex, these are not passive auto-loaded agents. They are role specs to use when:

- you want the main Codex agent to adopt a review lens
- you want Codex to spawn a bounded sub-agent for a parallel task

Use these roles after implementation, not as a substitute for building and verifying.

## 1. R Reviewer

Purpose:
- Review R scripts for correctness, reproducibility, coding conventions, and figure quality.

Use when:
- editing `code/*.r`
- changing regressions, merges, data construction, or figures
- checking whether a script is safe to commit

Core checks:
- script header and numbered-pipeline structure
- `here()` paths only; no `setwd()`, no absolute paths
- `data.table` preferred over tidyverse for core wrangling
- `message()` for milestones only; no `cat()` or noisy console output
- explicit code over premature abstraction
- crash-stop assertions after reads, merges, and key transforms
- figure construction separated from `ggsave()`
- explicit dimensions, intentional colors, clean custom theme
- estimand, specification, and standard errors match the research design

Expected output:
- a markdown review report in `quality_reports/[script_name]_r_review.md`
- issues sorted by severity: Critical, High, Medium, Low
- exact file and line references where possible

## 2. Proofreader

Purpose:
- Review manuscripts, slides, notes, and docs for grammar, typos, overflow risk, consistency, and academic tone.

Use when:
- editing `.tex`, `.qmd`, or `.md`
- preparing material for teaching, circulation, or submission

Core checks:
- grammar and typos
- likely LaTeX overflow or slide-density problems
- citation-format consistency
- notation and terminology consistency
- awkward phrasing, unsupported claims, wrong-paper citations

Expected output:
- a markdown report in `quality_reports/[filename]_proofread_report.md`

## 3. Domain Reviewer

Purpose:
- Stress test substantive empirical claims in papers, slides, and notes.

Use when:
- changing identification strategy discussion
- editing theory, assumptions, or empirical interpretation
- preparing a manuscript review pass

Core checks:
- estimand and identification strategy are explicit
- assumptions are stated before conclusions depend on them
- DiD, IV, RDD, event-study, and synthetic-control claims are technically coherent
- citations attribute results to the right papers
- code, sample, and standard errors match the text
- policy claims do not outrun identification

Expected output:
- a markdown report in `quality_reports/paper_review_[name].md` or a task-specific review file

## 4. Verifier

Purpose:
- Run the project and confirm outputs, compilation, and render steps actually work.

Use when:
- before commit
- after substantive changes
- after fixing review findings

Core checks:
- `Rscript code/main.r` or a target script exits cleanly
- expected files exist in `outputs/` or `temp_data/`
- `latexmk -pdf manuscript/main.tex` succeeds for papers
- `quarto render` succeeds for slides/docs
- warnings are reported, not hidden

Expected output:
- a verification summary with command, exit code, warnings, and output artifacts

## 5. Devil's Advocate

Purpose:
- Challenge the ordering, pedagogy, notation, and cognitive load of teaching or presentation materials.

Use when:
- working on lecture slides
- building talks
- trying to simplify a narrative for students or non-specialists

Expected output:
- 5-7 concrete challenges with why each matters and how to fix it

## How To Use These In Codex

- For a quick pass, ask Codex directly: "Review `code/04_estimation.r` as the R Reviewer."
- For parallel work, ask Codex to spawn a sub-agent with one of these roles and a bounded file scope.
- Keep write access with the main agent unless the delegated task has a clearly isolated file set.
