#!/usr/bin/env bash
# PreToolUse Write|Edit on *.md, *.svg, *.html.
# Blocks em-dashes, en-dashes, emoji and banned AI vocabulary.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
require_jq
read_input

FP="$(jget '.tool_input.file_path')"
[ -z "$FP" ] && exit 0
case "${FP,,}" in *.md|*.svg|*.html) ;; *) exit 0 ;; esac

REL="$(rel_path "$FP")"
# Doctrine files must list the banned words. Generated and vendored paths are out of scope.
case "$REL" in
  CLAUDE.md|.claude/skills/stop-slop/*|.dump/*|.venv/*|.terraform/*|*/node_modules/*) exit 0 ;;
esac

TEXT="$(new_text)"
[ -z "$TEXT" ] && exit 0

if has_match "$TEXT" "$FORBIDDEN_DASH_EMOJI_RE"; then
  block "$REL contains an em-dash, en-dash or emoji. Use commas, colons or full stops."
fi
if has_match "$TEXT" "$SLOP_WORDS_RE" -i; then
  HIT="$(printf '%s' "$TEXT" | grep -oiP "$SLOP_WORDS_RE" | sort -u | head -n3 | tr '\n' ' ')"
  block "$REL contains banned AI vocabulary: $HIT. Use plain British English."
fi
exit 0
