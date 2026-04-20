#!/usr/bin/env bash
# Pull live edits from ~/.claude/ back into the claude-config repo,
# so they can be committed and replicated to other devices.
#
# What it syncs:
#   ~/.claude/CLAUDE.md              -> repo/global/CLAUDE.md
#   ~/.claude/statusline-command.sh  -> repo/global/statusline.sh
#   ~/.claude/settings.json          -> repo/global/settings.template.json
#                                       (with $HOME/$USER → ${HOME}/${USER})
#
# Skills are NOT touched — they are symlinked, repo already sees changes.
#
# Modes:
#   (default)   apply changes, then run `git status` so the user can review
#   --dry-run   show diffs only, change nothing
#   --help      show this message
#
# Run from anywhere — script resolves its own location.

set -euo pipefail

DRY_RUN=0

usage() {
  sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) printf "unknown arg: %s\n" "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLAUDE_DIR="${HOME}/.claude"

log()  { printf "[sync->repo] %s\n" "$*"; }
warn() { printf "[sync->repo] WARN: %s\n" "$*" >&2; }
die()  { printf "[sync->repo] FATAL: %s\n" "$*" >&2; exit 1; }

for cmd in git jq diff; do
  command -v "$cmd" >/dev/null 2>&1 || die "missing required command: $cmd"
done

mkdir -p "${REPO_DIR}/global"

# sync_file <live> <repo>
sync_file() {
  local live="$1" repo="$2" label
  label="$(basename "$repo")"
  if [ ! -f "$live" ]; then
    warn "live file missing, skipping: $live"
    return 0
  fi
  if [ -f "$repo" ] && diff -q "$live" "$repo" >/dev/null 2>&1; then
    log "unchanged: $label"
    return 0
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    log "would update $label:"
    diff -u "${repo:-/dev/null}" "$live" || true
    return 0
  fi
  cp "$live" "${repo}.tmp"
  mv "${repo}.tmp" "$repo"
  log "updated: $label"
}

# sync_settings_template — strip per-host literals back to placeholders
sync_settings_template() {
  local live="${CLAUDE_DIR}/settings.json"
  local repo="${REPO_DIR}/global/settings.template.json"
  local out
  out="$(mktemp -t claude-settings-tpl.XXXXXX)"
  trap 'rm -f "$out"' RETURN

  if [ ! -f "$live" ]; then
    warn "no live settings.json — skipping template sync"
    return 0
  fi

  jq --arg home "$HOME" --arg user "$USER" \
     'walk(if type == "string"
           then gsub($home; "${HOME}") | gsub($user; "${USER}")
           else . end)' \
     "$live" > "$out" || die "jq placeholder-substitution failed"

  jq empty "$out" >/dev/null || die "rendered template is invalid JSON"

  if [ -f "$repo" ] && diff -q "$repo" "$out" >/dev/null 2>&1; then
    log "unchanged: settings.template.json"
    return 0
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    log "would update settings.template.json:"
    diff -u "${repo:-/dev/null}" "$out" || true
    return 0
  fi
  mv "$out" "$repo"
  log "updated: settings.template.json"
}

sync_file "${CLAUDE_DIR}/CLAUDE.md"             "${REPO_DIR}/global/CLAUDE.md"
sync_file "${CLAUDE_DIR}/statusline-command.sh" "${REPO_DIR}/global/statusline.sh"
sync_settings_template

if [ "$DRY_RUN" -eq 1 ]; then
  log "dry-run complete — repo unchanged"
  exit 0
fi

log "sync done. Repo status:"
git -C "$REPO_DIR" status --short
log "Review the diff and commit when ready:"
log "  git -C ${REPO_DIR} diff"
log "  git -C ${REPO_DIR} add -p && git -C ${REPO_DIR} commit"
