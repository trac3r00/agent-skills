#!/usr/bin/env python3
"""appshot: take a screenshot of any macOS app window, the full screen, or a region.

Zero dependencies — uses the native `screencapture` command. Capture a
specific app's window (browser, Notes, Hermes desktop, any running app), the
whole screen, or an interactive region. Use for visual QA evidence, app-state
documentation, or "show me what X looks like right now".

Usage:
    appshot.py --screen --out shot.png        # full screen
    appshot.py --app "Google Chrome" --out chrome.png
    appshot.py --app Notes --out notes.png
    appshot.py --region --out region.png      # interactive selection
    appshot.py --list [--json]                # windows available to capture
    appshot.py --screen --out -               # to stdout (base64)

Exit codes: 0 captured, 1 app/window not found, 2 usage error or non-macOS.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path

CAPTURE = "/usr/sbin/screencapture"


def list_windows() -> list[dict]:
    script = (
        'tell application "System Events"\n'
        '  set winList to {}\n'
        '  repeat with p in (every process whose visible is true)\n'
        '    set appName to name of p\n'
        '    try\n'
        '      set winCount to count of windows of p\n'
        '      if winCount > 0 then\n'
        '        set end of winList to (appName & " :: " & winCount & " window(s)")\n'
        '      end if\n'
        '    end try\n'
        '  end repeat\n'
        '  set AppleScript\'s text item delimiters to "\n"\n'
        '  return winList as string\n'
        'end tell'
    )
    p = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if p.returncode != 0:
        return []
    windows = []
    for line in p.stdout.strip().splitlines():
        if " :: " in line:
            app, _, info = line.partition(" :: ")
            windows.append({"app": app.strip(), "info": info.strip()})
    return windows


def capture_app(app_name: str, out: str) -> tuple[bool, str]:
    activate = subprocess.run(
        ["osascript", "-e", f'tell application "{app_name}" to activate'],
        capture_output=True, text=True)
    if activate.returncode != 0:
        return False, f"app not found: {app_name}"
    import time
    time.sleep(0.5)
    cmd = [CAPTURE, "-l"]
    wid = subprocess.run(
        ["osascript", "-e",
         f'tell application "System Events" to tell process "{app_name}"\n'
         '  set frontWin to value of attribute "AXWindowNumber" of window 1\n'
         "  return frontWin\n"
         "end tell"],
        capture_output=True, text=True)
    if wid.returncode != 0 or not wid.stdout.strip().isdigit():
        cmd = [CAPTURE, "-w"]
    else:
        cmd.append(wid.stdout.strip())
    cmd.append(out)
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        return False, p.stderr.strip() or "capture failed"
    return True, out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--screen", action="store_true")
    ap.add_argument("--app", default="")
    ap.add_argument("--region", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not Path(CAPTURE).exists():
        print("error: screencapture not found — macOS required", file=sys.stderr)
        return 2

    if args.list:
        windows = list_windows()
        if args.json:
            print(json.dumps({"windows": windows}, indent=2))
        else:
            for w in windows:
                print(f"{w['app']:<30} {w['info']}")
            print(f"\n{len(windows)} app(s) with capturable windows")
        return 0 if windows else 1

    if not args.out:
        ap.error("--out FILE required for captures")

    if args.screen:
        cmd = [CAPTURE, "-x", args.out]
    elif args.region:
        cmd = [CAPTURE, "-i", args.out]
    elif args.app:
        ok, msg = capture_app(args.app, args.out)
        if not ok:
            print(f"error: {msg}", file=sys.stderr)
            return 1
        cmd = None
    else:
        ap.error("pass --screen, --app NAME, --region, or --list")

    if cmd:
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            print(f"capture failed: {p.stderr.strip()}", file=sys.stderr)
            return 1

    out_path = Path(args.out)
    if args.out == "-":
        print(base64.b64encode(out_path.read_bytes()).decode() if out_path.exists()
              else "", end="")
    elif out_path.exists():
        size = out_path.stat().st_size
        if args.json:
            print(json.dumps({"captured": str(out_path), "bytes": size}))
        else:
            print(f"captured: {args.out} ({size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
