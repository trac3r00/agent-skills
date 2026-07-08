#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "gate-graph" / "scripts" / "gate_graph.py"
FIXTURES = ROOT / "tests" / "fixtures" / "gate_graph"


def run(args: list[str], check: bool = False):
    command = [sys.executable, str(SCRIPT), *args]
    return subprocess.run(
        command,
        check=check,
        capture_output=True,
        text=True,
    )


def test_gate_graph_reports_overlaps_orphans_and_count():
    proc = run([str(FIXTURES), "--json"])
    assert proc.returncode == 1
    data = json.loads(proc.stdout)

    assert data["target_dir"].endswith("tests/fixtures/gate_graph")
    assert data["gate_count"] == 4
    assert "high_overlap_pairs" in data
    over_pairs = {
        tuple(sorted((item["left"], item["right"])))
        for item in data["overlap_pairs"]
        if item["overlap"] > 0
    }
    assert ("overlap_a_gate", "overlap_b_gate") in over_pairs

    assert data["orphan_gates"] == ["orphan_gate"]


def test_gate_graph_threshold_gate_count_fails_when_below_limit_is_broken():
    proc = run([str(FIXTURES), "--max-gates", "1", "--json"])
    data = json.loads(proc.stdout)

    assert proc.returncode == 1
    assert data["gate_count"] == 4
    assert data["gate_count"] > data["max_gates"]
    assert data["violations"]["over_gate_limit"]


def test_gate_graph_threshold_overlap_fails_only_when_above_ratio():
    proc = run([str(FIXTURES), "--max-overlap", "0.0", "--json"])
    assert proc.returncode == 1
    data = json.loads(proc.stdout)
    assert data["overlap_violations"], data


def test_gate_graph_runs_clean_when_threshold_is_high():
    proc = run([str(FIXTURES), "--max-overlap", "0.99", "--json"])
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["violations"]["overlap_threshold"] is False
