#!/usr/bin/env python3
"""net-probe: network diagnostics with nothing but the stdlib socket/ssl modules.

Port checks (connect, not SYN-scan), DNS resolution, HTTP latency, and TLS
certificate expiry — the "is it up, is it reachable, is the cert about to
die" triage without nmap, dig, or openssl. Deterministic, offline-capable
against local targets.

Usage:
    net_probe.py --port-check 127.0.0.1:5432 [--port-check host:port ...] [--json]
    net_probe.py --dns example.com
    net_probe.py --tls example.com:443
    net_probe.py --latency https://example.com --count 3

Exit codes: 0 all good, 1 a check failed (closed port, expiry < warn days), 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
import time
import urllib.request


def port_check(target: str, timeout: float) -> dict:
    host, _, port = target.rpartition(":")
    if not host or not port.isdigit():
        return {"target": target, "error": "want host:port"}
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return {"target": target, "open": True}
    except (OSError, socket.timeout):
        return {"target": target, "open": False}


def dns_lookup(name: str) -> dict:
    try:
        infos = socket.getaddrinfo(name, None)
        addrs = sorted({i[4][0] for i in infos})
        return {"name": name, "addresses": addrs}
    except socket.gaierror as exc:
        return {"name": name, "error": str(exc)}


def tls_check(target: str, warn_days: int) -> dict:
    host, _, port = target.rpartition(":")
    port = int(port) if port.isdigit() else 443
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
        import datetime
        exp = datetime.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
        days = (exp - datetime.datetime.utcnow()).days
        return {"target": target, "expires": cert["notAfter"],
                "days_left": days, "ok": days >= warn_days,
                "issuer": dict(x[0] for x in cert.get("issuer", []))}
    except (OSError, ssl.SSLError) as exc:
        return {"target": target, "error": str(exc)}


def latency(url: str, count: int) -> dict:
    times = []
    for _ in range(count):
        start = time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                r.read(1)
            times.append(round((time.monotonic() - start) * 1000))
        except (urllib.error.URLError, OSError):
            return {"url": url, "error": "unreachable"}
    return {"url": url, "samples_ms": times,
            "min_ms": min(times), "avg_ms": sum(times) // len(times)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port-check", action="append", default=[], metavar="HOST:PORT")
    ap.add_argument("--dns", default="")
    ap.add_argument("--tls", default="", metavar="HOST:PORT")
    ap.add_argument("--tls-warn-days", type=int, default=14)
    ap.add_argument("--latency", default="")
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=3.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report: dict = {}
    failed = False
    if args.port_check:
        results = [port_check(t, args.timeout) for t in args.port_check]
        report["results"] = results
        failed = any(not r.get("open") for r in results)
    if args.dns:
        report.update(dns_lookup(args.dns))
        failed = failed or "error" in report
    if args.tls:
        r = tls_check(args.tls, args.tls_warn_days)
        report.update(r)
        failed = failed or "error" in r or not r.get("ok", True)
    if args.latency:
        r = latency(args.latency, args.count)
        report.update(r)
        failed = failed or "error" in r

    if not report:
        ap.error("pass at least one of --port-check/--dns/--tls/--latency")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for k, v in report.items():
            print(f"{k}: {v}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
