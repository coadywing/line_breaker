# CLAUDE.md — Project Workflow Template

**Project:** [PROJECT NAME]
**Type:** [research / teaching]
**Working Branch:** main

---

## Project Overview

<!-- Describe your project in 2-3 sentences. What question does it answer? -->

[DESCRIBE YOUR PROJECT HERE]

---

## Skills (Slash Commands)

| Command | What It Does |
|---------|-------------|
| `/compile-paper` | Compile LaTeX manuscript (latexmk + biber) |
| `/run-pipeline` | Run main.r and verify all outputs |
| `/proofread [file]` | Grammar, typo, and consistency review |
| `/review-r [file]` | R code quality and reproducibility review |
| `/review-paper [file]` | Full manuscript review (identification, econometrics, citations) |
| `/validate-bib` | Cross-reference citations vs bibliography |
| `/devils-advocate [file]` | Challenge design decisions |

---

## Project Structure

<!-- Adapt to your project. Delete directories you don't need. -->

```
project/
├── CLAUDE.md
├── .claude/                     # Starts empty; copy Claude runtime assets here when needed
├── AI Tools/
│   ├── claude code/             # Versioned Claude agents, rules, skills, settings
│   └── codex/                   # Codex-specific tools and planning
├── code/
│   ├── main.r                   # Reproduces all results
│   ├── 01_clean_data.r
│   ├── 02_make_panel.r
│   ├── 03_estimation.r
│   └── 04_figures.r
├── raw_data/                    # NOT in git
├── temp_data/                   # NOT in git
├── outputs/
│   ├── tables/
│   └── figures/
├── manuscript/
│   ├── main.tex                 # Compile from project root
│   └── references.bib
├── literature/                  # NOT in git
├── quality_reports/
│   ├── plans/
│   └── session_logs/
└── lab_journal.md               # NOT in git
```

**Compilation:** `latexmk -pdf manuscript/main.tex` from the project root.

---

## What Goes in Git

- **Commit:** code, outputs (tables/figures), manuscript, .Rproj
- **Do NOT commit:** raw_data/, temp_data/, literature/, lab_journal.md, .Rhistory, .RData

---

## Lab Journal

Maintain `lab_journal.md` in the project root (gitignored). Update at session end:
- What was accomplished
- Issues encountered
- Next steps
