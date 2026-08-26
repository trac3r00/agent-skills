#!/usr/bin/env python3
"""ext-scaffold: generate a working Manifest V3 browser extension skeleton.

Writes a complete, loadable MV3 extension: manifest.json, background service
worker, content script, and popup — valid on first load in Chrome/Edge/
Firefox, no npm, no bundler. Refuses to overwrite an existing directory.

Usage:
    ext_scaffold.py my-extension [--dir PATH] [--json]
    ext_scaffold.py my-extension --permissions storage,tabs

Exit codes: 0 created, 2 exists/invalid name.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MANIFEST = {
    "manifest_version": 3,
    "name": None,
    "version": "0.1.0",
    "description": "Browser extension scaffolded by ext-scaffold.",
    "background": {"service_worker": "background.js"},
    "content_scripts": [{
        "matches": ["<all_urls>"],
        "js": ["content.js"],
        "run_at": "document_idle",
    }],
    "action": {"default_popup": "popup.html", "default_title": None},
    "permissions": ["storage"],
}

BACKGROUND = """\
chrome.runtime.onInstalled.addListener(({ reason }) => {
  if (reason === "install") {
    console.log("[ext] installed");
  }
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "ping") {
    sendResponse({ ok: true, ts: Date.now() });
  }
  return true;
});
"""

CONTENT = """\
(() => {
  const seen = new WeakSet();
  const mark = (el) => {
    if (!seen.has(el)) seen.add(el);
  };
  document.querySelectorAll("*").forEach(mark);
  chrome.runtime.sendMessage({ type: "ping" }, (res) => {
    if (res?.ok) console.log("[ext] content script active");
  });
})();
"""

POPUP = """\
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font: 14px/1.4 system-ui, sans-serif; min-width: 240px; margin: 12px; }
    button { padding: 6px 12px; cursor: pointer; }
    #out { margin-top: 8px; white-space: pre-wrap; font-family: monospace; }
  </style>
</head>
<body>
  <strong>EXT_NAME</strong>
  <button id="go">Run</button>
  <div id="out"></div>
  <script src="popup.js"></script>
</body>
</html>
"""

POPUP_JS = """\
document.getElementById("go").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  document.getElementById("out").textContent = tab
    ? `Active tab: ${tab.title}\\n${tab.url}`
    : "no active tab";
});
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("name")
    ap.add_argument("--dir", default=".")
    ap.add_argument("--permissions", default="storage",
                    help="comma-separated MV3 permissions")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,60}", args.name):
        print("name must be kebab-case (a-z0-9-, 2-61 chars)", file=sys.stderr)
        return 2
    out = Path(args.dir) / args.name
    if out.exists():
        print(f"exists: {out}", file=sys.stderr)
        return 2

    manifest = dict(MANIFEST)
    manifest["name"] = args.name
    manifest["action"] = {"default_popup": "popup.html", "default_title": args.name}
    manifest["permissions"] = sorted({p.strip() for p in args.permissions.split(",") if p.strip()})

    out.mkdir(parents=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "background.js").write_text(BACKGROUND)
    (out / "content.js").write_text(CONTENT)
    (out / "popup.html").write_text(POPUP.replace("EXT_NAME", args.name))
    (out / "popup.js").write_text(POPUP_JS)

    files = sorted(f.name for f in out.iterdir())
    if args.json:
        print(json.dumps({"created": str(out), "files": files,
                          "manifest": manifest}, indent=2))
    else:
        print(f"created {out}: {', '.join(files)}")
        print(f"load it: chrome://extensions -> Developer mode -> Load unpacked -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
