#!/usr/bin/env python3
"""Coverage & freshness monitoring: SLIs, SLOs, and the link-rot alert.

Computes the catalog's health indicators from the records (offline) plus, when
given a check_accessions report, the live accession resolve-rate. Emits a
machine dashboard (build/dist/health.json), a human table, and a GitHub job
summary, and exits non-zero when an SLO is breached so a scheduled run raises an
alert. Pass --warn-only to always exit 0 (dashboard without gating).

SLIs
  datasets, cancer_types, platforms      coverage breadth
  verified_fraction                      share of records at the top trust tier
  linked_fraction                        share with a source_paper
  stale_verified                         verified records not re-checked in STALE_DAYS
  recent_fraction                        share whose source paper is from the last 24 months
  dead_accessions / resolve_rate         from a check_accessions --json report, if provided

Usage
  uv run python build/monitor.py
  uv run python build/monitor.py --accession-report report.json      # adds resolve-rate
  uv run python build/monitor.py --warn-only                         # never gate
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import runlog
import validate

# --- Service level objectives (edit here to retune the alert thresholds) ----
SLO_VERIFIED_FRACTION = 0.45  # at least this share verified
SLO_MAX_DEAD = 0  # any dead accession is a link-rot incident
SLO_MAX_STALE = 0  # every verified record re-checked within STALE_DAYS
STALE_DAYS = 180


def _parse_date(v):
    if not v:
        return None
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        return None


def compute_slis(accession_report: Path | None = None) -> dict:
    datasets = validate.load_records("datasets")
    papers = validate.load_records("papers")
    pyear = {pid: data.get("year") for pid, (_, data) in papers.items()}

    n = len(datasets)
    by_status: dict[str, int] = {}
    cancers, platforms = set(), set()
    linked = stale = recent = 0
    today = date.today()
    this_year = today.year

    for _rid, (_path, d) in datasets.items():
        status = d.get("curation_status", "machine_draft")
        by_status[status] = by_status.get(status, 0) + 1
        cancers.add(d.get("cancer_type"))
        platforms.add(d.get("platform"))
        if d.get("source_paper"):
            linked += 1
            yr = pyear.get(d["source_paper"])
            if isinstance(yr, int) and yr >= this_year - 1:
                recent += 1
        if status == "verified":
            lv = _parse_date(d.get("last_verified"))
            if lv is None or (today - lv).days > STALE_DAYS:
                stale += 1

    verified = by_status.get("verified", 0)
    slis = {
        "datasets": n,
        "cancer_types": len({c for c in cancers if c}),
        "platforms": len({p for p in platforms if p}),
        "by_status": by_status,
        "verified_fraction": round(verified / n, 3) if n else 0,
        "linked_fraction": round(linked / n, 3) if n else 0,
        "stale_verified": stale,
        "recent_fraction": round(recent / n, 3) if n else 0,
    }

    if accession_report and accession_report.exists():
        rep = json.loads(accession_report.read_text())
        checked = len(rep)
        dead = sum(1 for r in rep if not r.get("alive"))
        slis["accessions_checked"] = checked
        slis["dead_accessions"] = dead
        slis["resolve_rate"] = round((checked - dead) / checked, 3) if checked else None
    return slis


def evaluate(slis: dict) -> list[str]:
    breaches = []
    if slis["verified_fraction"] < SLO_VERIFIED_FRACTION:
        breaches.append(
            f"verified_fraction {slis['verified_fraction']} < SLO {SLO_VERIFIED_FRACTION}"
        )
    if slis.get("stale_verified", 0) > SLO_MAX_STALE:
        breaches.append(
            f"stale_verified {slis['stale_verified']} > SLO {SLO_MAX_STALE} "
            f"(not re-checked in {STALE_DAYS} days)"
        )
    if "dead_accessions" in slis and slis["dead_accessions"] > SLO_MAX_DEAD:
        breaches.append(
            f"LINK ROT: {slis['dead_accessions']} dead accession(s) > SLO {SLO_MAX_DEAD}"
        )
    return breaches


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--accession-report", type=Path, help="check_accessions --json output"
    )
    ap.add_argument("--warn-only", action="store_true", help="never exit non-zero")
    args = ap.parse_args(argv)

    slis = compute_slis(args.accession_report)
    breaches = evaluate(slis)

    health = {
        "generated": date.today().isoformat(),
        "run_id": runlog.run_id(),
        "slos": {
            "verified_fraction_min": SLO_VERIFIED_FRACTION,
            "max_dead_accessions": SLO_MAX_DEAD,
            "max_stale_verified": SLO_MAX_STALE,
            "stale_days": STALE_DAYS,
        },
        "slis": slis,
        "breaches": breaches,
        "healthy": not breaches,
    }
    dist = validate.ROOT / "build" / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "health.json").write_text(json.dumps(health, indent=2) + "\n")

    print("OncoMap health")
    for k in (
        "datasets",
        "cancer_types",
        "platforms",
        "verified_fraction",
        "linked_fraction",
        "recent_fraction",
        "stale_verified",
        "resolve_rate",
        "dead_accessions",
    ):
        if k in slis:
            print(f"  {k:20} {slis[k]}")
    print(f"  status               {'HEALTHY' if not breaches else 'BREACH'}")
    for b in breaches:
        print(f"    ! {b}")

    import os

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("\n### Catalog health\n\n")
            fh.write(
                f"**{'HEALTHY' if not breaches else 'SLO BREACH'}** - "
                f"{slis['datasets']} datasets, {slis['verified_fraction']:.0%} verified"
            )
            if "resolve_rate" in slis:
                fh.write(
                    f", resolve-rate {slis['resolve_rate']:.1%} "
                    f"({slis['dead_accessions']} dead)"
                )
            fh.write("\n")
            for b in breaches:
                fh.write(f"- {b}\n")

    runlog.log(
        "monitor",
        status="fail" if breaches else "ok",
        verified_fraction=slis["verified_fraction"],
        dead=slis.get("dead_accessions", "n/a"),
        breaches=len(breaches),
    )
    return 0 if (args.warn_only or not breaches) else 1


if __name__ == "__main__":
    raise SystemExit(main())
