---
name: sys-health
description: One-shot machine health report — disk usage, memory pressure, load average, top CPU processes, and zombie count — from native system interfaces (statvfs, sysctl/vm_stat, ps), no psutil or vendor binaries. Budgets turn it into a gate that alerts when disk or memory pressure crosses a threshold.
when_to_use: "Is this box okay?" before blaming code, pre-flight checks before heavy jobs, cron-based resource monitoring. NOT a metrics daemon or a historical tracker; it's a point-in-time snapshot.
version: 1.0.0
license: MIT
metadata:
  agentskills:
    tags: [sysops, monitoring, disk, memory, processes]
---

# Sys Health

The "is this box okay" check an agent should run before blaming code.

## Commands

```bash
python3 scripts/sys_health.py
python3 scripts/sys_health.py --json --top 10
python3 scripts/sys_health.py --max-disk-pct 90 --max-mem-pct 85   # gate
```

## Reports

| Metric | Source |
|---|---|
| Disk total/used/% | statvfs |
| Memory total/used % | vm_stat (macOS) or /proc/meminfo (Linux) |
| Load 1/5/15m | sysctl vm.loadavg or /proc/loadavg |
| Top N processes by CPU | ps |
| Zombie processes | ps state Z |

Exit 1 when any `--max-*-pct` budget is exceeded or zombies exist.

## Pairs with

`session-finder` (which agents are consuming that CPU),
`net-probe` (the network side of the same triage),
`log-analyzer` (what the box's logs say after you learn it's resource-starved).
