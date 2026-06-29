#!/bin/bash
# compact-threshold.sh — Stop hook
# Emits a reminder to stderr when the current session's last recorded
# context size exceeds the threshold. Silent otherwise.
#
# Context size = cache_read_input_tokens + cache_creation_input_tokens + input_tokens
# on the newest assistant message that carries a usage block.
#
# Default threshold matches the `/compact` rule in skills/context-discipline (80k).

set -euo pipefail

THRESHOLD="${CLAUDE_COMPACT_THRESHOLD:-80000}"

command -v jq >/dev/null 2>&1 || exit 0

INPUT=""
[ -t 0 ] || INPUT=$(cat)
[ -z "$INPUT" ] && exit 0

TRANSCRIPT=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null || true)
[ -z "$TRANSCRIPT" ] && exit 0
[ -f "$TRANSCRIPT" ] || exit 0

# Walk the last 200 lines (newest first) to find a usage block. 200 is generous —
# usage appears on every assistant message, so the last one is very near EOF.
TOKENS=$(tail -n 200 "$TRANSCRIPT" 2>/dev/null \
  | tac 2>/dev/null \
  | jq -r 'select(.message.usage) | .message.usage
           | ((.input_tokens // 0) + (.cache_read_input_tokens // 0) + (.cache_creation_input_tokens // 0))' \
  2>/dev/null \
  | head -n 1 || true)

# Fallback for platforms without `tac` (macOS default): reverse via awk.
if [ -z "$TOKENS" ]; then
  TOKENS=$(tail -n 200 "$TRANSCRIPT" 2>/dev/null \
    | awk '{a[NR]=$0} END{for (i=NR;i>=1;i--) print a[i]}' \
    | jq -r 'select(.message.usage) | .message.usage
             | ((.input_tokens // 0) + (.cache_read_input_tokens // 0) + (.cache_creation_input_tokens // 0))' \
    2>/dev/null \
    | head -n 1 || true)
fi

[ -z "$TOKENS" ] && exit 0
[ "$TOKENS" -lt "$THRESHOLD" ] 2>/dev/null && exit 0

printf '📦 Session at %s input tokens (threshold %s). Consider /compact.\n' \
  "$TOKENS" "$THRESHOLD" >&2
exit 0
