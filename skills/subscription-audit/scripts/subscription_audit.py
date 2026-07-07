#!/usr/bin/env python3
"""subscription_audit.py — find the recurring charges quietly draining a bank/card statement.

Point it at a CSV you exported from your bank or card (date, description, amount)
and it finds the *recurring* charges — the subscriptions — by clustering repeat
payments to the same merchant at a regular cadence (monthly / yearly / weekly).
It tells you the true monthly cost, flags the ones that look forgotten (haven't
hit in a while, or a free-trial-then-charge shape), and totals what you'd save by
cutting the stale ones.

The problem this solves: subscriptions are designed to be invisible. Each is small,
they land on different days, and nobody re-reads a year of statements by hand. This
is the re-reader — offline, deterministic, no bank login, no third-party service.

Usage:
    subscription_audit.py STATEMENT.csv [--budget N] [--stale-days N] [--json]
    subscription_audit.py -            # read CSV from stdin
    cat card.csv | subscription_audit.py - --budget 100

CSV is auto-sniffed: it finds the date, description, and amount columns by header
name or by content, so most bank/card exports work with no flags. Amounts may be
negative (debits) or positive; magnitude is what matters.

Exit code is non-zero when the detected recurring monthly spend blows --budget, so
it drops into a monthly cron / CI check ("ping me if my subscriptions creep past $X").
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from statistics import median

# ── column sniffing ────────────────────────────────────────────────────────
_DATE_HINTS = ("date", "posted", "transaction date", "trans date", "일자", "날짜", "거래일")
_DESC_HINTS = ("description", "desc", "merchant", "name", "payee", "memo", "details",
               "narration", "적요", "내용", "가맹점")
_AMT_HINTS = ("amount", "amt", "debit", "charge", "value", "금액", "출금", "결제금액")

_DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%d/%m/%y",
    "%d-%m-%Y", "%Y.%m.%d", "%m-%d-%Y", "%b %d, %Y", "%d %b %Y", "%Y%m%d",
)


def _parse_date(s: str) -> date | None:
    s = s.strip().strip('"')
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # last resort: ISO prefix like 2026-07-07T12:00:00
    m = re.match(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


_AMT_RE = re.compile(r"-?\(?\$?[\d,]+\.?\d*\)?")


def _parse_amount(s: str) -> float | None:
    s = s.strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.replace("(", "").replace(")", "")
    m = _AMT_RE.search(s)
    if not m:
        return None
    raw = m.group(0).replace("$", "").replace(",", "").replace("(", "").replace(")", "")
    try:
        val = float(raw)
    except ValueError:
        return None
    return -abs(val) if neg else val


def _pick_columns(header: list[str], sample: list[list[str]]):
    """Return (date_idx, desc_idx, amt_idx), sniffing by header then by content."""
    lower = [h.strip().lower() for h in header]

    def find(hints):
        for i, h in enumerate(lower):
            if any(hint in h for hint in hints):
                return i
        return None

    d_i, s_i, a_i = find(_DATE_HINTS), find(_DESC_HINTS), find(_AMT_HINTS)

    ncols = len(header)
    # content-based fallback for any column we couldn't name
    if d_i is None or a_i is None or s_i is None:
        date_hits = [0] * ncols
        amt_hits = [0] * ncols
        text_len = [0] * ncols
        for row in sample:
            for i in range(min(ncols, len(row))):
                cell = row[i]
                if _parse_date(cell):
                    date_hits[i] += 1
                if _parse_amount(cell) is not None and re.search(r"\d", cell):
                    amt_hits[i] += 1
                text_len[i] += len(cell)
        if d_i is None and any(date_hits):
            d_i = max(range(ncols), key=lambda i: date_hits[i])
        if a_i is None and any(amt_hits):
            order = sorted(range(ncols), key=lambda i: amt_hits[i], reverse=True)
            a_i = next((i for i in order if i != d_i), order[0])
        if s_i is None:
            s_i = max(range(ncols), key=lambda i: text_len[i] if i not in (d_i, a_i) else -1)
    return d_i, s_i, a_i


# ── merchant normalisation ─────────────────────────────────────────────────
_NORM_STRIP = re.compile(r"[^a-z0-9가-힣 ]+")
_TRAILING_NOISE = re.compile(
    r"\b(?:\d{2,}|x{2,}\d+|#\d+|auth|autopay|recurring|payment|pmt|purchase|"
    r"pos|debit|card|visa|mastercard|www|com|http\S*|ref\S*|id\s*\d+)\b")


def _normalise_merchant(desc: str) -> str:
    d = desc.lower().strip()
    d = re.sub(r"https?://\S+", "", d)
    d = _NORM_STRIP.sub(" ", d)
    d = _TRAILING_NOISE.sub(" ", d)
    d = re.sub(r"\s+", " ", d).strip()
    # keep the first 3 tokens — enough to identify a merchant, drops store #s
    toks = d.split()
    return " ".join(toks[:3]) if toks else desc.lower().strip()


@dataclass
class Txn:
    when: date
    desc: str
    amount: float
    merchant: str


@dataclass
class Subscription:
    merchant: str
    cadence: str          # monthly | yearly | weekly | irregular
    period_days: float
    monthly_cost: float
    typical_amount: float
    count: int
    first: date
    last: date
    days_since_last: int
    label_desc: str
    stale: bool = False
    trial_shape: bool = False

    def to_dict(self) -> dict:
        return {
            "merchant": self.merchant,
            "example_description": self.label_desc,
            "cadence": self.cadence,
            "period_days": round(self.period_days, 1),
            "typical_amount": round(self.typical_amount, 2),
            "monthly_cost": round(self.monthly_cost, 2),
            "charges": self.count,
            "first_seen": self.first.isoformat(),
            "last_seen": self.last.isoformat(),
            "days_since_last": self.days_since_last,
            "stale": self.stale,
            "free_trial_shape": self.trial_shape,
        }


# ── cadence classification ─────────────────────────────────────────────────
_CADENCE_BANDS = (
    ("weekly", 7, 3),
    ("monthly", 30.4, 8),
    ("quarterly", 91.3, 15),
    ("yearly", 365, 40),
)


def _classify(period: float) -> tuple[str, float]:
    """Return (cadence, monthly_multiplier) for an average period in days."""
    for name, center, tol in _CADENCE_BANDS:
        if abs(period - center) <= tol:
            return name, 30.4 / center
    return "irregular", 30.4 / period if period else 1.0


def detect(txns: list[Txn], min_charges: int = 3, stale_days: int = 75,
           today: date | None = None) -> list[Subscription]:
    today = today or (max(t.when for t in txns) if txns else date.today())
    by_merchant: dict[str, list[Txn]] = defaultdict(list)
    for t in txns:
        if abs(t.amount) < 0.01:
            continue
        by_merchant[t.merchant].append(t)

    subs: list[Subscription] = []
    for merchant, group in by_merchant.items():
        group.sort(key=lambda t: t.when)
        # dedupe same-day duplicates
        uniq: list[Txn] = []
        for t in group:
            if uniq and uniq[-1].when == t.when and abs(uniq[-1].amount - t.amount) < 0.01:
                continue
            uniq.append(t)
        if len(uniq) < min_charges:
            continue
        gaps = [(uniq[i + 1].when - uniq[i].when).days for i in range(len(uniq) - 1)]
        gaps = [g for g in gaps if g > 0]
        if not gaps:
            continue
        period = median(gaps)
        if period > 400:          # more than ~yearly → not a subscription rhythm
            continue
        # amount consistency: recurring charges are near-constant
        amts = [abs(t.amount) for t in uniq]
        typical = median(amts)
        if typical <= 0:
            continue
        spread = (max(amts) - min(amts)) / typical
        if spread > 0.6:          # too variable → looks like normal spending, not a sub
            continue
        cadence, mult = _classify(period)
        if cadence == "irregular" and period > 45:
            continue
        monthly = typical * mult
        last = uniq[-1].when
        days_since = (today - last).days
        stale = days_since > (period + stale_days)
        # free-trial shape: first charge notably smaller (or zero) than the rest
        first_amt = abs(uniq[0].amount)
        rest_typical = median(amts[1:]) if len(amts) > 1 else typical
        trial = first_amt < rest_typical * 0.5 and rest_typical > 0
        subs.append(Subscription(
            merchant=merchant, cadence=cadence, period_days=period,
            monthly_cost=monthly, typical_amount=typical, count=len(uniq),
            first=uniq[0].when, last=last, days_since_last=days_since,
            label_desc=uniq[-1].desc, stale=stale, trial_shape=trial,
        ))
    subs.sort(key=lambda s: s.monthly_cost, reverse=True)
    return subs


# ── input ──────────────────────────────────────────────────────────────────
def load_csv(text: str) -> list[Txn]:
    # sniff delimiter
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
        delim = dialect.delimiter
    except csv.Error:
        delim = ","
    reader = list(csv.reader(io.StringIO(text), delimiter=delim))
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return []
    header = rows[0]
    # is the first row a header (no date/amount) or already data?
    first_is_header = not (_parse_date(header[0]) or
                           any(_parse_amount(c) is not None and re.search(r"\d", c) for c in header))
    body = rows[1:] if first_is_header else rows
    if not first_is_header:
        header = [f"col{i}" for i in range(len(rows[0]))]
    d_i, s_i, a_i = _pick_columns(header, body[:50])
    if d_i is None or a_i is None or s_i is None:
        return []
    txns: list[Txn] = []
    for row in body:
        if max(d_i, s_i, a_i) >= len(row):
            continue
        when = _parse_date(row[d_i])
        amt = _parse_amount(row[a_i])
        desc = row[s_i].strip()
        if when is None or amt is None or not desc:
            continue
        txns.append(Txn(when=when, desc=desc, amount=amt, merchant=_normalise_merchant(desc)))
    return txns


# ── render ─────────────────────────────────────────────────────────────────
def render(subs: list[Subscription], budget: float | None, currency: str = "$") -> str:
    if not subs:
        return ("No recurring charges detected. Either this statement is short "
                "(need ≥3 hits of a merchant) or you have no subscriptions — nice.")
    total_monthly = sum(s.monthly_cost for s in subs)
    stale = [s for s in subs if s.stale]
    stale_monthly = sum(s.monthly_cost for s in stale)
    lines = []
    lines.append("Subscription audit")
    lines.append("=" * 70)
    lines.append(f"{'monthly':>9}  {'each':>8}  {'cadence':<9}  {'last':<12}  merchant")
    lines.append("-" * 70)
    for s in subs:
        flags = []
        if s.stale:
            flags.append("STALE")
        if s.trial_shape:
            flags.append("trial→paid")
        flag = ("  ⚠ " + ",".join(flags)) if flags else ""
        lines.append(
            f"{currency}{s.monthly_cost:>7.2f}  {currency}{s.typical_amount:>6.2f}  "
            f"{s.cadence:<9}  {s.last.isoformat():<12}  {s.merchant}{flag}")
    lines.append("-" * 70)
    lines.append(f"{currency}{total_monthly:>7.2f}  monthly across {len(subs)} "
                 f"subscriptions  (≈ {currency}{total_monthly*12:,.0f}/yr)")
    if stale:
        lines.append("")
        lines.append(f"⚠ {len(stale)} look forgotten (no charge in a while): "
                     f"cutting them saves {currency}{stale_monthly:.2f}/mo "
                     f"(≈ {currency}{stale_monthly*12:,.0f}/yr).")
        for s in stale:
            lines.append(f"    · {s.merchant} — last seen {s.last.isoformat()} "
                         f"({s.days_since_last}d ago), {currency}{s.monthly_cost:.2f}/mo")
    if budget is not None:
        verdict = "OK" if total_monthly <= budget else "OVER BUDGET"
        lines.append("")
        lines.append(f"budget {currency}{budget:.2f}/mo  →  {verdict} "
                     f"({currency}{total_monthly:.2f} detected)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Find the recurring charges (subscriptions) hiding in a bank/card CSV.")
    ap.add_argument("csv", help="statement CSV path, or - for stdin")
    ap.add_argument("--budget", type=float, default=None,
                    help="monthly subscription budget; exit!=0 if detected spend exceeds it")
    ap.add_argument("--min-charges", type=int, default=3,
                    help="how many hits of a merchant before it counts as recurring (default 3)")
    ap.add_argument("--stale-days", type=int, default=75,
                    help="days past the expected next charge before flagging as forgotten")
    ap.add_argument("--currency", default="$", help="currency symbol for display (default $)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    if args.csv == "-":
        text = sys.stdin.read()
    else:
        try:
            with open(args.csv, encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError as e:
            print(f"error: cannot read {args.csv}: {e}", file=sys.stderr)
            return 2

    txns = load_csv(text)
    if not txns:
        print("error: could not parse any dated transactions with amounts from that CSV. "
              "Expected columns for date, description, and amount.", file=sys.stderr)
        return 2

    subs = detect(txns, min_charges=args.min_charges, stale_days=args.stale_days)
    total_monthly = sum(s.monthly_cost for s in subs)

    if args.json:
        print(json.dumps({
            "transactions_parsed": len(txns),
            "subscriptions_found": len(subs),
            "total_monthly": round(total_monthly, 2),
            "total_yearly": round(total_monthly * 12, 2),
            "stale_count": sum(1 for s in subs if s.stale),
            "stale_monthly": round(sum(s.monthly_cost for s in subs if s.stale), 2),
            "budget": args.budget,
            "over_budget": bool(args.budget is not None and total_monthly > args.budget),
            "subscriptions": [s.to_dict() for s in subs],
        }, indent=2))
    else:
        print(render(subs, args.budget, args.currency))

    if args.budget is not None and total_monthly > args.budget:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
