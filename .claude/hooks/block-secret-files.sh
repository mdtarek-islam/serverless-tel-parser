#!/usr/bin/env bash
# PreToolUse Read|Grep|Glob|Bash.
# Blocks access to .env files, keys and secrets folders. Example files stay readable.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
require_jq
read_input

TARGET="$(printf '%s' "$INPUT" | jq -r '[.tool_input.file_path, .tool_input.path, .tool_input.pattern, .tool_input.glob, .tool_input.command] | map(select(. != null)) | join("\n")' 2>/dev/null)"
[ -z "$TARGET" ] && exit 0

# Remove *.example names so they never match.
CLEAN="$(printf '%s' "$TARGET" | sed -E 's#[^[:space:]"\x27/\\]*\.example##g')"
SECRET_FILE_RE='(^|[/\\\s"\x27=])(\.env(\.[A-Za-z0-9_-]+)?|[^/\\\s"\x27]*\.(pem|key)|id_rsa[^/\\\s"\x27]*|id_ed25519[^/\\\s"\x27]*)($|[\s"\x27;|&])|[/\\]secrets[/\\]'
if has_match "$CLEAN" "$SECRET_FILE_RE" -i; then
  block "Secret file access refused (.env, key, pem or secrets folder). Use the .example file."
fi
exit 0
