---
name: senior-commit
description: Professional git workflow across the sub-repos. Use for branch, pull, merge, commit and push tasks. Needs explicit user approval before any write.
---

# senior-commit

## Preconditions

1. Confirm the target repo. Each top-level folder is its own repo.
2. Run `git status` and `git branch --show-current`. Report both.
3. Stop and ask the user for approval before commit, merge or push.
4. The user creates the token: `bash .claude/hooks/ipc-bus.sh approve-git`.

## Workflow

1. Branch: `git switch -c <type>/<short-name>` from the default branch.
2. Pull: `git pull --ff-only`. Stop on a non-fast-forward result and report.
3. Stage by exact path: `git add path/to/file`. Never use `git add -A` or `git add .`.
4. Check staged files: `git diff --cached --name-only`. Reject .extra/, .dump/, models/ and weight files.
5. Commit with an imperative subject under 72 characters.
6. Merge with `--no-ff` only when the user asks. Push after approval.

## Commit rules

1. Sole author: mdtarek-islam. Set no other author.
2. Strip every AI co-author line. Add no Co-Authored-By, tool name or vendor name.
3. Follow stop-slop for the message text.
4. Never force-push. Never delete a branch. Archive instead.

## Report

1. Print the branch, the staged paths and the commit subject.
2. Print the exact command awaiting approval.
