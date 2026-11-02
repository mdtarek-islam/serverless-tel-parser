#!/usr/bin/env bash
# PreToolUse Bash.
# Rejects git commit and gh pr commands that carry AI attribution.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
require_jq
read_input

CMD="$(jget '.tool_input.command')"
[ -z "$CMD" ] && exit 0
has_match "$CMD" '\bgit\s+(-C\s+\S+\s+)?commit\b|\bgh\s+pr\b' -i || exit 0

CWD="$(jget '.cwd')"; [ -z "$CWD" ] && CWD="$ROOT"
CWD="$(norm_path "$CWD")"

# Include the text of any message file passed with -F or --file.
TEXT="$CMD"
MF="$(printf '%s' "$CMD" | grep -oP '(?:\s-F|--file[= ])\s*\K[^\s"\x27]+' | head -n1)"
if [ -n "$MF" ]; then
  case "$MF" in /*|[A-Za-z]:*) MP="$(norm_path "$MF")" ;; *) MP="$CWD/$MF" ;; esac
  [ -f "$MP" ] && TEXT="$TEXT"$'\n'"$(cat "$MP")"
fi

# Ignore path-like references to the .claude folder and CLAUDE.md.
CLEAN="$(printf '%s' "$TEXT" | sed -E 's#[^[:space:]"]*\.claude[^[:space:]"]*##g; s#CLAUDE\.md##g')"
if has_match "$CLEAN" 'co-authored-by|\bclaude\b|anthropic' -i; then
  block "AI attribution found (Co-Authored-By, Claude or Anthropic). Sole author is mdtarek-islam."
fi
exit 0
