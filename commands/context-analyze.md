---
description: Analyze the current session transcript (or top-N largest sessions) and print a markdown token-usage report.
---

Run the transcript analyzer shipped with `claude-context-optimizer` to see where the session's tokens are going: largest `tool_results`, tool-use distribution, Bash prefix histogram, `hook_success` overhead, and peak context size.

## Usage

- With no argument → analyze the 3 largest transcripts in `~/.claude/projects/`.
- With a path → analyze that specific `.jsonl` transcript.
- With `--project <substring>` → analyze the largest session whose project dir contains the substring.

## Execution

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/analyze-transcript.py" --top 3
```

If the user supplied a specific path in the prompt, pass it through instead:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/analyze-transcript.py" <path>
```

Return the stdout verbatim. Do not re-summarise it — the markdown report is already structured for the user to read.
