#!/usr/bin/env python3
"""
analyze-transcript.py — Diagnostic for Claude Code session transcripts.

Reads one or more *.jsonl transcript files from ~/.claude/projects/<slug>/,
then prints a Markdown report showing where a session's tokens go: biggest
tool_results, tool-use distribution, Bash command patterns, hook_success
overhead, and the peak context size derived from usage fields.

Usage:
  python3 analyze-transcript.py <path-to-session.jsonl>
  python3 analyze-transcript.py --top 5            # auto-find 5 largest sessions
  python3 analyze-transcript.py --project <slug>   # largest session in project

No dependencies beyond the stdlib. Standalone — does not require the
claude-context-optimizer plugin to be installed.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# ---------- discovery ----------

def projects_root() -> Path:
    return Path.home() / ".claude" / "projects"


def find_largest(top_n: int, project_filter: str | None) -> list[Path]:
    root = projects_root()
    if not root.exists():
        sys.exit(f"no transcripts dir: {root}")
    candidates = []
    for f in root.rglob("*.jsonl"):
        if project_filter and project_filter not in f.parent.name:
            continue
        try:
            candidates.append((f.stat().st_size, f))
        except OSError:
            continue
    candidates.sort(reverse=True)
    return [f for _, f in candidates[:top_n]]


# ---------- analysis ----------

def analyze(path: Path) -> dict:
    type_count = Counter()
    type_bytes = Counter()
    tool_use_count = Counter()
    tool_use_bytes = Counter()
    bash_prefix = Counter()
    hook_success_bytes = 0
    hook_success_count = 0
    tool_results = []  # (size, tool_name_guess, preview)
    max_ctx = {"total": 0, "cache_read": 0, "cache_creation": 0, "input": 0}
    total_lines = 0
    total_bytes = 0

    # map tool_use_id → tool_name so we can attribute tool_results later
    id_to_tool = {}

    with open(path, encoding="utf-8", errors="replace") as fp:
        for line in fp:
            total_lines += 1
            total_bytes += len(line)
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = obj.get("type", "unknown")
            type_count[t] += 1
            type_bytes[t] += len(line)

            if t == "attachment":
                if obj.get("attachment", {}).get("type") == "hook_success":
                    hook_success_bytes += len(line)
                    hook_success_count += 1

            elif t == "assistant":
                msg = obj.get("message", {}) or {}
                usage = msg.get("usage") or {}
                # usage fields: input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens
                cr = usage.get("cache_read_input_tokens") or 0
                cc = usage.get("cache_creation_input_tokens") or 0
                it = usage.get("input_tokens") or 0
                total_ctx = cr + cc + it
                if total_ctx > max_ctx["total"]:
                    max_ctx = {"total": total_ctx, "cache_read": cr, "cache_creation": cc, "input": it}

                for c in msg.get("content", []) or []:
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        name = c.get("name", "?")
                        tool_use_count[name] += 1
                        tool_use_bytes[name] += len(json.dumps(c))
                        tid = c.get("id")
                        if tid:
                            id_to_tool[tid] = name
                        if name == "Bash":
                            cmd = (c.get("input", {}) or {}).get("command", "")
                            bash_prefix[_bash_key(cmd)] += 1

            elif t == "user":
                msg = obj.get("message", {}) or {}
                content = msg.get("content")
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "tool_result":
                            size = len(json.dumps(c))
                            tid = c.get("tool_use_id")
                            tool_name = id_to_tool.get(tid, "?")
                            preview = _preview(c)
                            tool_results.append((size, tool_name, preview))

    tool_results.sort(reverse=True)

    return {
        "path": path,
        "total_lines": total_lines,
        "total_bytes": total_bytes,
        "type_count": type_count,
        "type_bytes": type_bytes,
        "tool_use_count": tool_use_count,
        "tool_use_bytes": tool_use_bytes,
        "bash_prefix": bash_prefix,
        "hook_success_bytes": hook_success_bytes,
        "hook_success_count": hook_success_count,
        "tool_results_top": tool_results[:10],
        "max_ctx": max_ctx,
    }


def _bash_key(cmd: str) -> str:
    parts = cmd.strip().split()
    if not parts:
        return "(empty)"
    head = parts[0]
    if head in ("git", "docker", "kubectl", "make") and len(parts) > 1:
        return f"{head} {parts[1]}"
    return head


def _preview(result_block: dict) -> str:
    content = result_block.get("content")
    if isinstance(content, str):
        return content[:120]
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                return str(item.get("text", ""))[:120]
    return str(content)[:120] if content else ""


# ---------- rendering ----------

def render(stats: dict) -> str:
    out = []
    path = stats["path"]
    total_kb = stats["total_bytes"] / 1024
    out.append(f"# Transcript analysis: `{path.name}`")
    out.append("")
    out.append(f"- Project dir: `{path.parent.name}`")
    out.append(f"- Size: **{total_kb:,.0f} KB** across {stats['total_lines']:,} lines")
    mc = stats["max_ctx"]
    if mc["total"]:
        out.append(
            f"- Peak context: **{mc['total']:,} input tokens** "
            f"(cache_read={mc['cache_read']:,}, cache_creation={mc['cache_creation']:,}, input={mc['input']:,})"
        )
    out.append(f"- `hook_success` attachments: **{stats['hook_success_count']:,}** events, "
               f"**{stats['hook_success_bytes']/1024:,.1f} KB**")
    out.append("")

    # Event type breakdown
    out.append("## Event types (by bytes)")
    out.append("")
    out.append("| type | count | MB |")
    out.append("|---|---|---|")
    for t, b in sorted(stats["type_bytes"].items(), key=lambda x: -x[1]):
        mb = b / 1024 / 1024
        out.append(f"| {t} | {stats['type_count'][t]:,} | {mb:.2f} |")
    out.append("")

    # Tool use distribution
    if stats["tool_use_count"]:
        out.append("## Assistant tool_use (by call count)")
        out.append("")
        out.append("| tool | calls | tool_use KB |")
        out.append("|---|---|---|")
        for name, n in stats["tool_use_count"].most_common(15):
            kb = stats["tool_use_bytes"][name] / 1024
            out.append(f"| {name} | {n:,} | {kb:.1f} |")
        out.append("")

    # Bash patterns
    if stats["bash_prefix"]:
        out.append("## Top 25 Bash command prefixes")
        out.append("")
        out.append("| count | prefix |")
        out.append("|---|---|")
        for k, n in stats["bash_prefix"].most_common(25):
            out.append(f"| {n:,} | `{k}` |")
        out.append("")

    # Top tool_result offenders
    if stats["tool_results_top"]:
        out.append("## Top 10 largest tool_results")
        out.append("")
        out.append("| size (KB) | tool | preview |")
        out.append("|---|---|---|")
        for size, tool, preview in stats["tool_results_top"]:
            short = preview.replace("|", "\\|").replace("\n", " ")[:80]
            out.append(f"| {size/1024:.1f} | `{tool}` | {short} |")
        out.append("")

    # Recommendations
    out.append("## Recommendations")
    out.append("")
    recs = _recommendations(stats)
    if not recs:
        out.append("_Nothing actionable detected — session already lean._")
    else:
        for r in recs:
            out.append(f"- {r}")
    out.append("")
    return "\n".join(out)


def _recommendations(stats: dict) -> list[str]:
    recs = []
    bp = stats["bash_prefix"]
    # raw-bash tools that should be dedicated
    bash_redirect = {"grep", "rg", "cat", "ls", "find", "head", "tail"}
    redirect_total = sum(bp.get(k, 0) for k in bash_redirect)
    if redirect_total >= 20:
        tops = ", ".join(f"`{k}`×{bp[k]}" for k in bash_redirect if bp.get(k, 0))
        recs.append(
            f"**{redirect_total} raw Bash calls** to {tops} — add to `permissions.deny` "
            f"and let the model switch to Grep/Read/Glob. Est. save 1–2 KB per avoided call."
        )
    # hook noise
    if stats["hook_success_count"] > 200:
        avg = stats["hook_success_bytes"] / stats["hook_success_count"]
        recs.append(
            f"**{stats['hook_success_count']:,} hook_success attachments** "
            f"(~{avg:.0f} B each, total {stats['hook_success_bytes']/1024:.0f} KB). "
            "Audit each hook: does it really need to run on every tool call?"
        )
    # peak context near limit
    if stats["max_ctx"]["total"] > 150_000:
        recs.append(
            f"**Peak context {stats['max_ctx']['total']:,} tokens** — you're past the "
            "comfortable compact window. Next time, run `/compact` around 80–100k."
        )
    # plan-mode re-approvals (ExitPlanMode tool)
    if stats["tool_use_count"].get("ExitPlanMode", 0) >= 5:
        n = stats["tool_use_count"]["ExitPlanMode"]
        recs.append(
            f"**{n} ExitPlanMode calls** — each re-reads the full plan file in its "
            "tool_result. Consider keeping plans shorter or using plan mode less often."
        )
    # ssh/curl without limits (heuristic: many ssh calls suggests logs)
    ssh_count = bp.get("ssh", 0)
    if ssh_count > 50:
        recs.append(
            f"**{ssh_count} `ssh` calls** — if any tail logs, always add `| tail -N` or "
            "remote-side `--tail` flag. One un-limited log dump can be 5–10 KB."
        )
    return recs


# ---------- main ----------

def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze a Claude Code transcript.")
    ap.add_argument("path", nargs="?", help="Path to a *.jsonl transcript.")
    ap.add_argument("--top", type=int, default=0,
                    help="Auto-find the N largest transcripts in ~/.claude/projects.")
    ap.add_argument("--project", type=str,
                    help="Restrict --top search to project dirs containing this substring.")
    args = ap.parse_args()

    paths: list[Path]
    if args.path:
        p = Path(args.path).expanduser()
        if not p.is_file():
            sys.exit(f"not a file: {p}")
        paths = [p]
    elif args.top:
        paths = find_largest(args.top, args.project)
        if not paths:
            sys.exit("no transcripts found")
    else:
        ap.print_help()
        sys.exit(2)

    for i, p in enumerate(paths):
        if i:
            print("\n---\n")
        print(render(analyze(p)))


if __name__ == "__main__":
    main()
