#!/usr/bin/env python3
"""Backfill deposition_year into existing dataset records (growth-stats support).

The catalog stores no per-dataset deposition date; this resolves each record's
repository release/publication YEAR from its accession (build/deposition.py) and
writes it surgically into the YAML - inserting a single `deposition_year:` line
before `curation_status:`, leaving everything else byte-for-byte unchanged (the
same minimal-edit discipline as build/promote.py). Records that already carry a
year, or whose source exposes no public date (Synapse/HTAN, CELLxGENE, 10x), are
left untouched.

Network-dependent, so NOT part of offline CI. Harvesters set deposition_year on
NEW drafts directly, so this only needs re-running for records that predate a
source gaining a resolvable date.

Usage:
  uv run python build/backfill_deposition_year.py --dry-run
  uv run python build/backfill_deposition_year.py --status machine_draft
  uv run python build/backfill_deposition_year.py --json report.json
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import deposition
import runlog
import validate

DATASETS = validate.ROOT / "records" / "datasets"


def add_deposition_year(path: Path, year: int) -> bool:
    text = path.read_text()
    if re.search(r"^\s*deposition_year:", text, re.M):
        return False  # already present
    m = re.search(r"^curation_status:.*$", text, re.M)
    if not m:
        return False
    new = text[: m.start()] + f"deposition_year: {year}\n" + text[m.start() :]
    path.write_text(new)
    return True


def resolve_for(d: dict) -> int | None:
    """Earliest deposition year across a record's accessions (best-effort)."""
    years = []
    for acc in d.get("accession", []) or []:
        y = deposition.resolve_deposition_year(acc)
        if y:
            years.append(y)
        time.sleep(deposition.THROTTLE)
    return min(years) if years else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--status", help="only records with this curation_status")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", metavar="PATH", help="write a JSON report to PATH")
    args = ap.parse_args(argv)

    datasets = validate.load_records("datasets")
    results = []
    written = 0
    resolved = 0
    checked = 0

    for rid, (_, d) in sorted(datasets.items()):
        if args.status and d.get("curation_status") != args.status:
            continue
        if d.get("deposition_year"):
            continue
        checked += 1
        year = resolve_for(d)
        results.append({"dataset": rid, "deposition_year": year})
        mark = "----"
        if year:
            resolved += 1
            path = DATASETS / f"{rid}.yaml"
            if not args.dry_run and add_deposition_year(path, year):
                written += 1
                mark = "SET "
            elif args.dry_run:
                mark = "dry "
        print(f"  [{mark}] {rid:52} {year if year else ''}")
        if args.limit and checked >= args.limit:
            break

    verb = "would set" if args.dry_run else "set"
    print(
        f"\nChecked {checked} record(s) without a year: resolved {resolved}, "
        f"{verb} {written if not args.dry_run else resolved}."
    )
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2) + "\n")
        print(f"Report written to {args.json}")

    runlog.log(
        "backfill_deposition_year",
        status="ok",
        checked=checked,
        resolved=resolved,
        written=written,
        scope=args.status or "all",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
