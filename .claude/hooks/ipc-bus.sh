#!/usr/bin/env bash
# File-based message bus and approval tokens under .claude/ipc/ (git-ignored).
# The user runs the approve commands. Agents cannot create tokens (see block-remote-leak.sh).
#   approve-git [minutes]   Allow git commit, merge and push for a short window.
#   approve-claude-md       Allow one CLAUDE.md edit window.
#   approve-hooks           Allow edits to hooks and settings.
#   revoke                  Archive all tokens into .dump/.claude/.
#   send <channel> <text>   Append a message.
#   read <channel>          Print a channel.
#   expire                  Archive tokens older than one hour (SessionStart).
#   status                  List live tokens.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
mkdir -p "$IPC_DIR"

make_token() { printf '%s %s\n' "$(stamp)" "${USERNAME:-user}" > "$IPC_DIR/$1.token"; echo "TOKEN $1 created"; }

archive_token() {
  local f="$1" dest="$ROOT/.dump/.claude"
  mkdir -p "$dest"
  mv "$f" "$dest/$(basename "$f").$(stamp).bak"
}

case "${1:-}" in
  approve-git)       make_token git-approved ;;
  approve-claude-md) make_token claude-md-approved ;;
  approve-hooks)     make_token hooks-edit ;;
  revoke)
    for f in "$IPC_DIR"/*.token; do [ -f "$f" ] && archive_token "$f"; done
    echo "TOKENS revoked" ;;
  expire)
    now="$(date +%s)"
    for f in "$IPC_DIR"/*.token; do
      [ -f "$f" ] || continue
      [ $((now - $(stat -c %Y "$f"))) -gt 3600 ] && archive_token "$f"
    done
    exit 0 ;;
  send)
    [ -n "${2:-}" ] || { echo "usage: send <channel> <text>"; exit 1; }
    ch="${2//[^A-Za-z0-9_-]/}"
    printf '%s\t%s\n' "$(stamp)" "${*:3}" >> "$IPC_DIR/$ch.chan" ;;
  read)
    ch="${2//[^A-Za-z0-9_-]/}"
    [ -f "$IPC_DIR/$ch.chan" ] && cat "$IPC_DIR/$ch.chan" ;;
  status)
    ls -1 "$IPC_DIR"/*.token 2>/dev/null || echo "no live tokens" ;;
  *)
    sed -n '2,11p' "${BASH_SOURCE[0]}"; exit 1 ;;
esac
