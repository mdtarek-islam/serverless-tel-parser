#!/usr/bin/env bash
# Skill and hook integrity scanner.
#   (no args)             Hook mode: PreToolUse and PostToolUse on Edit|Write. Reads JSON on stdin.
#   --all                 Scan every skill and verify skills-lock.json and hooks.lock.
#   --scan <path>         Scan one file or folder.
#   --quarantine <dir>    Scan a folder. On findings, move it to .claude/quarantine/.
#   --relock              Regenerate skills-lock.json and hooks.lock after a reviewed change.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
require_jq

SKILLS_DIR="$ROOT/.claude/skills"
QUAR_DIR="$ROOT/.claude/quarantine"
SKILLS_LOCK="$ROOT/.claude/skills-lock.json"
HOOKS_LOCK="$ROOT/.claude/hooks.lock"

INJECT_RE='ignore (all )?previous|system override|curl |wget |nc -e|eval\('
PRIV_RE='sudo |chmod \+s'
HOOKMOD_RE='(>>?|\btee( -a)?|sed -i|\bmv|\bcp)\s+\S*(settings(\.local)?\.json|\.claude/hooks/)'

# scan_text <label> <text> : print findings, return 0 when clean.
scan_text() {
  local label="$1" text="$2" bad=0 out
  if out="$(printf '%s' "$text" | grep -nP "$HIDDEN_UNICODE_RE")"; then echo "FAIL $label: hidden Unicode"; bad=1; fi
  if out="$(printf '%s' "$text" | grep -niP "$INJECT_RE")"; then echo "FAIL $label: injection string: $(printf '%s' "$out" | head -n1)"; bad=1; fi
  if out="$(printf '%s' "$text" | grep -nP "$PRIV_RE")"; then echo "FAIL $label: privilege escalation: $(printf '%s' "$out" | head -n1)"; bad=1; fi
  if out="$(printf '%s' "$text" | grep -nP "$HOOKMOD_RE")"; then echo "FAIL $label: hook or settings modification: $(printf '%s' "$out" | head -n1)"; bad=1; fi
  return $bad
}

# scan_path <path> : scan every text file below path.
scan_path() {
  local p="$1" f bad=0
  while IFS= read -r f; do
    scan_text "${f#"$ROOT"/}" "$(cat "$f")" || bad=1
  done < <(find "$p" -type f \( -name '*.md' -o -name '*.sh' -o -name '*.py' -o -name '*.json' -o -name '*.txt' -o -name '*.js' \) 2>/dev/null)
  return $bad
}

relock() {
  ( cd "$ROOT/.claude" && find skills -type f | sort | xargs sha256sum | sed -E 's/^([0-9a-f]+) [ *]/\1  /' \
      | jq -R -s --argjson src "$( [ -f skills-sources.json ] && cat skills-sources.json || echo '{}' )" \
          'split("\n") | map(select(length > 0) | split("  ") | {key: .[1], value: .[0]}) | from_entries | {version: 1, algorithm: "sha256", sources: $src, files: .}' > skills-lock.json )
  ( cd "$ROOT/.claude" && sha256sum hooks/* settings.json > hooks.lock )
  echo "RELOCKED skills-lock.json and hooks.lock"
}

verify_locks() {
  local bad=0 listed actual
  if [ ! -f "$SKILLS_LOCK" ]; then echo "FAIL skills-lock.json missing"; return 1; fi
  if ! ( cd "$ROOT/.claude" && jq -r '.files | to_entries[] | "\(.value)  \(.key)"' skills-lock.json | sha256sum -c --quiet - >/dev/null 2>&1 ); then
    echo "FAIL skills-lock.json hash mismatch. Review, then run --relock."; bad=1
  fi
  listed="$(jq -r '.files | keys[]' "$SKILLS_LOCK" | sort)"
  actual="$(cd "$ROOT/.claude" && find skills -type f | sort)"
  if [ "$listed" != "$actual" ]; then echo "FAIL skills-lock.json file list differs from disk"; bad=1; fi
  if [ ! -f "$HOOKS_LOCK" ]; then echo "FAIL hooks.lock missing"; bad=1
  elif ! ( cd "$ROOT/.claude" && sha256sum -c --quiet hooks.lock >/dev/null 2>&1 ); then
    echo "FAIL hooks.lock mismatch: unauthorised hook or settings change"; bad=1
  fi
  return $bad
}

case "${1:-}" in
  all) set -- --all ;;
  --scan|--all|--quarantine|--relock|"") ;;
  *) [ -e "$1" ] && set -- --scan "$1" ;;
esac

case "${1:-}" in
  --all)
    bad=0
    scan_path "$SKILLS_DIR" || bad=1
    verify_locks || bad=1
    if [ $bad -eq 0 ]; then echo "PASS scan-skill --all"; exit 0; else echo "FAIL scan-skill --all"; exit 1; fi
    ;;
  --scan)
    [ -e "${2:-}" ] || { echo "usage: --scan <path>"; exit 1; }
    if scan_path "$2"; then echo "PASS $2"; exit 0; else echo "FAIL $2"; exit 1; fi
    ;;
  --quarantine)
    d="${2:-}"; [ -d "$d" ] || { echo "usage: --quarantine <dir>"; exit 1; }
    if scan_path "$d"; then echo "PASS $d"; exit 0; fi
    mkdir -p "$QUAR_DIR"
    dest="$QUAR_DIR/$(basename "$d").$(stamp)"
    mv "$d" "$dest" && echo "QUARANTINED $d -> ${dest#"$ROOT"/}"
    exit 1
    ;;
  --relock)
    relock; exit 0
    ;;
esac

# Hook mode.
read_input
EVENT="$(jget '.hook_event_name')"
FP="$(jget '.tool_input.file_path')"
[ -z "$FP" ] && exit 0
REL="$(rel_path "$FP")"

if [ "$EVENT" = "PreToolUse" ]; then
  case "$REL" in
    .claude/ipc/*.token) block "Approval tokens come from the user only." ;;
    .claude/hooks/*|.claude/settings.json|.claude/hooks.lock|.claude/skills-lock.json)
      token_fresh "$IPC_DIR/hooks-edit.token" 3600 \
        || block "Edit of $REL needs approval. User runs in own terminal: bash .claude/hooks/ipc-bus.sh approve-hooks" ;;
    .claude/skills/*)
      TEXT="$(new_text)"
      if ! out="$(scan_text "$REL" "$TEXT")"; then echo "$out" >&2; block "Skill content failed the security scan."; fi ;;
  esac
  exit 0
fi

if [ "$EVENT" = "PostToolUse" ]; then
  case "$REL" in
    .claude/skills/*)
      if ! out="$(scan_path "$ROOT/$REL")"; then
        echo "$out" >&2
        echo "Run: bash .claude/hooks/scan-skill.sh --quarantine .claude/skills/<name>" >&2
        exit 2
      fi ;;
  esac
fi
exit 0
