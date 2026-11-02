#!/usr/bin/env bash
# Shared helpers for governance hooks. Source this file. Do not run it.
# All hooks parse JSON with jq only. Exit 2 blocks the tool call.

export LC_ALL=C.UTF-8

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
  ROOT="$(printf '%s' "$CLAUDE_PROJECT_DIR" | sed 's#\\#/#g; s#^\([A-Za-z]\):#/\L\1#')"
else
  # Manual CLI run: derive the root from this script, so any working directory is safe.
  ROOT="$(cd "$HOOK_DIR/../.." && pwd)"
fi
CLAUDE_PROJECT_DIR="$ROOT"; export CLAUDE_PROJECT_DIR
IPC_DIR="$ROOT/.claude/ipc"

SECRET_RE='(AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,}|sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{32,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(api[_-]?key|secret|token|passwd|password)["\x27 ]*[:=]["\x27 ]*[A-Za-z0-9_/+=-]{16,})'

SLOP_WORDS_RE='\b(delve|leverage|tapestry|testament|seamless|seamlessly|cutting-edge|game-changer|unlock|unleash|elevate|foster|realm|paradigm|beacon|underscore|pivotal|meticulous|embark|symphony)\b'

# U+2013 en-dash, U+2014 em-dash, dingbat and pictograph emoji ranges, variation selector.
FORBIDDEN_DASH_EMOJI_RE='[\x{2013}\x{2014}\x{2600}-\x{27BF}\x{1F000}-\x{1FAFF}\x{FE0F}]'

# Hidden Unicode: U+200B-200D, U+2060, U+FEFF, U+E0000-E007F.
HIDDEN_UNICODE_RE='[\x{200B}-\x{200D}\x{2060}\x{FEFF}\x{E0000}-\x{E007F}]'

require_jq() {
  if ! command -v jq >/dev/null 2>&1; then
    local p
    for p in "$LOCALAPPDATA"/Microsoft/WinGet/Packages/jqlang.jq_*; do
      [ -d "$p" ] && PATH="$p:$PATH"
    done
    for p in "$LOCALAPPDATA"/Microsoft/WinGet/Links; do
      [ -d "$p" ] && PATH="$p:$PATH"
    done
    export PATH
  fi
  if ! command -v jq >/dev/null 2>&1; then
    echo "BLOCKED: jq not found. Run: winget install jqlang.jq" >&2
    exit 2
  fi
  # jq.exe on Windows ends lines with CRLF. Strip the CR so paths and hashes compare cleanly.
  eval 'jq() { command jq "$@" | tr -d "\r"; return "${PIPESTATUS[0]}"; }'
}

read_input() { INPUT="$(cat)"; }

# jget '<jq filter>' : print the value or an empty string.
jget() { printf '%s' "$INPUT" | jq -r "$1 // empty" 2>/dev/null; }

block() { echo "BLOCKED: $*" >&2; exit 2; }

stamp() { date +%Y%m%d-%H%M%S; }

# Match text against a PCRE. Usage: has_match "$text" "$regex" [grep flags]
has_match() { printf '%s' "$1" | grep -qP ${3:+"$3"} -- "$2" 2>/dev/null; }

# Convert Windows paths to Git Bash paths: D:\a\b -> /d/a/b
norm_path() { printf '%s' "$1" | sed 's#\\#/#g; s#^\([A-Za-z]\):#/\L\1#'; }

# Print the path relative to ROOT, or the absolute path if outside ROOT.
rel_path() {
  local p lp lr
  p="$(norm_path "$1")"
  lp="${p,,}"; lr="${ROOT,,}"
  if [[ "$lp" == "$lr/"* ]]; then printf '%s' "${p:$((${#lr} + 1))}"; else printf '%s' "$p"; fi
}

# Print true when the file holds a fresh approval token (max age in seconds, default 3600).
token_fresh() {
  local f="$1" max="${2:-3600}" now mt
  [ -s "$f" ] || return 1
  now="$(date +%s)"; mt="$(stat -c %Y "$f" 2>/dev/null || echo 0)"
  [ $((now - mt)) -le "$max" ]
}

# Text the tool call will write: Write content, Edit new_string, or MultiEdit new_strings.
new_text() {
  printf '%s' "$INPUT" | jq -r '[.tool_input.content, .tool_input.new_string, (.tool_input.edits[]?.new_string)] | map(select(. != null)) | join("\n")' 2>/dev/null
}
