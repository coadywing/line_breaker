# Codex Rules

These are the default repository rules Codex should follow in projects built from this template.

## 1. Operating Model

- For non-trivial tasks, plan before editing.
- Then execute the loop: implement, verify, review, fix, re-verify.
- Do not stop at analysis when the user clearly wants code or document changes.
- Prefer direct action over long speculative proposals.
- Keep the user informed with short progress updates while working.

## 2. Project State

At the start of a substantial session, Codex should:
- read the project guidance file in use
- inspect recent git history
- inspect current uncommitted changes
- check `quality_reports/plans/` and `quality_reports/session_logs/` for recent context

At the end of a substantial session, Codex should:
- summarize what changed
- note verification status
- record next steps when useful

## 3. R Workflow Standards

- Use `data.table` as the default data-wrangling tool.
- Use `fixest` for regressions when appropriate.
- Use `ggplot2` for figures.
- Use `here()` for all project paths.
- Never use `setwd()` in project scripts.
- Avoid absolute paths.
- Load packages near the top of scripts.
- Prefer explicit code to abstraction unless repetition is risky or substantial.
- Use snake_case names throughout.

## 4. Pipeline Discipline

- Number pipeline scripts in execution order.
- Keep `code/main.r` as the orchestrator when the project has a pipeline.
- Use section separators to make scripts scan cleanly.
- Put intermediate data in `temp_data/`.
- Put final tables and figures in `outputs/`.

## 5. Crash-Stop Philosophy

- If a data integrity condition matters, fail loudly.
- Use `stopifnot()` after reading inputs, merges, and critical transforms.
- Use `stop()` with a concrete remediation message for missing prerequisites.
- Do not hide important problems with `warning()`, `tryCatch()`, `try()`, or `suppressWarnings()` in numbered pipeline scripts.

## 6. Console Hygiene

- Use `message()` for milestone-level progress only.
- Do not use `cat()` or `print()` for routine status output.
- Keep logs readable and sparse.

## 7. Figure Standards

- Create plots and save them in separate steps.
- Always specify `width` and `height` in `ggsave()`.
- Use intentional colors, not ggplot defaults, for publication figures.
- Prefer direct labels over legends when feasible.
- Use a clean custom theme with white background and minimal gridlines.

## 8. Review Discipline

- After modifying R code, run an R review pass.
- After modifying manuscripts or slides, run proofreading and, when relevant, domain review.
- Before commit, run actual verification commands rather than relying on inspection alone.
- Present findings ordered by severity.

## 9. Git Policy

- Never revert unrelated user changes.
- Avoid destructive git commands unless explicitly requested.
- Use non-interactive git commands.
- Commit messages should explain why, not just what.

## 10. Communication

- Be concise and factual.
- Surface risks and assumptions explicitly.
- When blocked, say what is blocked and what evidence is missing.
- If verification was not run, say so directly.
