# Global Instructions

Behavioral guidelines to reduce common LLM coding mistakes and keep responses efficient. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 0. Context Budget

Active context ≈ `cache_read + cache_creation + input_tokens`. When it reaches ~80k, stop and suggest `/compact` before the next non-trivial action. Do not silently continue heavy work past that threshold — summarize, then compact. The Stop hook nags at 100k; beat it to the punch. Long tool outputs (logs, file dumps) are the main drivers — always pipe to `tail`/`head` or read with `limit`.

---

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

## 5. Response Style

- **Be direct**: lead with the answer, not the reasoning.
- **Be concise**: one sentence when possible, never three when one suffices.
- **Skip preamble**: no "Let me…", "I'll…", or similar filler.
- **Omit pleasantries**: no "Sure thing", "Great question", etc.
- **No hedging**: avoid "probably", "might", "could" unless uncertainty is real and load-bearing.
- **Declarative sentences**: short, abbreviate when unambiguous ("repo" not "repository").

## 6. Tooling Defaults

- **Use `tree` before coding** — run `tree -L N -I node_modules --gitignore` to see structure before modifying code.
- **Batch related edits** to minimize tool calls.
- **No explanatory comments** unless the WHY is non-obvious.
- **Parallel tool calls** when independent — single message, multiple calls.
- **Prefer dedicated tools** (Read, Edit, Glob, Grep) over Bash.

## 7. Release Discipline

**One command to ship. Preflight hard. Assert after scripted edits.**

- **Single source of truth for version.** One canonical file (`Cargo.toml` / `pyproject.toml` / `package.json` / `manifest.json` / equivalent). Duplicates — sync via script or delete.
- **Public version ≠ internal schema.** Storage/DB migrations are invisible to users. Never bump public major because of an internal migration.
- **Release = one command.** `make release-patch|minor|major` or equivalent. Zero manual steps before deciding "what to ship".
- **Preflight gates.** On the release branch? Working tree clean? `git fetch` + `pull --ff-only`? Fail early, fail loud — never release from a dirty or stale state.
- **Assert after scripted edits.** `sed`/`awk`/JSON mutations are not trustworthy — always assert after (`grep -q` or equivalent). If the assertion fails, stop BEFORE commit/tag/push.
- **Git tags are immutable; branch pushes are `--ff-only`.** Public version matches the tag, monotonic, strict format. Never move or force-push a tag.
- **Expose build provenance at runtime.** Inject SHA + version via build-time define so support/debug surfaces can show `v1.2.3 · sha · schema`.
- **Every release has a note.** Even one line. Tag message, CHANGELOG, or release body — pick one and always fill it.
- **Rollback is part of release.** Know the revert command before you tag.

---

## In Practice

- ✅ "Fixed the typo in line 42."
- ❌ "I've identified and fixed a typo in the codebase on line 42 where…"
- ✅ "3 files changed: src/api.ts, src/types.ts, tests/api.test.ts"
- ❌ "Let me read those files and make the necessary updates…"

---

Credits: [Karpathy-inspired guidelines](https://github.com/forrestchang/andrej-karpathy-skills) (sections 1–4) + [Anthropic prompt engineering best practices](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices) (sections 5–7) + synthesis from release workflow (section 8).
