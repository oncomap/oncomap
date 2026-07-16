#!/usr/bin/env python3
"""Harvest human tumour spatial studies from ArrayExpress / EBI BioStudies.

A second source alongside GEO. ArrayExpress (now hosted in EBI BioStudies) holds
many European spatial studies deposited under E-MTAB accessions that never reach
GEO. This reuses the GEO harvester's platform detector, conservative disease
classifier and model/methods exclude filter, so records are drafted on the same
integrity bar:

  - only native E-MTAB accessions (E-GEOD-* mirrors of GEO are skipped, since
    those studies are reachable via their GSE and would double-count),
  - study Organism attribute must be Homo sapiens,
  - a spatial platform keyword must appear in the title/description,
  - a distinctive disease term must classify the cancer type, and
  - model-system / methods / benchmark studies are dropped.

Every record lands at curation_status machine_draft, pointing at the resolvable
E-MTAB accession, for later human promotion.

Usage:
  uv run python build/harvest_arrayexpress.py --dry-run
  uv run python build/harvest_arrayexpress.py --limit 40
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

import deposition  # sibling; repository deposition-year resolver
import harvest_geo as g  # reuse EXCLUDE, CLASSIFY, detect_platform, write_draft
import validate

try:
    import certifi

    _SSL = ssl.create_default_context(cafile=certifi.where())
except ModuleNotFoundError:
    _SSL = None

SEARCH = "https://www.ebi.ac.uk/biostudies/api/v1/search"
STUDY = "https://www.ebi.ac.uk/biostudies/api/v1/studies"
UA = {"User-Agent": "OncoMap-arrayexpress-harvester/1.0 (+https://oncomap.org)"}
ROOT = Path(__file__).resolve().parent.parent
DATASETS = ROOT / "records" / "datasets"
THROTTLE = 0.15

# Require an explicit malignancy term. The BioStudies search is loose and the
# shared classifier keys on organ words (endometrium, mantle) that also appear in
# normal-tissue atlases/references; this gate drops those false positives.
MALIGNANT = re.compile(
    r"cancer|carcinoma|tumou?r|malignan|neoplas|sarcoma|lymphoma|melanoma|"
    r"leukemi|myeloma|glioma|glioblastoma|blastoma|adenocarcinoma|metasta",
    re.I,
)

QUERIES = [
    "Visium cancer",
    "Visium carcinoma",
    "Visium tumour",
    "Xenium cancer",
    "Xenium carcinoma",
    "Xenium tumour",
    "CosMx cancer",
    "spatial transcriptomics carcinoma",
    "spatial transcriptomics tumour",
    "imaging mass cytometry cancer",
    "CODEX multiplexed tumour",
    "spatial proteomics carcinoma",
]


def _get(url: str) -> dict:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(
                req, timeout=45, context=_SSL
            ) as r:  # noqa: S310
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if attempt == 2:
                return {}
            time.sleep(1.0 + attempt)
    return {}


def existing_accessions() -> set[str]:
    have = set()
    for f in DATASETS.glob("*.yaml"):
        have |= set(re.findall(r"E-MTAB-\d+", f.read_text()))
    return have


def search_emtab(query: str, pages: int = 2, page_size: int = 100) -> list[str]:
    accs: list[str] = []
    for page in range(1, pages + 1):
        q = urllib.parse.urlencode(
            {
                "query": query,
                "collection": "arrayexpress",
                "pageSize": page_size,
                "page": page,
            }
        )
        hits = _get(f"{SEARCH}?{q}").get("hits", [])
        if not hits:
            break
        for h in hits:
            acc = h.get("accession", "")
            if acc.startswith("E-MTAB-"):
                accs.append(acc)
        time.sleep(THROTTLE)
    return accs


def study_attrs(acc: str) -> dict:
    d = _get(f"{STUDY}/{acc}")
    sec = d.get("section", {}) if isinstance(d, dict) else {}
    # Merge top-level study attributes (ReleaseDate lives here) with section ones.
    attrs = {
        a.get("name"): a.get("value")
        for a in (d.get("attributes", []) or []) + (sec.get("attributes", []) or [])
        if a.get("name")
    }
    if not attrs.get("Title") and d.get("title"):
        attrs["Title"] = d["title"]
    return attrs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--pages", type=int, default=2, help="search pages per query")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    oncotree = validate.load_oncotree()
    uberon = set(validate.load_uberon())
    have = existing_accessions()

    # gather candidate E-MTAB accessions across queries, deduped
    candidates: list[str] = []
    seen_acc: set[str] = set()
    for query in QUERIES:
        for acc in search_emtab(query, args.pages):
            if acc not in seen_acc and acc not in have:
                seen_acc.add(acc)
                candidates.append(acc)
    print(f"  {len(candidates)} unique new E-MTAB candidate(s) to inspect")

    drafted = 0
    per_type: dict[str, int] = {}
    for acc in candidates:
        attrs = study_attrs(acc)
        time.sleep(THROTTLE)
        if "homo sapiens" not in (attrs.get("Organism", "") or "").lower():
            continue
        title = (attrs.get("Title") or "").strip()
        desc = (attrs.get("Description") or "").strip()
        blob = f"{title} {desc}"
        if g.EXCLUDE.search(blob):
            continue
        if not MALIGNANT.search(blob):
            continue  # drop normal-tissue atlases/references
        plat = g.detect_platform(blob)
        if not plat or not g.confirm_platform(plat, blob):
            continue
        # Classify on the TITLE only: tumour studies name the cancer in the title,
        # whereas normal-tissue atlases (e.g. "Tonsil Atlas") merely mention a
        # disease in the description. This drops those normal-tissue mislabels.
        code = tissue = None
        for rx, c, t in g.CLASSIFY:
            if rx.search(title):
                code, tissue = c, t
                break
        if not code or code not in oncotree or tissue not in uberon:
            continue
        note = (
            "Machine-drafted by the ArrayExpress/BioStudies harvester. E-MTAB "
            "accession; study Organism attribute is Homo sapiens. Platform "
            f"detected as {plat} and cancer_type classified as {code} from a "
            "distinctive disease term in the study title/description. Confirm the "
            "spatial-only sample count, tissue detail and histology, and link the "
            "source paper before promoting past machine_draft."
        )
        x = {
            "accession": acc,
            "title": title,
            "n_samples": None,
            "deposition_year": deposition.year_from_biostudies_attrs(attrs),
        }
        rid = g.write_draft(code, tissue, plat, x, note, args.dry_run, source="ae")
        if rid:
            per_type[code] = per_type.get(code, 0) + 1
            drafted += 1
            if args.limit and drafted >= args.limit:
                break

    verb = "would draft" if args.dry_run else "drafted"
    print(f"\nArrayExpress harvester {verb} {drafted} new record(s).")
    if per_type:
        print(
            "  by type: " + ", ".join(f"{k}+{v}" for k, v in sorted(per_type.items()))
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
