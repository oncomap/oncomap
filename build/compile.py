#!/usr/bin/env python3
"""Compile OncoMap records into a graph, flat tables, and a site payload.

Deterministic and re-runnable: same records in -> same
bytes out (no wall-clock timestamps in the artifacts). Reads records/ + the
frozen vocab snapshots, writes build/dist/:

  - datasets.csv       flat one-row-per-dataset table (stdlib csv)
  - datasets.parquet   same table (only if pyarrow is installed; skipped w/ note)
  - graph.json         knowledge graph: nodes + typed edges
  - site.json          denormalized payload for the static browsable view
  - summary.json       coverage stats (counts by platform/cancer/status/access)

This does NOT validate; run build/validate.py first (CI does both). Record
loading + vocab access are reused from validate.py so the two stay in lockstep.

Run: uv run python build/compile.py  (add --extra build for parquet)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import runlog  # sibling; structured run logging
import validate  # sibling module; import is safe (main-guarded)

DIST = validate.ROOT / "build" / "dist"

# Flat dataset table columns (order is stable for deterministic output).
DATASET_COLUMNS = [
    "id",
    "title",
    "cancer_type",
    "cancer_type_name",
    "cancer_type_ncit",
    "tissue",
    "tissue_label",
    "modality",
    "platform",
    "sequencer",
    "n_samples",
    "n_patients",
    "accession",
    "access",
    "curation_status",
    "last_verified",
    "deposition_year",
    "source_paper",
    "paper_doi",
    "paper_year",
    "lab",
    "lab_name",
    "pipeline_ref",
    "method_name",
    "reuse_notes",
]


def _first(value):
    """Return the first element of a list, else the value itself, else ''."""
    if isinstance(value, list):
        return value[0] if value else ""
    return value if value is not None else ""


def build_rows(records, oncotree, uberon):
    """Return a list of flat dataset dicts with references + vocab resolved."""
    papers = {rid: d for rid, (_, d) in records["paper"].items()}
    groups = {rid: d for rid, (_, d) in records["group"].items()}
    methods = {rid: d for rid, (_, d) in records["method"].items()}

    rows = []
    for rid, (_, d) in sorted(records["dataset"].items()):
        code = d.get("cancer_type")
        tissue = d.get("tissue")
        paper = papers.get(d.get("source_paper"), {})
        group = groups.get(d.get("lab"), {})
        method = methods.get(d.get("pipeline_ref"), {})
        rows.append(
            {
                "id": rid,
                "title": d.get("title", ""),
                "cancer_type": code or "",
                "cancer_type_name": (
                    oncotree.get(code, {}).get("name") if oncotree and code else ""
                )
                or "",
                "cancer_type_ncit": d.get("cancer_type_ncit", ""),
                "tissue": tissue or "",
                "tissue_label": (
                    uberon.get(tissue, {}).get("label") if uberon and tissue else ""
                )
                or "",
                "modality": d.get("modality", ""),
                "platform": d.get("platform", ""),
                "sequencer": d.get("sequencer", ""),
                "n_samples": d.get("n_samples", ""),
                "n_patients": d.get("n_patients", ""),
                "accession": ";".join(d.get("accession", []) or []),
                "access": d.get("access", ""),
                "curation_status": d.get("curation_status", ""),
                "last_verified": d.get("last_verified", ""),
                "deposition_year": d.get("deposition_year", ""),
                "source_paper": d.get("source_paper", ""),
                "paper_doi": paper.get("doi", ""),
                "paper_year": paper.get("year", ""),
                "lab": d.get("lab", ""),
                "lab_name": group.get("name", ""),
                "pipeline_ref": d.get("pipeline_ref", ""),
                "method_name": method.get("name", ""),
                "reuse_notes": " ".join((d.get("reuse_notes") or "").split()),
            }
        )
    return rows


def build_graph(records):
    """Return {nodes, edges} for the dataset<->paper/method/group graph."""
    nodes, edges = [], []

    def label(nt, d):
        return d.get("title") or d.get("name") or d.get("id")

    for nt in validate.NODE_TYPES:
        for rid, (_, d) in sorted(records[nt].items()):
            nodes.append({"id": rid, "type": nt, "label": label(nt, d)})

    dataset_ids = set(records["dataset"])
    paper_ids = set(records["paper"])
    group_ids = set(records["group"])
    method_ids = set(records["method"])

    for rid, (_, d) in sorted(records["dataset"].items()):
        for field, universe, rel in (
            ("source_paper", paper_ids, "described_in"),
            ("lab", group_ids, "produced_by"),
            ("pipeline_ref", method_ids, "processed_with"),
        ):
            ref = d.get(field)
            if ref and ref in universe:
                edges.append({"source": rid, "target": ref, "rel": rel})

    # Group -collaborates_with-> Group, derived from datasets sharing a paper.
    paper_to_groups: dict[str, set[str]] = {}
    for rid, (_, d) in records["dataset"].items():
        sp, lab = d.get("source_paper"), d.get("lab")
        if sp and lab and lab in group_ids:
            paper_to_groups.setdefault(sp, set()).add(lab)
    collab: set[tuple[str, str]] = set()
    for labs in paper_to_groups.values():
        labs = sorted(labs)
        for i in range(len(labs)):
            for j in range(i + 1, len(labs)):
                collab.add((labs[i], labs[j]))
    for a, b in sorted(collab):
        edges.append({"source": a, "target": b, "rel": "collaborates_with"})

    _ = dataset_ids  # (kept for symmetry/readability)
    return {"nodes": nodes, "edges": edges}


def _counter(rows, key):
    out: dict[str, int] = {}
    for r in rows:
        out[str(r[key])] = out.get(str(r[key]), 0) + 1
    return dict(sorted(out.items()))


def source_of(row):
    """Which source repository a dataset came from, from its accession/id.

    Mirrors detectSource() in the web app so the two stay in lockstep.
    """
    acc = (row.get("accession") or "").upper()
    rid = row.get("id", "").lower()
    if acc.startswith("GSE") or "-geo-" in rid:
        return "geo"
    if "ZENODO" in acc or "zenodo" in rid:
        return "zenodo"
    if acc.startswith("SYNAPSE:") or "-htan-" in rid:
        return "htan"
    if acc.startswith("S-BIAD") or "-biad-" in rid:
        return "biad"
    if acc.startswith("E-MTAB") or "-ae-" in rid:
        return "arrayexpress"
    if acc.startswith("CELLXGENE:") or "-cxg-" in rid:
        return "cellxgene"
    if acc.startswith("10X:") or "-tenx-" in rid or "-10x-" in rid:
        return "tenx"
    return "unknown"


def _counter_nonempty(rows, key):
    """Counter keyed by a field, skipping rows where it is blank."""
    out: dict[str, int] = {}
    for r in rows:
        v = r.get(key)
        if v == "" or v is None:
            continue
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items()))


def build_summary(rows, graph):
    verified = sum(1 for r in rows if r["curation_status"] == "verified")
    by_source: dict[str, int] = {}
    for r in rows:
        s = source_of(r)
        by_source[s] = by_source.get(s, 0) + 1
    return {
        "dataset_count": len(rows),
        "node_count": len(graph["nodes"]),
        "edge_count": len(graph["edges"]),
        "by_platform": _counter(rows, "platform"),
        "by_modality": _counter(rows, "modality"),
        "by_cancer_type": _counter(rows, "cancer_type"),
        "by_curation_status": _counter(rows, "curation_status"),
        "by_access": _counter(rows, "access"),
        "by_source": dict(sorted(by_source.items())),
        "by_deposition_year": _counter_nonempty(rows, "deposition_year"),
        "distinct_cancer_types": len({r["cancer_type"] for r in rows}),
        "verified_fraction": round(verified / len(rows), 3) if rows else 0.0,
    }


# Reusability signals (Tier 1): derived purely from record metadata (no data
# re-processing). Each is a "can I reuse this?" question a curator/researcher
# asks; the headline score is the fraction that are satisfied.
REUSABILITY_SIGNALS = [
    ("resolvable_accession", "Resolvable accession", lambda r: bool(r["accession"])),
    (
        "ontology_coded",
        "OncoTree + UBERON coded",
        lambda r: bool(r["cancer_type"]) and bool(r["tissue"]),
    ),
    ("ncit_cross_map", "NCIt cross-map", lambda r: bool(r["cancer_type_ncit"])),
    (
        "sample_counts",
        "Sample/patient counts",
        lambda r: r["n_samples"] != "" or r["n_patients"] != "",
    ),
    ("linked_paper", "Linked source paper", lambda r: bool(r["source_paper"])),
    (
        "curator_reviewed",
        "Curator-reviewed",
        lambda r: r["curation_status"] in ("human_reviewed", "verified"),
    ),
    ("verified", "Verified", lambda r: r["curation_status"] == "verified"),
]


def reusability(row):
    """Return {score, signals} summarizing metadata reusability for one dataset."""
    signals = {key: bool(fn(row)) for key, _label, fn in REUSABILITY_SIGNALS}
    met = sum(signals.values())
    return {
        "score": round(100 * met / len(REUSABILITY_SIGNALS)),
        "met": met,
        "total": len(REUSABILITY_SIGNALS),
        "signals": [
            {"key": key, "label": label, "ok": signals[key]}
            for key, label, _fn in REUSABILITY_SIGNALS
        ],
    }


def _citation_meta() -> tuple[str, str]:
    """Single source of truth for catalog version + release date: CITATION.cff.

    The release date (not the wall clock) is used for ``generated_at`` so the
    compiled payload stays byte-identical between runs - required for the
    reproducible Zenodo snapshot.
    """
    try:
        import yaml

        meta = yaml.safe_load((validate.ROOT / "CITATION.cff").read_text())
        version = str(meta.get("version", "")) or "unknown"
        released = str(meta.get("date-released", "")) or "unknown"
        return version, released
    except Exception:
        return "unknown", "unknown"


def build_site(rows, summary):
    """Denormalized payload for the static view: facets + full dataset list."""
    version, generated_at = _citation_meta()
    datasets = [{**r, "reusability": reusability(r)} for r in rows]
    return {
        "generated_at": generated_at,
        "version": version,
        "counts": {
            "datasets": summary["dataset_count"],
            "cancer_types": summary["distinct_cancer_types"],
        },
        "facets": {
            "modality": list(summary["by_modality"]),
            "platform": list(summary["by_platform"]),
            "cancer_type": list(summary["by_cancer_type"]),
            "access": list(summary["by_access"]),
            "curation_status": list(summary["by_curation_status"]),
        },
        "datasets": datasets,
    }


def _write_json(path: Path, obj) -> None:
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    )


def _write_csv(path: Path, rows) -> None:
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=DATASET_COLUMNS)
        w.writeheader()
        w.writerows(rows)


def _write_parquet(path: Path, rows) -> bool:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ModuleNotFoundError:
        return False
    cols = {c: [r[c] if r[c] != "" else None for r in rows] for c in DATASET_COLUMNS}
    pq.write_table(pa.table(cols), path)
    return True


def main() -> int:
    records = {
        nt: validate.load_records(sub) for nt, (sub, _) in validate.NODE_TYPES.items()
    }
    oncotree = validate.load_oncotree()
    uberon = validate.load_uberon()

    rows = build_rows(records, oncotree, uberon)
    graph = build_graph(records)
    summary = build_summary(rows, graph)
    site = build_site(rows, summary)

    DIST.mkdir(parents=True, exist_ok=True)
    _write_csv(DIST / "datasets.csv", rows)
    _write_json(DIST / "graph.json", graph)
    _write_json(DIST / "site.json", site)
    _write_json(DIST / "summary.json", summary)
    parquet = _write_parquet(DIST / "datasets.parquet", rows)

    rel = DIST.relative_to(validate.ROOT)
    print(f"Compiled {summary['dataset_count']} datasets -> {rel}/")
    print(
        f"  datasets.csv ({len(DATASET_COLUMNS)} cols), graph.json "
        f"({summary['node_count']} nodes / {summary['edge_count']} edges), "
        f"site.json, summary.json"
    )
    print(
        f"  datasets.parquet: {'written' if parquet else 'skipped (pyarrow not installed)'}"
    )
    print(
        f"  cancer types: {summary['distinct_cancer_types']} | "
        f"verified: {summary['verified_fraction']:.0%}"
    )
    runlog.log(
        "compile",
        datasets=summary["dataset_count"],
        cancer_types=summary["distinct_cancer_types"],
        verified_fraction=round(summary["verified_fraction"], 3),
        parquet=bool(parquet),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
