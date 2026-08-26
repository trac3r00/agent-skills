#!/usr/bin/env python3
"""sys-health: one-shot machine health report — disk, memory, load, top processes.

The "is this box okay" check an agent should run before blaming code. Reads
df, sysctl/ps on macOS, /proc on Linux; no psutil, no vendor binaries.
Budgets turn it into a gate: alert (and exit 1) when disk or memory pressure
crosses a threshold.

Usage:
    sys_health.py [--json]
    sys_health.py --max-disk-pct 90 --max-mem-pct 85
    sys_health.py --top 5

Exit codes: 0 healthy, 1 over budget, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def _disk(path: str) -> dict:
    st = __import__("os").statvfs(path)
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    used = total - free
    return {"mount": path, "total_gb": round(total / 1e9, 1),
            "used_gb": round(used / 1e9, 1),
            "used_pct": round(used / total * 100, 1) if total else 0.0}


def _memory() -> dict:
    try:
        p = subprocess.run(["sysctl", "-n", "hw.memsize"],
                           capture_output=True, text=True)
        total = int(p.stdout.strip())
        vm = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
        page = 16384
        free = inactive = 0
        for line in vm.splitlines():
            if "Pages free" in line:
                free = int(line.split(":")[1].strip().rstrip(".")) * page
            elif "Pages inactive" in line:
                inactive = int(line.split(":")[1].strip().rstrip(".")) * page
        avail = free + inactive
        used = total - avail
        return {"total_gb": round(total / 1e9, 1),
                "used_pct": round(used / total * 100, 1)}
    except (OSError, ValueError):
        try:
            info = {}
            for line in open("/proc/meminfo"):
                k, _, v = line.partition(":")
                info[k] = int(v.strip().split()[0]) * 1024
            total = info["MemTotal"]
            avail = info.get("MemAvailable", info.get("MemFree", 0))
            return {"total_gb": round(total / 1e9, 1),
                    "used_pct": round((total - avail) / total * 100, 1)}
        except (OSError, ValueError, KeyError):
            return {"total_gb": 0.0, "used_pct": 0.0}


def _load() -> dict:
    try:
        p = subprocess.run(["sysctl", "-n", "vm.loadavg"],
                           capture_output=True, text=True)
        parts = p.stdout.strip().strip("{}").split()
        return {"1m": float(parts[0]), "5m": float(parts[1]), "15m": float(parts[2])}
    except (OSError, ValueError, IndexError):
        try:
            a, b, c, *_ = open("/proc/loadavg").read().split()
            return {"1m": float(a), "5m": float(b), "15m": float(c)}
        except (OSError, ValueError):
            return {"1m": 0.0, "5m": 0.0, "15m": 0.0}


def _top_processes(n: int) -> list[dict]:
    p = subprocess.run(["ps", "-eo", "pid,pcpu,pmem,comm", "-r"],
                       capture_output=True, text=True)
    out = []
    for line in p.stdout.splitlines()[1 : n + 1]:
        parts = line.split(None, 3)
        if len(parts) == 4:
            out.append({"pid": int(parts[0]), "cpu_pct": float(parts[1]),
                        "mem_pct": float(parts[2]), "command": parts[3][:60]})
    return out


def _zombies() -> int:
    p = subprocess.run(["ps", "-eo", "stat"], capture_output=True, text=True)
    return sum(1 for line in p.stdout.splitlines() if line.strip().startswith("Z"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max-disk-pct", type=float, default=None)
    ap.add_argument("--max-mem-pct", type=float, default=None)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = {
        "disk": _disk("/"),
        "memory": _memory(),
        "load": _load(),
        "top_processes": _top_processes(args.top),
        "zombies": _zombies(),
    }
    alerts = []
    if args.max_disk_pct is not None and report["disk"]["used_pct"] > args.max_disk_pct:
        alerts.append(f"disk {report['disk']['used_pct']}% > {args.max_disk_pct}%")
    if args.max_mem_pct is not None and report["memory"]["used_pct"] > args.max_mem_pct:
        alerts.append(f"memory {report['memory']['used_pct']}% > {args.max_mem_pct}%")
    if report["zombies"]:
        alerts.append(f"{report['zombies']} zombie process(es)")
    report["alerts"] = alerts

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"disk: {report['disk']['used_pct']}% of {report['disk']['total_gb']}GB")
        print(f"memory: {report['memory']['used_pct']}% of {report['memory']['total_gb']}GB")
        print(f"load: {report['load']['1m']} {report['load']['5m']} {report['load']['15m']}")
        for proc in report["top_processes"]:
            print(f"  {proc['pid']:>7} {proc['cpu_pct']:>5.1f}%cpu {proc['command']}")
        for a in alerts:
            print(f"ALERT: {a}")
    return 1 if alerts else 0


if __name__ == "__main__":
    raise SystemExit(main())
