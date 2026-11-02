#!/usr/bin/env bash
# PreToolUse Bash.
# Python and pip run only through the .venv at the workspace root.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
require_jq
read_input

CMD="$(jget '.tool_input.command')"
[ -z "$CMD" ] && exit 0

# Creating the venv is the one allowed bare call.
has_match "$CMD" '\b(python3?|py)(\.exe)?\s+(-\S+\s+)*-m\s+venv\b' -i && exit 0

if has_match "$CMD" '(^|[;&|(]\s*)(sudo\s+)?(python3?|py|pip3?)(\.exe)?(\s|$)' -i; then
  block "Run Python through the venv: .venv/Scripts/python.exe <script> or .venv/Scripts/pip.exe install <pkg>"
fi
exit 0
