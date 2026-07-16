#!/usr/bin/env python3
"""Validate OncoMap records against the JSON Schemas and cross-record rules.

This is the CI gate referenced in docs/OncoMap-SPEC.md §5. It enforces four
layers:

  1. Schema conformance   -- every record matches its node-type schema.
  2. Curation trust gate   -- a `verified` dataset must carry a resolvable
                              accession list + last_verified + source_paper
                              (structural half here; live dead-link checks
                              are deferred).
  3. Referential integrity -- every cross-reference (source_paper, lab,
                              pipeline_ref, datasets[], reference_paper) points
                              at a record that actually exists.
  4. Vocabulary membership -- cancer_type is a real OncoTree code (with a
                              consistent NCIt cross-map) and tissue is a term
                              in the frozen UBERON subset. See vocab/.

Exit code is non-zero if any record fails, so it can gate commits and PRs.
Run: `python build/validate.py` (or `uv run python build/validate.py`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import runlog  # sibling; structured run logging
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"
RECORDS_DIR = ROOT / "records"
VOCAB_DIR = ROOT / "vocab"

# node type -> (records subdir, schema file)
NODE_TYPES = {
    "dataset": ("datasets", "dataset.schema.json"),
    "paper": ("papers", "paper.schema.json"),
    "method": ("methods", "method.schema.json"),
    "group": ("groups", "group.schema.json"),
}


def load_schema(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMA_DIR / name).read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def load_oncotree() -> dict[str, dict] | None:
    """Load the frozen OncoTree snapshot (vocab/oncotree.json), or None if absent."""
    p = VOCAB_DIR / "oncotree.json"
    if not p.exists():
        return None
    return json.loads(p.read_text()).get("codes", {})


def load_uberon() -> dict[str, dict] | None:
    """Load the frozen UBERON tissue snapshot (vocab/uberon.json), or None if absent."""
    p = VOCAB_DIR / "uberon.json"
    if not p.exists():
        return None
    return json.loads(p.read_text()).get("terms", {})


def load_records(subdir: str) -> dict[str, tuple[Path, dict]]:
    """Return {id: (path, record)} for all YAML records in a subdir."""
    out: dict[str, tuple[Path, dict]] = {}
    base = RECORDS_DIR / subdir
    if not base.exists():
        return out
    for path in sorted(base.glob("*.y*ml")):
        if path.name.startswith("_") or path.name.startswith("."):
            continue  # templates / hidden files are not records
        data = yaml.safe_load(path.read_text())
        if data is None:
            continue
        rid = data.get("id", f"<no-id:{path.name}>")
        out[rid] = (path, data)
    return out


def main() -> int:
    errors: list[str] = []

    validators = {nt: load_schema(schema) for nt, (_, schema) in NODE_TYPES.items()}
    records = {nt: load_records(subdir) for nt, (subdir, _) in NODE_TYPES.items()}

    # Layer 1: schema conformance
    for nt, recs in records.items():
        for rid, (path, data) in recs.items():
            for err in sorted(validators[nt].iter_errors(data), key=str):
                loc = "/".join(str(p) for p in err.absolute_path) or "(root)"
                errors.append(f"[schema:{nt}] {path.name} :: {loc}: {err.message}")

    dataset_ids = set(records["dataset"])
    paper_ids = set(records["paper"])
    method_ids = set(records["method"])
    group_ids = set(records["group"])

    # Layer 3: referential integrity
    for rid, (path, d) in records["dataset"].items():
        for field, universe in (
            ("source_paper", paper_ids),
            ("lab", group_ids),
            ("pipeline_ref", method_ids),
        ):
            ref = d.get(field)
            if ref and ref not in universe:
                errors.append(
                    f"[ref:dataset] {path.name} :: {field} -> unknown id '{ref}'"
                )

    for rid, (path, p) in records["paper"].items():
        for ref in p.get("datasets", []):
            if ref not in dataset_ids:
                errors.append(
                    f"[ref:paper] {path.name} :: datasets[] -> unknown id '{ref}'"
                )

    for rid, (path, m) in records["method"].items():
        ref = m.get("reference_paper")
        if ref and ref not in paper_ids:
            errors.append(
                f"[ref:method] {path.name} :: reference_paper -> unknown id '{ref}'"
            )

    for rid, (path, g) in records["group"].items():
        for ref in g.get("datasets", []):
            if ref not in dataset_ids:
                errors.append(
                    f"[ref:group] {path.name} :: datasets[] -> unknown id '{ref}'"
                )

    # Layer 4: controlled-vocabulary membership.
    # The schema enforces term *format*; here we enforce *membership* in the
    # frozen OncoTree snapshot, and consistency of any NCIt cross-map.
    oncotree = load_oncotree()
    if oncotree is None:
        errors.append(
            "[vocab] vocab/oncotree.json missing - run `python vocab/build_vocab.py`"
        )
    else:
        for rid, (path, d) in records["dataset"].items():
            code = d.get("cancer_type")
            if code and code not in oncotree:
                errors.append(
                    f"[vocab:dataset] {path.name} :: cancer_type '{code}' "
                    f"not an OncoTree code"
                )
            elif code:
                expected_ncit = oncotree[code].get("ncit")
                given_ncit = d.get("cancer_type_ncit")
                if given_ncit and expected_ncit and given_ncit != expected_ncit:
                    errors.append(
                        f"[vocab:dataset] {path.name} :: cancer_type_ncit "
                        f"'{given_ncit}' != OncoTree mapping '{expected_ncit}' "
                        f"for {code}"
                    )

    uberon = load_uberon()
    if uberon is None:
        errors.append(
            "[vocab] vocab/uberon.json missing - run `python vocab/build_vocab.py`"
        )
    else:
        for rid, (path, d) in records["dataset"].items():
            tissue = d.get("tissue")
            if tissue and tissue not in uberon:
                errors.append(
                    f"[vocab:dataset] {path.name} :: tissue '{tissue}' not in the "
                    f"frozen UBERON set (add it to vocab/uberon_tissue_seed.txt)"
                )

    total = sum(len(r) for r in records.values())
    if errors:
        print(
            f"FAIL: {len(errors)} problem(s) across {total} record(s):\n",
            file=sys.stderr,
        )
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        runlog.log("validate", status="fail", records=total, invalid=len(errors))
        return 1

    counts = ", ".join(f"{nt}={len(records[nt])}" for nt in NODE_TYPES)
    print(f"OK: {total} record(s) valid ({counts}).")
    runlog.log("validate", records=total, invalid=0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
