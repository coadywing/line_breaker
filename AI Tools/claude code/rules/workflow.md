# Workflow: Plan → Build → Verify

## Plan First

For non-trivial tasks (multi-file, unclear approach, new features), **enter plan mode before writing code:**

1. Use `EnterPlanMode`
2. Draft the plan — what changes, which files, in what order
3. Save to `quality_reports/plans/YYYY-MM-DD_short-description.md`
4. Present to user and wait for approval
5. Exit plan mode, then implement

Skip planning for: single-file edits, running existing skills, informational questions.

## The Orchestrator Loop

After plan approval, execute autonomously:

```
IMPLEMENT → VERIFY → REVIEW (agents) → FIX → RE-VERIFY → SCORE
```

- **Verify:** compile/render/run code and confirm outputs exist
- **Review:** launch appropriate agents by file type (.tex → proofreader, .R → r-reviewer, etc.)
- **Fix:** critical → major → minor
- **Score:** apply quality thresholds (see below)
- **Max 3 review-fix rounds.** After that, present what remains.

"Just do it" mode (user says "handle it"): skip final approval pause, auto-commit if score >= 80.

## Quality Thresholds

- **80/100** — ready to commit
- **90/100** — ready for PR

## Session Management

**Start:** Read CLAUDE.md → check `git log` → check `quality_reports/plans/` for in-progress work.

**During:** Save important decisions to disk (session logs, plan updates). Prefer auto-compression over `/clear`.

**End:** Save session log to `quality_reports/session_logs/YYYY-MM-DD_description.md`. Note what was done and what's next.

**Recovery** (after compression or new session): Read most recent plan + `git log --oneline -10` + `git diff`. State what you understand the current task to be.

## Continuous Learning

When a mistake is corrected, save a `[LEARN:tag]` entry to MEMORY.md:
```
[LEARN:r-code] fread silently drops rows when ... → use ...
```
