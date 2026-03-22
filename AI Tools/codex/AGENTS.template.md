# AGENTS.md

Use this as the root-level `AGENTS.md` when starting a new project from this template.

## Project Overview

Describe the project in 2-3 sentences:
- the research question or teaching objective
- the main outputs you expect to produce
- any major constraints or milestones

## Key Directories

- `code/`: analysis and data-processing scripts
- `raw_data/`: manually added source data, not tracked in git
- `temp_data/`: intermediate artifacts
- `outputs/`: final tables and figures
- `manuscript/`: paper source files
- `slides/`: teaching or presentation materials
- `quality_reports/`: plans, review reports, session logs

Delete sections that do not apply for a given project.

## Working Rules

- Follow `AI Tools/codex/RULES.md`.
- Use `AI Tools/codex/WORKFLOWS.md` for recurring tasks.
- Use `AI Tools/codex/AGENTS.md` for reviewer-role definitions.
- Prefer implement -> verify -> review -> fix -> re-verify for non-trivial work.
- Do not use absolute paths or `setwd()` in project scripts.

## Verification

- Full pipeline: `Rscript code/main.r`
- Single script: `Rscript code/<script_name>.r`
- Paper compile: `latexmk -pdf manuscript/main.tex`
- Slides/docs render: `quarto render <path-to-file.qmd>`

## Git Expectations

- Do not revert unrelated changes.
- Use non-interactive git commands.
- Verify meaningful changes before commit.
- Write commit messages that explain why the change was made.

## Project-Specific Notes

Use this section for:
- notation conventions
- sample definitions
- key filenames
- recurring domain assumptions
- open risks the agent should keep in mind

## Session Continuity

At session start:
- inspect recent git history
- inspect uncommitted changes
- check `quality_reports/plans/` and `quality_reports/session_logs/`

At session end:
- summarize completed work
- note verification status
- record next steps when useful
