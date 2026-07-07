#!/usr/bin/env python3
"""Self-tests for both skills. Pure stdlib + pytest — no network, no secrets."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CB = ROOT / "skills" / "context-budget" / "scripts" / "context_budget.py"
CA = ROOT / "skills" / "claim-audit" / "scripts" / "claim_audit.py"


def run(script, *args, stdin=None):
    p = subprocess.run(
        [sys.executable, str(script), *args],
        input=stdin, capture_output=True, text=True,
    )
    return p.returncode, p.stdout, p.stderr


# ── context-budget ────────────────────────────────────────────────────────
def test_context_budget_counts_and_ranks(tmp_path):
    big = tmp_path / "big.md"
    small = tmp_path / "small.md"
    big.write_text("word " * 2000)
    small.write_text("word " * 10)
    rc, out, _ = run(CB, str(tmp_path), "--json")
    assert rc == 0
    import json
    data = json.loads(out)
    assert data["file_count"] == 2
    # heaviest file ranked first
    assert data["entries"][0]["path"].endswith("big.md")
    assert data["total_tokens"] > 0


def test_context_budget_exit_over_budget(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("word " * 5000)
    rc_over, _, _ = run(CB, str(tmp_path), "--budget", "10")
    rc_ok, _, _ = run(CB, str(tmp_path), "--budget", "10000000")
    assert rc_over == 1
    assert rc_ok == 0


def test_context_budget_missing_path_is_soft():
    rc, _, err = run(CB, "/nonexistent/path/xyz")
    # no files found → prints notice, still exits 0 (nothing over budget)
    assert rc == 0


# ── claim-audit ───────────────────────────────────────────────────────────
def test_claim_audit_flags_bare_facts():
    rc, out, _ = run(CA, "-", stdin="The capital of Australia is Sydney. It was founded in 1788.")
    assert rc == 0
    assert "bare" in out
    assert "Sydney" in out


def test_claim_audit_grounded_and_hedged_not_bare():
    text = "According to the census [1], it had 5 million residents. I think it is probably large."
    rc, out, _ = run(CA, "-", "--json", stdin=text)
    import json
    data = json.loads(out)
    kinds = [c["kind"] for c in data["claims"]]
    assert "grounded" in kinds
    assert "hedged" in kinds
    assert "bare" not in kinds


def test_claim_audit_fail_over_gate():
    high = "Python was released in 1991. The GIL was removed in 2020. It has 5 keywords."
    low = "This is likely fine. See https://example.com for details."
    rc_high, _, _ = run(CA, "-", "--fail-over", "0.4", stdin=high)
    rc_low, _, _ = run(CA, "-", "--fail-over", "0.4", stdin=low)
    assert rc_high == 1
    assert rc_low == 0
