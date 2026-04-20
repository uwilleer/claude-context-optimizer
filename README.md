# claude-context-optimizer

Reduce Claude Code's **baseline** token footprint via shell hooks, permissions tweaks, and a context-discipline skill. Includes a standalone transcript analyzer so you can measure your own savings before trusting mine.

**What this is:** simple, transparent, file-level — hooks + settings + guidelines. No MCP server, no vector DB, no runtime compression.

**What this isn't:** a semantic code-retriever. For runtime compression (40–99%) see [lean-ctx](https://github.com/) and [zilliztech/claude-context](https://github.com/zilliztech/claude-context). They reduce **runtime** context; this repo reduces **baseline** and **enforces discipline**. Complementary, not competing.

---

## Is this for you?

**Likely yes** if:
- Your `/context` shows a baseline ≥ 40k tokens.
- You run multi-hour Claude Code sessions that grow past 100k messages.
- You have many CLAUDE.md files, many plugins, or large memory indexes.
- You've caught the model using `grep`/`cat`/`ls` via Bash when Grep/Read/Glob would do.

**Likely no** if:
- Your sessions are short and baseline already < 30k.
- You need semantic/embedding-based code retrieval — use an MCP tool.
- You don't use Claude Code's hook system.

**Don't trust claims — measure.** See _Measure first_ below.

---

## Measure first (no install needed)

`scripts/analyze-transcript.py` is a standalone diagnostic that reads any Claude Code session jsonl and tells you where your tokens go.

```bash
# Clone or download just the script
curl -O https://raw.githubusercontent.com/uwilleer/claude-context-optimizer/main/scripts/analyze-transcript.py
chmod +x analyze-transcript.py

# Analyze your largest recent session
python3 analyze-transcript.py --top 1
```

Output is a markdown report:

- Event-type byte breakdown (assistant / user / attachment / file-history-snapshot).
- Top-10 largest `tool_results` with tool attribution.
- Tool-use distribution.
- Top 25 Bash command prefixes — exposes `grep`/`cat`/`ls` calls that should be redirected to dedicated tools.
- `hook_success` attachment overhead (how much hook-noise you're paying).
- Peak context from `usage` fields.
- Actionable recommendations (e.g. "132 raw Bash grep/cat calls — add to permissions.deny").

No dependencies beyond Python stdlib. Does not require this plugin to be installed.

---

## Install

### Option A: as a Claude Code plugin (recommended)

```bash
/plugin install uwilleer/claude-context-optimizer
```

The plugin auto-wires:

- `hooks/compact-threshold.sh` on the Stop event — nags about `/compact` when input tokens exceed 100k (configurable via `CLAUDE_COMPACT_THRESHOLD`).
- `hooks/simplify-ignore.sh` on Read / Edit / Write / Stop — hides `simplify-ignore-start`/`simplify-ignore-end` blocks from the model.
- `skills/context-discipline` — describes the 80k-token pre-emptive compact rule, loaded into sessions proactively.

### Option B: manual merge

For users who prefer to own their `~/.claude/settings.json`:

```bash
git clone git@github.com:uwilleer/claude-context-optimizer.git
cd claude-context-optimizer

# Copy hooks
mkdir -p ~/.claude/hooks && cp hooks/*.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh

# Review the settings template and merge selectively
diff -u ~/.claude/settings.json global/settings.template.json | less

# Review guidelines and merge
diff -u ~/.claude/CLAUDE.md global/CLAUDE.md | less
```

The template uses `${HOME}` placeholders; your real `~/.claude/settings.json` needs literal paths.

---

## Comparison with alternatives

| Tool | Approach | Scope | Complexity | Unique value |
|---|---|---|---|---|
| **claude-context-optimizer** (this) | Shell hooks + permissions + guidelines | Baseline + discipline | Low — 4 files, readable bash/python | Transparent; includes a diagnostic analyzer |
| [lean-ctx](https://github.com/) | MCP server + token-dense-dialect compression | Runtime context | High — MCP setup | Up to 99% compression on tool outputs |
| [zilliztech/claude-context](https://github.com/zilliztech/claude-context) | MCP server + vector DB | Semantic code retrieval | High — vector DB ops | Embedding-based relevant-file lookup |
| context-mode | MCP server | Runtime tool output trimming | Medium | Focused on tool-output bloat |

None of these replace each other. This repo pairs naturally with an MCP compression tool if you want both baseline savings and runtime compression.

---

## What's in the hooks

### `compact-threshold.sh`

Stop-hook. Parses the transcript, sums `cache_read_input_tokens + cache_creation_input_tokens + input_tokens` from the newest `usage` block, and emits a stderr reminder when the total exceeds the threshold.

- Default threshold: **100,000** input tokens.
- Override: `CLAUDE_COMPACT_THRESHOLD=80000`.
- Zero cost when below threshold (silent `exit 0`).

### `simplify-ignore.sh`

PreToolUse(Read) / PostToolUse(Edit|Write) / Stop-hook. Protects code blocks from `/code-simplify` and similar refactor passes by hiding them from the model's view of the file and restoring them afterwards.

```js
/* simplify-ignore-start: perf-critical */
result[0] = buf[0] ^ key[0];
result[1] = buf[1] ^ key[1];
/* simplify-ignore-end */
```

The model sees only `/* BLOCK_<hash>: perf-critical */` when reading. Edits to surrounding code are preserved; the protected block round-trips intact. See [hooks/SIMPLIFY-IGNORE.md](hooks/SIMPLIFY-IGNORE.md) for details.

---

## Limits & caveats

- **Effect is workflow-dependent.** The author's baseline dropped 32% (54.4k → 37.2k). Yours will differ. Run the analyzer first.
- **Hook schema may shift.** Claude Code updates can change hook input/output formats. Pin your plugin version in production sessions; watch CHANGELOG.
- **Permissions denials are visible to you.** The first time the model hits a `deny` rule, you get a permission prompt. Approve once, done.
- **`simplify-ignore.sh` writes backups to `.claude/.simplify-ignore-cache/`.** Make sure this path is in your `.gitignore`.
- **Not a replacement for discipline.** Hooks nag; you decide. If you habitually dump 50k-line logs into tool_results, no config will save you.

---

## Requirements

- `bash 3.2+`, `jq`, `python3` (for analyzer and `compact-threshold.sh`).
- `shasum` or `sha1sum` (for `simplify-ignore.sh`).
- Claude Code with plugin support (tested April 2026).

## License

MIT — see [LICENSE](LICENSE).

## Credits

- Global guidelines sections 1–4 adapted from [Karpathy-inspired skills](https://github.com/forrestchang/andrej-karpathy-skills).
- Sections 5–7 from [Anthropic prompt-engineering docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices).
- Section 8 (release discipline), hooks, and the analyzer are original work.
