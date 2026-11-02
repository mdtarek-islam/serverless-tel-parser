---
description: Prepare a semver release. Update CHANGELOG.md, run the checklist, stop for the owner token.
---

# /release

Agent: sre-release-steward. Skills: ci-cd-harness, senior-commit.

## Steps

1. Run `git status` and `git branch --show-current`. Stop if the branch is not `main` or the tree is dirty.
2. Read the commits since the last tag. Group them as Added, Changed, Fixed, Removed, Security.
3. Pick the bump: patch, minor or major. State the reason in one line.
4. Move the Unreleased entries in CHANGELOG.md under `## [<version>] - <YYYY-MM-DD>`. Keep an empty Unreleased section.
5. Set `version` in pyproject.toml to the new value.
6. Run the release checklist in ci-cd-harness. Show the evidence for each item.
7. Write the commit subject: `Release v<version>`. Keep it under 72 characters.
8. STOP. Print the staged paths and the exact commands. Wait for the owner token.

## Rules

1. Stage by exact path: CHANGELOG.md and pyproject.toml only.
2. Add no AI trailer and no Co-Authored-By line.
3. Never tag, push or deploy. The owner does these after the token.
