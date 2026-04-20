#!/bin/bash
# compact-threshold.sh — Stop hook
# Emits a reminder to stderr when the current session's last recorded
# input_tokens exceed the threshold. Silent otherwise.
#
# Threshold is input_tokens (not jsonl bytes) because the harness counts tokens,
# not bytes, and the right moment to compact is mid-growth, not at the limit.

set -euo pipefail

THRESHOLD="${CLAUDE_COMPACT_THRESHOLD:-100000}"

if ! command -v jq >/dev/null 2>&1; then exit 0; fi

INPUT=""
if [ ! -t 0 ]; then INPUT=$(cat); fi
[ -z "$INPUT" ] && exit 0

TRANSCRIPT=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null || true)
[ -z "$TRANSCRIPT" ] && exit 0
[ -f "$TRANSCRIPT" ] || exit 0

# Context size ≈ cache_read_input_tokens + cache_creation_input_tokens + input_tokens.
# Walk transcript from the end; find the newest line that has usage fields.
TOKENS=$(python3 - "$TRANSCRIPT" <<'PY' 2>/dev/null || true
import json, re, sys
path = sys.argv[1]
with open(path) as f:
    lines = f.readlines()
for line in reversed(lines):
    m_r = re.search(r'"cache_read_input_tokens":\s*(\d+)', line)
    m_c = re.search(r'"cache_creation_input_tokens":\s*(\d+)', line)
    m_i = re.search(r'"input_tokens":\s*(\d+)', line)
    if m_r or m_c or m_i:
        total = (int(m_r.group(1)) if m_r else 0) + \
                (int(m_c.group(1)) if m_c else 0) + \
                (int(m_i.group(1)) if m_i else 0)
        print(total)
        break
PY
)

[ -z "$TOKENS" ] && exit 0
[ "$TOKENS" -lt "$THRESHOLD" ] 2>/dev/null && exit 0

printf '📦 Session at %s input tokens (threshold %s). Consider /compact.\n' \
  "$TOKENS" "$THRESHOLD" >&2
exit 0
