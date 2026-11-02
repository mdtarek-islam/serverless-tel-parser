#!/usr/bin/env bash
# CLAUDE.md governance.
#   --audit    Check the file on disk. Print PASS or FAIL.
#   (no args)  PreToolUse Write|Edit: block unapproved edits and any result above 110 lines.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
require_jq

MD="$ROOT/CLAUDE.md"
MAX_LINES=110

audit() {
  local bad=0 n sections dup line
  [ -f "$MD" ] || { echo "FAIL CLAUDE.md missing"; return 1; }
  n="$(wc -l < "$MD")"
  [ "$n" -le $MAX_LINES ] || { echo "FAIL $n lines, cap is $MAX_LINES"; bad=1; }
  sections="$(grep -cP '^## [1-6]\. ' "$MD")"
  [ "$sections" -eq 6 ] || { echo "FAIL $sections numbered sections, need 6"; bad=1; }
  grep -qP "$FORBIDDEN_DASH_EMOJI_RE" "$MD" && { echo "FAIL em-dash, en-dash or emoji present"; bad=1; }
  grep -q $'\r' "$MD" && { echo "FAIL CRLF line endings"; bad=1; }
  # Deduplication: no long line may repeat inside a skill file.
  dup=0
  while IFS= read -r line; do
    [ ${#line} -ge 50 ] || continue
    if grep -rqxF -- "$line" "$ROOT/.claude/skills" 2>/dev/null; then echo "FAIL duplicate in skills: ${line:0:60}"; dup=1; fi
  done < "$MD"
  [ $dup -eq 0 ] || bad=1
  if [ $bad -eq 0 ]; then echo "PASS guard-claude-md --audit ($n lines, $sections sections)"; return 0; fi
  echo "FAIL guard-claude-md --audit"; return 1
}

if [ "${1:-}" = "--audit" ]; then audit; exit $?; fi

read_input
FP="$(jget '.tool_input.file_path')"
[ -z "$FP" ] && exit 0
[ "$(rel_path "$FP")" = "CLAUDE.md" ] || exit 0

token_fresh "$IPC_DIR/claude-md-approved.token" 3600 \
  || block "CLAUDE.md edit needs approval of the exact diff. User runs: bash .claude/hooks/ipc-bus.sh approve-claude-md"

TOOL="$(jget '.tool_name')"
CUR=0; [ -f "$MD" ] && CUR="$(wc -l < "$MD")"
if [ "$TOOL" = "Write" ]; then
  NEW="$(jget '.tool_input.content' | wc -l)"
else
  OLD="$(jget '.tool_input.old_string' | wc -l)"
  ADD="$(jget '.tool_input.new_string' | wc -l)"
  NEW=$((CUR - OLD + ADD))
fi
[ "$NEW" -le $MAX_LINES ] || block "CLAUDE.md would reach $NEW lines. Cap is $MAX_LINES. Compress first."
exit 0
