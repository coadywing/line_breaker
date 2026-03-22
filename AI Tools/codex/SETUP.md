# Codex Setup

This file explains how to use the Codex toolkit in a new project created from this template.

## What Plays The Role Of `CLAUDE.md`

Codex does not depend on a single `CLAUDE.md`-style file in the same way Claude Code does.

For this template, the equivalent startup guidance is split across:
- `AI Tools/codex/RULES.md`
- `AI Tools/codex/WORKFLOWS.md`
- `AI Tools/codex/AGENTS.md`
- `AI Tools/codex/AGENTS.template.md`

If you want a single-file entry point for future projects, copy `AI Tools/codex/AGENTS.template.md` to a root-level `AGENTS.md` and customize it for that specific project.

## Recommended New-Project Pattern

1. Keep `CLAUDE.md` if you still want Claude compatibility.
2. Copy `AI Tools/codex/AGENTS.template.md` to a root-level `AGENTS.md` for Codex session startup.
3. In that file, summarize:
   - project overview
   - active directories
   - data and output locations
   - coding standards
   - verification commands
   - git expectations
4. Point to repo-local support docs for details.

## Suggested Root-Level `AGENTS.md` Shape

Start from `AI Tools/codex/AGENTS.template.md` rather than writing it from scratch.

## What Belongs In Codex Files vs Shared Project Files

Put in `AI Tools/codex/`:
- Codex-specific operating instructions
- review-role definitions
- task playbooks

Put in shared project files:
- research design details
- notation conventions
- project timeline and decisions
- manuscript-specific or course-specific context

## First Upgrade Path

The next useful step is to test `AI Tools/codex/AGENTS.template.md` in a fresh cloned project and refine the sections that are still too generic.
