#!/usr/bin/env python3
"""apple-suite: drive macOS Notes, Reminders, and Maps via AppleScript.

Usage:
    apple_suite.py notes list [--limit N] [--json]
    apple_suite.py notes create --title T --body B
    apple_suite.py notes search QUERY [--json]
    apple_suite.py reminders list [--json]
    apple_suite.py reminders add --title T [--due "YYYY-MM-DD HH:MM"]
    apple_suite.py reminders complete --title T
    apple_suite.py maps search QUERY
    apple_suite.py maps directions --from X --to Y
    apple_suite.py maps open ADDRESS

Exit codes: 0 success, 1 app error, 2 usage error or non-macOS.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _osascript(script: str) -> tuple[int, str, str]:
    p = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _notes_list(limit: int) -> dict:
    script = (
        f'tell application "Notes"\n'
        f'  set noteList to {{}}\n'
        f'  repeat with n in notes\n'
        f'    try\n'
        f'      set noteName to name of n\n'
        f'      set end of noteList to noteName\n'
        f'    end try\n'
        f'    if (count of noteList) >= {limit} then exit repeat\n'
        f'  end repeat\n'
        f'  set AppleScript\'s text item delimiters to "\n"\n'
        f'  return noteList as string\n'
        f'end tell'
    )
    rc, out, err = _osascript(script)
    if rc != 0:
        return {"error": err}
    notes = [n.strip() for n in out.split("\n") if n.strip()]
    return {"count": len(notes), "notes": notes}


def _notes_create(title: str, body: str) -> dict:
    escaped_title = title.replace('"', '\\"')
    escaped_body = body.replace('"', '\\"').replace("\n", "<br>")
    script = (
        'tell application "Notes"\n'
        '  set newNote to make new note at folder "Notes"\n'
        f'  set name of newNote to "{escaped_title}"\n'
        f'  set body of newNote to "{escaped_body}"\n'
        '  return "created"\n'
        'end tell'
    )
    rc, out, err = _osascript(script)
    return {"status": "created", "title": title} if rc == 0 else {"error": err}


def _notes_search(query: str) -> dict:
    escaped = query.replace('"', '\\"')
    script = (
        'tell application "Notes"\n'
        '  set matches to {}\n'
        '  repeat with n in notes\n'
        f'    if name of n contains "{escaped}" then\n'
        '      set noteFolder to name of folder of n\n'
        '      set end of matches to (noteFolder & " :: " & name of n)\n'
        '    end if\n'
        '  end repeat\n'
        '  return matches as string\n'
        'end tell'
    )
    rc, out, err = _osascript(script)
    if rc != 0:
        return {"error": err}
    notes = [n.strip() for n in out.split(",") if n.strip()] if out else []
    return {"query": query, "count": len(notes), "notes": notes}


def _reminders_list() -> dict:
    script = (
        'tell application "Reminders"\n'
        '  set remList to {}\n'
        '  repeat with r in reminders\n'
        '    if completed of r is false then\n'
        '      set end of remList to name of r\n'
        '    end if\n'
        '  end repeat\n'
        '  return remList as string\n'
        'end tell'
    )
    rc, out, err = _osascript(script)
    if rc != 0:
        return {"error": err}
    rems = [r.strip() for r in out.split(",") if r.strip()] if out else []
    return {"count": len(rems), "reminders": rems}


def _reminders_add(title: str, due: str = "") -> dict:
    escaped = title.replace('"', '\\"')
    script = 'tell application "Reminders"\n'
    if due:
        script += (
            f'  set newRem to make new reminder with properties {{name:"{escaped}", '
            f'due date:date "{due}"}}\n'
        )
    else:
        script += f'  set newRem to make new reminder with properties {{name:"{escaped}"}}\n'
    script += '  return "added"\nend tell'
    rc, _, err = _osascript(script)
    return {"status": "added", "title": title} if rc == 0 else {"error": err}


def _reminders_complete(title: str) -> dict:
    escaped = title.replace('"', '\\"')
    script = (
        'tell application "Reminders"\n'
        f'  set matchingReminders to (reminders whose name is "{escaped}" and completed is false)\n'
        '  if (count of matchingReminders) > 0 then\n'
        '    set completed of item 1 of matchingReminders to true\n'
        '    return "completed"\n'
        '  else\n'
        '    return "not found"\n'
        '  end if\n'
        'end tell'
    )
    rc, out, err = _osascript(script)
    if rc != 0:
        return {"error": err}
    if out == "completed":
        return {"status": "completed", "title": title}
    return {"error": f"reminder not found: {title}"}


def _mail_unread() -> dict:
    script = (
        'tell application "Mail"\n'
        '  set unreadCount to unread count of inbox\n'
        '  return unreadCount\n'
        'end tell'
    )
    rc, out, err = _osascript(script)
    if rc != 0:
        return {"error": err}
    return {"unread": int(out) if out.isdigit() else out}


def _mail_list(limit: int) -> dict:
    script = (
        'tell application "Mail"\n'
        '  set msgList to {}\n'
        '  set allMsgs to messages of inbox\n'
        '  repeat with m in allMsgs\n'
        '    set end of msgList to (subject of m & " :: " & sender of m & " :: " & (date received of m as string))\n'
        f'    if (count of msgList) >= {limit} then exit repeat\n'
        '  end repeat\n'
        '  set AppleScript\'s text item delimiters to "\n"\n'
        '  return msgList as string\n'
        'end tell'
    )
    rc, out, err = _osascript(script)
    if rc != 0:
        return {"error": err}
    msgs = [m.strip() for m in out.split("\n") if m.strip()] if out else []
    return {"count": len(msgs), "messages": msgs}


def _calendar_list() -> dict:
    script = 'tell application "Calendar" to get name of every calendar'
    rc, out, err = _osascript(script)
    if rc != 0:
        return {"error": err}
    cals = [c.strip() for c in out.split(",") if c.strip()]
    return {"count": len(cals), "calendars": cals}


def _calendar_today() -> dict:
    script = (
        'tell application "Calendar"\n'
        '  set today to current date\n'
        '  set endOfDay to today + (1 * days)\n'
        '  set eventList to {}\n'
        '  repeat with c in calendars\n'
        '    repeat with e in (events of c whose start date >= today and start date < endOfDay)\n'
        '      set end of eventList to (summary of e & " @ " & (start date of e as string))\n'
        '    end repeat\n'
        '  end repeat\n'
        '  set AppleScript\'s text item delimiters to "\n"\n'
        '  return eventList as string\n'
        'end tell'
    )
    rc, out, err = _osascript(script)
    if rc != 0:
        return {"error": err}
    events = [e.strip() for e in out.split("\n") if e.strip()] if out else []
    return {"count": len(events), "events": events}


def _calendar_add(title: str, date_str: str, calendar_name: str = "") -> dict:
    escaped = title.replace('"', '\\"')
    if calendar_name:
        cal_clause = f'calendar "{calendar_name}"'
    else:
        cal_clause = 'calendar 1'
    script = (
        'tell application "Calendar"\n'
        f'  tell {cal_clause}\n'
        f'    make new event with properties {{summary:"{escaped}", start date:date "{date_str}", end date:date "{date_str}" + (1 * hours)}}\n'
        '  end tell\n'
        '  return "added"\n'
        'end tell'
    )
    rc, _, err = _osascript(script)
    return {"status": "added", "title": title} if rc == 0 else {"error": err}


def _terminal_run(command: str) -> dict:
    escaped = command.replace('"', '\\"')
    script = (
        'tell application "Terminal"\n'
        '  activate\n'
        f'  do script "{escaped}"\n'
        '  delay 2\n'
        '  set tabContent to contents of selected tab of front window\n'
        '  return tabContent\n'
        'end tell'
    )
    rc, out, err = _osascript(script)
    if rc != 0:
        return {"error": err}
    lines = out.splitlines()
    output = lines[-1] if lines else ""
    return {"command": command, "output": output, "full": out}


def _shortcuts_list() -> dict:
    script = 'tell application "Shortcuts" to get name of every shortcut'
    rc, out, err = _osascript(script)
    if rc != 0:
        return {"error": err}
    names = [n.strip() for n in out.split(",") if n.strip()]
    return {"count": len(names), "shortcuts": names}


def _shortcuts_run(name: str) -> dict:
    escaped = name.replace('"', '\\"')
    script = f'tell application "Shortcuts" to run shortcut "{escaped}"'
    rc, _, err = _osascript(script)
    return {"status": "ran", "shortcut": name} if rc == 0 else {"error": err}


def _contacts_count() -> dict:
    script = 'tell application "Contacts" to get count of people'
    rc, out, err = _osascript(script)
    if rc != 0:
        return {"error": err}
    return {"count": int(out) if out.isdigit() else out}


def _contacts_search(query: str) -> dict:
    escaped = query.replace('"', '\\"')
    script = (
        'tell application "Contacts"\n'
        f'  set matches to (every person whose name contains "{escaped}")\n'
        '  set names to {}\n'
        '  repeat with p in matches\n'
        '    set end of names to name of p\n'
        '  end repeat\n'
        '  set AppleScript\'s text item delimiters to "\n"\n'
        '  return names as string\n'
        'end tell'
    )
    rc, out, err = _osascript(script)
    if rc != 0:
        return {"error": err}
    names = [n.strip() for n in out.split("\n") if n.strip()] if out else []
    return {"query": query, "count": len(names), "contacts": names}


def _photos_albums() -> dict:
    script = 'tell application "Photos" to get name of every album'
    rc, out, err = _osascript(script)
    if rc != 0:
        return {"error": err}
    albums = [a.strip() for a in out.split(",") if a.strip()]
    return {"count": len(albums), "albums": albums}


def _photos_count() -> dict:
    script = 'tell application "Photos" to get count of media items'
    rc, out, err = _osascript(script)
    if rc != 0:
        return {"error": err}
    return {"count": int(out) if out.isdigit() else out}


def _appstore_search(term: str) -> dict:
    from urllib.parse import quote
    script = f'open location "macappstore://search?term={quote(term)}"'
    rc, _, err = _osascript(script)
    return {"status": "opened", "term": term} if rc == 0 else {"error": err}


def _phone_open(number: str) -> dict:
    from urllib.parse import quote
    script = f'open location "tel:{quote(number)}"'
    rc, _, err = _osascript(script)
    return {"status": "opened", "number": number} if rc == 0 else {"error": err}


NOT_SCRIPTABLE = {
    "voicememo": "VoiceMemos has no public AppleScript dictionary (confirmed: -2741 error on every access pattern). Recordings are stored in ~/Library/Application Support/com.apple.voicememos/ but the format is undocumented and private.",
    "password": "Passwords.app has no AppleScript API. The only interface is the Settings app UI or System Settings > Passwords.",
    "findmy": "Find My has no public AppleScript API. Locations are not scriptable. Use the Find My app or Siri.",
    "activitymonitor": "Activity Monitor has no AppleScript API for process data. Use `ps`, `top`, or `vm_stat` instead.",
    "appstore": "App Store has no AppleScript API for listing installed apps or checking updates. Search works via macappstore:// URL scheme.",
}


def _maps_open_url(url: str) -> tuple[int, str, str]:
    script = (
        'tell application "Maps"\n'
        '  activate\n'
        f'  open location "{url}"\n'
        'end tell'
    )
    return _osascript(script)


def _maps_search(query: str) -> dict:
    from urllib.parse import quote
    rc, _, err = _maps_open_url(f"maps://?q={quote(query)}")
    return {"status": "opened", "query": query} if rc == 0 else {"error": err}


def _maps_directions(src: str, dst: str) -> dict:
    from urllib.parse import quote
    rc, _, err = _maps_open_url(
        f"maps://?saddr={quote(src)}&daddr={quote(dst)}")
    return {"status": "opened", "from": src, "to": dst} if rc == 0 else {"error": err}


def _maps_open(address: str) -> dict:
    from urllib.parse import quote
    rc, _, err = _maps_open_url(f"maps://?q={quote(address)}")
    return {"status": "opened", "address": address} if rc == 0 else {"error": err}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="app", required=True)

    notes = sub.add_parser("notes")
    notes_sub = notes.add_subparsers(dest="action", required=True)
    notes_sub.add_parser("list").add_argument("--limit", type=int, default=20)
    nc = notes_sub.add_parser("create")
    nc.add_argument("--title", required=True)
    nc.add_argument("--body", required=True)
    ns = notes_sub.add_parser("search")
    ns.add_argument("query")

    rems = sub.add_parser("reminders")
    rems_sub = rems.add_subparsers(dest="action", required=True)
    rems_sub.add_parser("list")
    ra = rems_sub.add_parser("add")
    ra.add_argument("--title", required=True)
    ra.add_argument("--due", default="")
    rc_ = rems_sub.add_parser("complete")
    rc_.add_argument("--title", required=True)

    maps = sub.add_parser("maps")
    maps_sub = maps.add_subparsers(dest="action", required=True)
    ms = maps_sub.add_parser("search")
    ms.add_argument("query")
    md = maps_sub.add_parser("directions")
    md.add_argument("--from", dest="src", required=True)
    md.add_argument("--to", dest="dst", required=True)
    mo = maps_sub.add_parser("open")
    mo.add_argument("address")

    mail = sub.add_parser("mail")
    mail_sub = mail.add_subparsers(dest="action", required=True)
    mail_sub.add_parser("unread")
    ml = mail_sub.add_parser("list")
    ml.add_argument("--limit", type=int, default=20)

    cal = sub.add_parser("calendar")
    cal_sub = cal.add_subparsers(dest="action", required=True)
    cal_sub.add_parser("list")
    cal_sub.add_parser("today")
    ca = cal_sub.add_parser("add")
    ca.add_argument("--title", required=True)
    ca.add_argument("--date", required=True)
    ca.add_argument("--calendar", default="")

    term = sub.add_parser("terminal")
    term_sub = term.add_subparsers(dest="action", required=True)
    tr = term_sub.add_parser("run")
    tr.add_argument("command")

    sc = sub.add_parser("shortcuts")
    sc_sub = sc.add_subparsers(dest="action", required=True)
    sc_sub.add_parser("list")
    sr = sc_sub.add_parser("run")
    sr.add_argument("name")

    contacts = sub.add_parser("contacts")
    contacts_sub = contacts.add_subparsers(dest="action", required=True)
    contacts_sub.add_parser("count")
    cs = contacts_sub.add_parser("search")
    cs.add_argument("query")

    photos = sub.add_parser("photos")
    photos_sub = photos.add_subparsers(dest="action", required=True)
    photos_sub.add_parser("count")
    photos_sub.add_parser("albums")

    ast = sub.add_parser("appstore")
    ast_sub = ast.add_subparsers(dest="action", required=True)
    asq = ast_sub.add_parser("search")
    asq.add_argument("term")

    phone = sub.add_parser("phone")
    phone_sub = phone.add_subparsers(dest="action", required=True)
    po = phone_sub.add_parser("open")
    po.add_argument("number")

    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not Path("/usr/bin/osascript").exists():
        print("error: osascript not found — this skill requires macOS", file=sys.stderr)
        return 2

    result = {}
    if args.app == "notes":
        if args.action == "list":
            result = _notes_list(args.limit)
        elif args.action == "create":
            result = _notes_create(args.title, args.body)
        elif args.action == "search":
            result = _notes_search(args.query)
    elif args.app == "reminders":
        if args.action == "list":
            result = _reminders_list()
        elif args.action == "add":
            result = _reminders_add(args.title, args.due)
        elif args.action == "complete":
            result = _reminders_complete(args.title)
    elif args.app == "maps":
        if args.action == "search":
            result = _maps_search(args.query)
        elif args.action == "directions":
            result = _maps_directions(args.src, args.dst)
        elif args.action == "open":
            result = _maps_open(args.address)
    elif args.app == "mail":
        if args.action == "unread":
            result = _mail_unread()
        elif args.action == "list":
            result = _mail_list(args.limit)
    elif args.app == "calendar":
        if args.action == "list":
            result = _calendar_list()
        elif args.action == "today":
            result = _calendar_today()
        elif args.action == "add":
            result = _calendar_add(args.title, args.date, args.calendar)
    elif args.app == "terminal":
        if args.action == "run":
            result = _terminal_run(args.command)
    elif args.app == "shortcuts":
        if args.action == "list":
            result = _shortcuts_list()
        elif args.action == "run":
            result = _shortcuts_run(args.name)
    elif args.app == "contacts":
        if args.action == "count":
            result = _contacts_count()
        elif args.action == "search":
            result = _contacts_search(args.query)
    elif args.app == "photos":
        if args.action == "count":
            result = _photos_count()
        elif args.action == "albums":
            result = _photos_albums()
    elif args.app == "appstore":
        if args.action == "search":
            result = _appstore_search(args.term)
    elif args.app == "phone":
        if args.action == "open":
            result = _phone_open(args.number)
    elif args.app in NOT_SCRIPTABLE:
        print(f"error: {NOT_SCRIPTABLE[args.app]}", file=sys.stderr)
        return 2

    if "error" in result:
        print(f"error: {result['error']}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for k, v in result.items():
            print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
