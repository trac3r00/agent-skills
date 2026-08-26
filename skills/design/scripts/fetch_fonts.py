#!/usr/bin/env python3
"""Download curated open-license (OFL) fonts from Google Fonts for design work.

Instead of vendoring ~5.5MB of TTFs in the repo, this fetches the same curated
families on demand and caches them locally. Zero dependencies (stdlib only).

Usage:
    python3 fetch_fonts.py                 # list families
    python3 fetch_fonts.py Lora Outfit     # fetch specific families
    python3 fetch_fonts.py --all           # fetch everything
    python3 fetch_fonts.py --dir ~/fonts   # custom cache dir (default ./fonts)

Fonts are downloaded from the google/fonts GitHub repo (OFL directory), which
serves raw TTFs without an API key.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Curated families: display / body / mono / decorative, all SIL OFL licensed.
FAMILIES = {
    # display
    "BigShoulders": "bigshouldersdisplay",
    "Boldonse": "boldonse",
    "BricolageGrotesque": "bricolagegrotesque",
    "EricaOne": "ericaone",
    "Gloock": "gloock",
    "Italiana": "italiana",
    "PoiretOne": "poiretone",
    "SmoochSans": "smoochsans",
    "Tektur": "tektur",
    "YoungSerif": "youngserif",
    # body
    "CrimsonPro": "crimsonpro",
    "IBMPlexSerif": "ibmplexserif",
    "InstrumentSans": "instrumentsans",
    "InstrumentSerif": "instrumentserif",
    "LibreBaskerville": "librebaskerville",
    "Lora": "lora",
    "Outfit": "outfit",
    "WorkSans": "worksans",
    # mono
    "DMMono": "dmmono",
    "GeistMono": "geistmono",
    "IBMPlexMono": "ibmplexmono",
    "JetBrainsMono": "jetbrainsmono",
    "RedHatMono": "redhatmono",
    "Jura": "jura",
    "NothingYouCouldDo": "nothingyoucoulddo",
    "PixelifySans": "pixelifysans",
    "Silkscreen": "silkscreen",
}

API = "https://api.github.com/repos/google/fonts/contents/ofl/{slug}"
UA = {"User-Agent": "agent-skills-fetch-fonts"}


def fetch_family(name: str, slug: str, dest: Path) -> list[str]:
    req = urllib.request.Request(API.format(slug=slug), headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        entries = json.load(r)
    saved = []
    for e in entries:
        if not e["name"].endswith(".ttf"):
            continue
        out = dest / f"{name}-{e['name'].split('-')[-1]}" if "-" in e["name"] else dest / e["name"]
        if out.exists():
            saved.append(str(out))
            continue
        dl = urllib.request.Request(e["download_url"], headers=UA)
        with urllib.request.urlopen(dl, timeout=60) as r:
            out.write_bytes(r.read())
        saved.append(str(out))
    return saved


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("families", nargs="*", help="family names to fetch (see --list)")
    ap.add_argument("--all", action="store_true", help="fetch every curated family")
    ap.add_argument("--dir", default="fonts", help="download directory (default ./fonts)")
    args = ap.parse_args()

    if not args.families and not args.all:
        print("Curated families (pass names, or --all):")
        for name in sorted(FAMILIES):
            print(f"  {name}")
        return 0

    wanted = sorted(FAMILIES) if args.all else args.families
    unknown = [f for f in wanted if f not in FAMILIES]
    if unknown:
        print(f"Unknown families: {', '.join(unknown)}", file=sys.stderr)
        return 2

    dest = Path(args.dir).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    failures = 0
    for name in wanted:
        try:
            saved = fetch_family(name, FAMILIES[name], dest)
            print(f"{name}: {len(saved)} file(s)")
        except (urllib.error.URLError, OSError) as exc:
            print(f"{name}: FAILED ({exc})", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
