"""Unit tests for scripts/analyze-transcript.py.

Loads the script as a module via importlib because its filename contains a
hyphen (not a legal Python identifier for a regular `import` statement).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "analyze-transcript.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("analyze_transcript", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["analyze_transcript"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


at = _load_module()


# ---------- _bash_key ----------

@pytest.mark.parametrize(
    ("cmd", "expected"),
    [
        ("grep -r foo .", "grep"),
        ("  rg pattern  ", "rg"),
        ("git status", "git status"),
        ("git commit -m 'x'", "git commit"),
        ("docker compose up", "docker compose"),
        ("kubectl get pods", "kubectl get"),
        ("make test", "make test"),
        ("", "(empty)"),
        ("   ", "(empty)"),
        ("cat foo.py", "cat"),
    ],
)
def test_bash_key(cmd: str, expected: str) -> None:
    assert at._bash_key(cmd) == expected


# ---------- _preview ----------

def test_preview_string_truncates_at_120() -> None:
    text = "x" * 500
    assert at._preview({"content": text}) == "x" * 120


def test_preview_list_with_text_block() -> None:
    block = {"content": [{"type": "text", "text": "hello world"}]}
    assert at._preview(block) == "hello world"


def test_preview_list_without_text_block() -> None:
    block = {"content": [{"type": "image", "source": {"data": "..."}}]}
    # falls through to str() of the list, truncated
    out = at._preview(block)
    assert isinstance(out, str)


def test_preview_empty() -> None:
    assert at._preview({}) == ""
    assert at._preview({"content": None}) == ""


# ---------- analyze ----------

def _write_fixture(tmp_path: Path) -> Path:
    lines = [
        {"type": "user", "message": {"content": "go"}},
        {
            "type": "assistant",
            "message": {
                "usage": {
                    "input_tokens": 500,
                    "cache_read_input_tokens": 40_000,
                    "cache_creation_input_tokens": 2_000,
                },
                "content": [
                    {"type": "tool_use", "id": "tu1", "name": "Bash", "input": {"command": "grep foo src"}},
                    {"type": "tool_use", "id": "tu2", "name": "Read", "input": {"file_path": "a.py"}},
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "tu1", "content": "found\n" * 50},
                ]
            },
        },
        {"type": "attachment", "attachment": {"type": "hook_success"}},
        {
            "type": "assistant",
            "message": {
                "usage": {
                    "input_tokens": 700,
                    "cache_read_input_tokens": 90_000,
                    "cache_creation_input_tokens": 100,
                },
                "content": [],
            },
        },
    ]
    p = tmp_path / "session.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    return p


def test_analyze_counts_types_and_tracks_peak(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path)
    stats = at.analyze(path)

    assert stats["total_lines"] == 5
    assert stats["type_count"]["assistant"] == 2
    assert stats["type_count"]["user"] == 2
    assert stats["type_count"]["attachment"] == 1

    # Peak is the second assistant message (90_000 + 100 + 700 = 90_800)
    assert stats["max_ctx"]["total"] == 90_800
    assert stats["max_ctx"]["cache_read"] == 90_000

    # tool_use aggregation
    assert stats["tool_use_count"]["Bash"] == 1
    assert stats["tool_use_count"]["Read"] == 1
    assert stats["bash_prefix"]["grep"] == 1

    # tool_result attributed back to Bash via id_to_tool
    assert stats["tool_results_top"]
    top_size, top_tool, _preview = stats["tool_results_top"][0]
    assert top_tool == "Bash"
    assert top_size > 0

    # hook_success tallied
    assert stats["hook_success_count"] == 1


def test_analyze_handles_malformed_lines(tmp_path: Path) -> None:
    p = tmp_path / "broken.jsonl"
    p.write_text('{"type":"user","message":{"content":"ok"}}\nnot-json\n{"type":"unknown"}\n')
    stats = at.analyze(p)
    assert stats["total_lines"] == 3
    # Malformed line counted in total_lines but skipped by JSON parser
    assert stats["type_count"]["user"] == 1
    assert stats["type_count"]["unknown"] == 1


# ---------- _recommendations ----------

def test_recommendations_flags_bash_redirect() -> None:
    from collections import Counter

    stats = {
        "bash_prefix": Counter({"grep": 40, "cat": 5}),
        "hook_success_count": 0,
        "hook_success_bytes": 0,
        "max_ctx": {"total": 10_000},
        "tool_use_count": Counter(),
    }
    recs = at._recommendations(stats)
    joined = "\n".join(recs)
    assert "raw Bash" in joined
    assert "grep" in joined


def test_recommendations_flags_peak_context() -> None:
    from collections import Counter

    stats = {
        "bash_prefix": Counter(),
        "hook_success_count": 0,
        "hook_success_bytes": 0,
        "max_ctx": {"total": 200_000},
        "tool_use_count": Counter(),
    }
    recs = at._recommendations(stats)
    joined = "\n".join(recs)
    assert "Peak context" in joined


def test_recommendations_silent_on_clean_session() -> None:
    from collections import Counter

    stats = {
        "bash_prefix": Counter({"git status": 3}),
        "hook_success_count": 10,
        "hook_success_bytes": 2_000,
        "max_ctx": {"total": 50_000},
        "tool_use_count": Counter(),
    }
    assert at._recommendations(stats) == []
