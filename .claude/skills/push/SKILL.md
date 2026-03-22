---
name: push
description: Stage, commit, and push to GitHub with automatic SSH remote verification.
disable-model-invocation: true
argument-hint: "[optional: commit message]"
---

# Commit and Push

Stage all changes, create a commit, and push to GitHub.

## Steps

1. **Check for changes:**
   ```bash
   git status
   git diff --stat
   ```
   - If there are no staged, unstaged, or untracked changes AND no unpushed commits, tell the user "nothing to commit or push" and stop.

2. **Stage and commit (if there are uncommitted changes):**
   - Review what will be committed with `git status` and `git diff`
   - Stage tracked changes and new files: `git add -A`
   - Do NOT stage files matching .gitignore patterns (git handles this automatically)
   - Warn the user and skip any files that look like secrets (.env, credentials, tokens)
   - Create a commit with a concise message:
     - If `$ARGUMENTS` is provided, use it as the commit message
     - Otherwise, write a short descriptive message based on the changes (1-2 sentences, focus on "why" not "what")
     - End the commit message with: `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`

3. **Identify remote and branch:**
   - Remote: `origin`
   - Branch: detect with `git branch --show-current`

4. **Check remote URL format:**
   ```bash
   git remote -v
   ```
   - If the remote URL starts with `https://`, convert it to SSH:
     - Extract owner/repo from the HTTPS URL
     - Run: `git remote set-url origin git@github.com:<owner>/<repo>.git`
     - Confirm the change with `git remote -v`

5. **Test SSH connectivity:**
   ```bash
   ssh -T git@github.com 2>&1
   ```
   - Success: message contains "successfully authenticated"
   - Failure: report the error and stop. Do NOT attempt HTTPS fallback.

6. **Push:**
   ```bash
   git push -u origin <branch>
   ```

7. **Report results:**
   - Files committed (count and summary)
   - Commit hash and message
   - PUSH PASS / FAIL with details
