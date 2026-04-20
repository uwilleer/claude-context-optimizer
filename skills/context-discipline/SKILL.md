---
name: context-discipline
description: Watch the active context budget during long Claude Code sessions. Suggest /compact when approaching 80k input tokens (cache_read + cache_creation + input_tokens), before quality degrades and before the 100k Stop-hook reminder fires. Pipe long tool outputs (logs, file dumps) through tail/head or read with limit; prefer Grep/Read/Glob over grep/cat/ls in Bash.
---

# Context Discipline

Applied by the `claude-context-optimizer` plugin to keep sessions lean.

## Core rule

Active context ≈ `cache_read_input_tokens + cache_creation_input_tokens + input_tokens` from the last assistant `usage` block. When this sum approaches **80k**, stop and suggest `/compact` before the next non-trivial action. Do not silently continue heavy work past that threshold — summarize what's relevant, then compact.

The `compact-threshold.sh` Stop-hook nags at 100k by default (configurable via `CLAUDE_COMPACT_THRESHOLD`). Beat it to the punch: if you can compact at 80k mid-turn, the next 100k of runway is fresh.

## Main drivers of context bloat (in order of impact)

1. **Long tool outputs.** `docker logs`, `pytest -v`, `journalctl`, `git log` without `tail`/`head` can dump 10–50k tokens in one result. Always pipe: `| tail -100`, `--tail=200`, `pytest -x --tb=short`.
2. **Large file Reads.** `Read` without `limit` on a 2000-line file = ~20–30k tokens. Either `Grep` first to find the relevant section, then `Read` with `limit`/`offset`, or accept the cost consciously.
3. **CLAUDE.md growth.** Every CLAUDE.md in the project tree loads into baseline. Keep them ≤ 2k tokens each. Move how-to examples into `docs/`.
4. **Bash substitutes for dedicated tools.** `grep`/`cat`/`ls`/`find`/`head`/`tail` via Bash → output is dumped raw into tool_result. `Grep`/`Read`/`Glob` return structured, bounded output. The plugin's `settings.template.json` denies the raw-Bash variants.

## Session workflow

- **Start of session**: glance at `/context` if available. If baseline > 40k, the session will bleed. Consider closing unused plugins / trimming CLAUDE.md.
- **Mid-session**: every ~10 non-trivial turns, do a mental budget check. "Did I just dump a 30k log? Did I Read a whole file I didn't need?" If yes — `/compact` is cheap insurance.
- **When the Stop-hook reminder fires at 100k**: you're already late. Compact now, don't start a new subtask first.

## What this skill does NOT replace

- Runtime context compression (see MCP-based alternatives like `lean-ctx`, `zilliztech/claude-context`).
- Semantic code retrieval (same).

This skill + the plugin's hooks operate on **discipline and baseline**, not on runtime compression.
