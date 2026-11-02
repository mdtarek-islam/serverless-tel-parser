---
name: caveman
description: Ultra-dense agent-to-agent handoff compression. Use when passing context to a subagent or ending a long session.
---

# caveman

Compress handoffs. The reader is another agent, not a person.

## Rules

1. Drop articles, filler and pleasantries.
2. Use fragments. Use `key: value` pairs.
3. Name files by exact path. Name commands in full.
4. Use symbols: `->` leads to, `!` blocked, `ok` done, `?` open question.
5. Keep the handoff under 15 lines.

## Template

```
goal: <one line>
state: ok <done> ; ! <blocked>
files: <exact paths>
next: <one action>
avoid: <known traps>
q: <open question or none>
```

## Example

```
goal: add pre-push guard
state: ok hook written ; ! no .git at root
files: .claude/hooks/pre-push.sh
next: git init, copy to .git/hooks/pre-push
avoid: no commit without token
q: none
```

## Voice rules (merged from JuliusBrussee/caveman)

1. Drop articles, filler, pleasantries and hedging.
2. Use short words. Pattern: thing, action, reason. Next step.
3. Keep code blocks, paths, commands and error text exact.
4. Say less when writing. Read less: open only the lines the task needs.
5. Same fix, fewer tokens. Never trade accuracy for brevity.

## Limits

1. Never compress secrets, paths or commands. Keep them exact.
2. Never use this style in user-facing prose or repo files.
