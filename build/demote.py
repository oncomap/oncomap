#!/usr/bin/env python3
"""Demote a record and log the corrective action.

When an accession dies, a source DB restructures, or a verified record is found
wrong, the record must drop out of the top trust tier and the action must be
recorded. This flips curation_status (verified -> human_reviewed by default, or
-> machine_draft for a serious defect) and appends a row to the corrective-
action register (docs/CORRECTIVE_ACTIONS.md). See docs/INCIDENT_RESPONSE.md.

Usage
  uv run python build/demote.py <record-id> --reason "GSE... 404s at GEO"
  uv run python build/demote.py <record-id> --to machine_draft --reason "wrong cancer_type"
  uv run python build/demote.py <record-id> --reason "..." --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import runlog
import validate

REGISTER = validate.ROOT / "docs" / "CORRECTIVE_ACTIONS.md"
DATASETS = validate.RECORDS_DIR / "datasets"


def demote_file(path: Path, to: str) -> str | None:
    """Flip curation_status to ``to``; return the previous status, or None."""
    text = path.read_text()
    m = re.search(r"^curation_status:\s*(\w+)\s*$", text, re.M)
    if not m:
        return None
    prev = m.group(1)
    path.write_text(
        re.sub(
            r"^curation_status:\s*\w+\s*$",
            f"curation_status: {to}",
            text,
            count=1,
            flags=re.M,
        )
    )
    return prev


def append_register(rid: str, frm: str, to: str, reason: str) -> None:
    row = f"| {date.today().isoformat()} | `{rid}` | {frm} -> {to} | {reason} |\n"
    with REGISTER.open("a", encoding="utf-8") as fh:
        fh.write(row)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("record_id")
    ap.add_argument(
        "--reason", required=True, help="what went wrong (goes in the register)"
    )
    ap.add_argument(
        "--to", default="human_reviewed", choices=["human_reviewed", "machine_draft"]
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    path = DATASETS / f"{args.record_id}.yaml"
    if not path.exists():
        print(f"no such record: {path}", file=sys.stderr)
        return 2
    if args.dry_run:
        print(f"[dry] would demote {args.record_id} -> {args.to} ({args.reason})")
        return 0
    prev = demote_file(path, args.to)
    if prev is None:
        print(f"no curation_status line in {path.name}", file=sys.stderr)
        return 2
    append_register(args.record_id, prev, args.to, args.reason)
    runlog.log("demote", record=args.record_id, frm=prev, to=args.to)
    print(f"demoted {args.record_id}: {prev} -> {args.to}; logged to {REGISTER.name}")
    print("Remember to run validate + commit, and note the change in the next release.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
