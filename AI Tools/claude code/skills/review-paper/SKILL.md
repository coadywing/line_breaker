---
name: review-paper
description: Comprehensive manuscript review covering identification strategy, econometric specification, citation fidelity, and potential referee objections. Delegates to the domain-reviewer agent.
disable-model-invocation: true
argument-hint: "[paper filename or path to .tex/.pdf]"
allowed-tools: ["Read", "Grep", "Glob", "Write", "Task"]
---

# Manuscript Review

Produce a thorough, constructive review of an academic manuscript — the kind of report a top-journal referee would write.

**Input:** `$ARGUMENTS` — path to a paper (.tex, .pdf, or .qmd).

---

## Steps

1. **Locate and read the manuscript.** Check:
   - Direct path from `$ARGUMENTS`
   - `manuscript/` directory
   - Glob for partial matches

2. **Launch the `domain-reviewer` agent** to perform the substantive review:
   - The agent reviews through 5 lenses: identification, derivation, citation fidelity, code-theory alignment, and backward logic
   - It saves its report to `quality_reports/`

3. **Supplement the agent's review** with these additional checks:

   ### Writing Quality
   - Clarity and concision
   - Academic tone
   - Abstract effectively summarizes the paper
   - Tables and figures are self-contained (clear labels, notes, sources)

   ### Literature Positioning
   - Are the key papers cited?
   - Is prior work characterized accurately?
   - Is the contribution clearly differentiated from existing work?

4. **Generate 3-5 "referee objections"** — the tough questions a top referee would ask.

5. **Produce the combined review report** and save to `quality_reports/paper_review_[sanitized_name].md`

---

## Output Format

```markdown
# Manuscript Review: [Paper Title]

**Date:** [YYYY-MM-DD]
**File:** [path to manuscript]

## Summary Assessment

**Overall recommendation:** [Strong Accept / Accept / Revise & Resubmit / Reject]

[2-3 paragraph summary: main contribution, strengths, and key concerns]

## Strengths

1. [Strength 1]
2. [Strength 2]

## Major Concerns

### MC1: [Title]
- **Dimension:** [Identification / Econometrics / Argument / Literature / Writing]
- **Issue:** [Specific description]
- **Suggestion:** [How to address it]

## Minor Concerns

### mc1: [Title]
- **Issue:** [Description]
- **Suggestion:** [Fix]

## Referee Objections

### RO1: [Question]
**Why it matters:** [Why this could be fatal]
**How to address it:** [Suggested response or additional analysis]
```

---

## Principles

- **Be constructive.** Every criticism should come with a suggestion.
- **Be specific.** Reference exact sections, equations, tables.
- **Think like a referee at a top-5 journal.** What would make them reject?
- **Distinguish fatal flaws from minor issues.**
- **Acknowledge what's done well.**
