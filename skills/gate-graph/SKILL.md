---
name: gate-graph
description: Find overlap and dead weight in a Python gate layer by extracting AST fingerprints, generating an overlap matrix, and failing CI when redundant gates or too many gates are detected.
when_to_use: Your agent has dozens of gate/validator/middleware modules and you need a deterministic offline signal for consolidation candidates, duplicated checks, and dead gates before CI token/latency spending grows. NOT a replacement for semantic tests.
version: 1.0.0
license: MIT
metadata:
  agentskills:
    tags: [agent-governance, gate-maintenance, overlap, redundancy, ci, python-ast]
---
