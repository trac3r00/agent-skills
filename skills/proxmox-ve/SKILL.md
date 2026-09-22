---
name: proxmox-ve
description: Safely operate Proxmox VE through its MCP server: discover APIs, inspect clusters, and perform deliberate administration.
when_to_use: Use for Proxmox VE nodes, VMs, containers, storage, networking, backups, cluster administration, or API discovery. Start with read-only calls and inspect endpoint metadata before unfamiliar operations.
version: 1.0.0
license: MIT
metadata:
  agentskills:
    tags: [proxmox, virtualization, mcp, infrastructure, api, security]
---

# Proxmox VE MCP

This skill carries the audited [Proxmox MCP source](mcp) as a Git submodule at
`mcp/`. Initialize it after cloning this repository:

```sh
git submodule update --init --recursive skills/proxmox-ve/mcp
cd skills/proxmox-ve/mcp
bun install --frozen-lockfile
bun run build
```

Copy [`mcp.json.example`](mcp.json.example) to your user-scoped skill directory
as `mcp.json`, replacing only the absolute installation paths. Keep
`PROXMOX_URL`, token ID, token secret, and CA file in an ignored, mode-`0600`
environment file; never put them in this skill, MCP configuration, prompts, or
tool arguments.

## Safe workflow

1. Start with `proxmox_get` for `/version`, `/nodes`, or
   `/access/permissions`.
2. For unfamiliar operations, use `proxmox_search_endpoints` and then
   `proxmox_describe_endpoint` before constructing the request.
3. Use `proxmox_request` only with a concrete endpoint path and explicit HTTP
   method. POST, PUT, and DELETE can change the cluster.
4. A returned UPID only confirms submission. Read
   `/nodes/{node}/tasks/{upid}/status` and `/log` before reporting completion.

## File and network boundaries

- Proxmox API tokens enforce authorization; this skill never widens their ACLs.
- Upload and download paths must be under `PROXMOX_FILE_ROOTS`. Do not place
  credentials, private keys, or unrelated user files there.
- Use HTTPS and a trusted CA. Remote cleartext HTTP is rejected unless the MCP
  configuration explicitly opts in.
- API catalog descriptions are advisory. The target PVE server remains
  authoritative for accepted parameters and permissions.

## Verification

Run the MCP project's full suite before publishing a local change:

```sh
cd skills/proxmox-ve/mcp
bun run typecheck
bun test
bun run build
```

Then start a fresh agent session, load this skill explicitly, and make
read-only `/version` and `/nodes` calls before any administration.
