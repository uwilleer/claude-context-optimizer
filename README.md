# claude-context-optimizer

Hooks, settings template, and global instructions for reducing Claude Code's token footprint. Extracted from a real-world optimization session that cut baseline context by ~30%.

## What's inside

```
.
├── global/
│   ├── CLAUDE.md               # Global behavioral guidelines (~/.claude/CLAUDE.md)
│   └── settings.template.json  # Starter ~/.claude/settings.json
├── hooks/
│   ├── compact-threshold.sh    # Stop-hook: nag about /compact at N input tokens
│   ├── simplify-ignore.sh      # Hide marked code blocks from the model during edits
│   ├── simplify-ignore-test.sh # Test suite for simplify-ignore
│   └── SIMPLIFY-IGNORE.md      # Docs for simplify-ignore
├── scripts/
│   └── sync-to-repo.sh         # Pull live ~/.claude edits back into your fork
└── README.md
```

## Install

```bash
git clone git@github.com:<you>/claude-context-optimizer.git
cd claude-context-optimizer

# Hooks
mkdir -p ~/.claude/hooks
cp hooks/*.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh

# Settings (merge with your existing ~/.claude/settings.json — do NOT overwrite blindly)
diff -u ~/.claude/settings.json global/settings.template.json | less

# Global instructions (merge into your ~/.claude/CLAUDE.md)
diff -u ~/.claude/CLAUDE.md global/CLAUDE.md | less
```

The template uses `${HOME}` placeholders; your real `~/.claude/settings.json` needs literal paths.

## Hooks

### `compact-threshold.sh`

**Stop-hook.** Reads the transcript's last `usage` block, sums `cache_read_input_tokens + cache_creation_input_tokens + input_tokens`, and prints a reminder when the total exceeds a threshold (default 100000, override via `CLAUDE_COMPACT_THRESHOLD`).

Why: Claude Code's built-in auto-compact kicks in very late. Earlier compact = better quality + lower cost on long sessions.

### `simplify-ignore.sh`

**PreToolUse(Read) / PostToolUse(Edit|Write) / Stop-hook.** Replaces marked blocks with `BLOCK_<hash>` placeholders before the model reads a file, then restores the real code afterwards. Lets you protect performance-critical or intentionally-weird code from `/code-simplify` and similar refactor loops.

Mark with any comment style:

```js
/* simplify-ignore-start: perf-critical */
result[0] = buf[0] ^ key[0];
result[1] = buf[1] ^ key[1];
/* simplify-ignore-end */
```

See [`hooks/SIMPLIFY-IGNORE.md`](hooks/SIMPLIFY-IGNORE.md) for full docs.

## Settings template highlights

- `permissions.deny` for `grep/rg/cat/head/tail/find/ls` — forces the model to use dedicated tools (`Grep`, `Read`, `Glob`) instead of Bash. Shorter, more structured tool results.
- Stop-hook chain wired up for both `simplify-ignore.sh` and `compact-threshold.sh`.
- `defaultMode: "auto"` and `additionalDirectories` set to a typical `~/programming` layout — adjust to your workspace.

## Context Budget guideline

Added to `global/CLAUDE.md`:

> Active context ≈ `cache_read + cache_creation + input_tokens`. When it reaches ~80k, stop and suggest `/compact` before the next non-trivial action.

Paired with `compact-threshold.sh` at 100k, this gives you ~20k of runway between the model's self-nudge and the hook's hard reminder.

## Scripts

`sync-to-repo.sh` pulls your current `~/.claude/CLAUDE.md`, `settings.json`, and statusline back into this repo's `global/` directory with `$HOME`/`$USER` substituted by placeholders. Run it to capture manual changes before committing.

```bash
bash scripts/sync-to-repo.sh --dry-run   # preview
bash scripts/sync-to-repo.sh             # apply
```

## Requirements

- `jq`, `python3`, `bash 3.2+`
- `shasum` or `sha1sum` (for `simplify-ignore.sh`)

## License

MIT — see [LICENSE](LICENSE).

## Credits

- Global guidelines sections 1–4 adapted from [Karpathy-inspired skills](https://github.com/forrestchang/andrej-karpathy-skills).
- Sections 5–7 from [Anthropic prompt-engineering docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices).
- Section 8 (release discipline) and hooks are original work.
