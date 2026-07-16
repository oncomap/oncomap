#!/usr/bin/env python3
"""Harvest human tumour spatial datasets deposited on Zenodo.

A third source. Zenodo hosts primary spatial data (Seurat / SpatialExperiment
objects, Loupe files, processed matrices) behind citable DOIs that never enter
GEO or ArrayExpress. Its metadata is unstructured (no organism or assay fields),
so this leans harder on the shared guards and adds an organism exclude:

  - the platform must be detectable from the title/description,
  - the cancer type must be named in the TITLE (precision over recall),
  - a malignancy term must be present, and
  - model-system / methods / benchmark records and any non-human organism marker
    (mouse, rat, zebrafish, axolotl, porcine, canine, C57BL, ...) are dropped.

The Zenodo DOI is the accession (resolvable via doi.org, already handled by
check_accessions.py). Records land at curation_status machine_draft.

Usage:
  uv run python build/harvest_zenodo.py --dry-run
  uv run python build/harvest_zenodo.py --pages 6
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
import harvest_geo as g
import validate

try:
    import certifi

    _SSL = ssl.create_default_context(cafile=certifi.where())
except ModuleNotFoundError:
    _SSL = None

API = "https://zenodo.org/api/records"
UA = {"User-Agent": "OncoMap-zenodo-harvester/1.0 (+https://oncomap.org)"}
ROOT = Path(__file__).resolve().parent.parent
DATASETS = ROOT / "records" / "datasets"
THROTTLE = 0.4

QUERY = '(visium OR xenium OR cosmx OR "stereo-seq" OR merfish OR codex OR cycif OR "imaging mass cytometry" OR mibi OR "multiplexed immunofluorescence") AND (cancer OR carcinoma OR tumor OR tumour OR sarcoma OR lymphoma OR melanoma OR glioblastoma)'

MALIGNANT = re.compile(
    r"cancer|carcinoma|tumou?r|malignan|neoplas|sarcoma|lymphoma|melanoma|"
    r"leukemi|myeloma|glioma|glioblastoma|blastoma|adenocarcinoma|metasta",
    re.I,
)
# Non-human organism markers; Zenodo has no organism field so screen the text.
NONHUMAN = re.compile(
    r"\bmouse\b|\bmurine\b|\bmice\b|\brat\b|zebrafish|axolotl|porcine|canine|"
    r"drosophila|\bC57BL\b|\bBALB\b|macaque|\bovine\b|xenograft",
    re.I,
)

TAG = re.compile(r"<[^>]+>")
# Title-level reject: secondary/derived artifacts and non-spatial primary
# modalities. Zenodo often deposits per-study byproducts under their own DOIs
# (gene counts, intermediate files, code, annotations) and scRNA/Chromium data
# whose description merely mentions the paired spatial assay. Keep only titles
# that denote a primary spatial dataset.
ARTIFACT = re.compile(
    r"supplement|intermediate file|derived |source data|gene count|factor analysis|"
    r"computational output|analysis output|\boutput\b|\bcode\b|loupe file|"
    r"image data|\bh&e\b|\bh&es\b|\bexample\b|annotation|scrna|"
    r"single[- ]cell rna|\bchromium\b|snrna|bulk rna|metadata",
    re.I,
)


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
            time.sleep(1.5 + attempt)
    return {}


def existing_dois() -> set[str]:
    have = set()
    for f in DATASETS.glob("*.yaml"):
        have |= {d.lower() for d in re.findall(r"10\.5281/zenodo\.\d+", f.read_text())}
    return have


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--pages", type=int, default=12)
    ap.add_argument("--size", type=int, default=25)  # Zenodo caps unauth size at 25
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    oncotree = validate.load_oncotree()
    uberon = set(validate.load_uberon())
    have = existing_dois()

    drafted = 0
    per_type: dict[str, int] = {}
    seen: set[str] = set()
    inspected = 0
    for page in range(1, args.pages + 1):
        q = urllib.parse.urlencode(
            {
                "q": QUERY,
                "size": args.size,
                "page": page,
                "type": "dataset",
                "sort": "mostrecent",
            }
        )
        hits = _get(f"{API}?{q}").get("hits", {}).get("hits", [])
        if not hits:
            break
        for r in hits:
            inspected += 1
            doi = (r.get("doi") or "").strip()
            m = re.search(r"zenodo\.(\d+)", doi)
            if not m or doi.lower() in have or doi.lower() in seen:
                continue
            md = r.get("metadata", {})
            title = (md.get("title") or "").strip()
            desc = TAG.sub(" ", md.get("description") or "")
            blob = f"{title} {desc}"
            if NONHUMAN.search(blob) or g.EXCLUDE.search(blob):
                continue
            if ARTIFACT.search(title):
                continue  # secondary artifact or non-spatial modality
            if not MALIGNANT.search(blob):
                continue
            plat = g.detect_platform(blob)
            if not plat or not g.confirm_platform(plat, blob):
                continue
            code = tissue = None
            for rx, c, t in g.CLASSIFY:
                if rx.search(title):  # classify on title for precision
                    code, tissue = c, t
                    break
            if not code or code not in oncotree or tissue not in uberon:
                continue
            seen.add(doi.lower())
            # Zenodo record metadata may be public while its FILES are gated
            # (restricted / embargoed / closed). Map that to the catalog's
            # data-classification value so gated data is never advertised as open.
            access_right = (md.get("access_right") or "open").lower()
            access = "open" if access_right == "open" else "on_request"
            gated = (
                ""
                if access == "open"
                else (
                    f" NOTE: the Zenodo files are {access_right} (record metadata is "
                    "public but the data itself is gated at source); cataloged as a "
                    "pointer, access on_request."
                )
            )
            note = (
                "Machine-drafted by the Zenodo harvester. Citable DOI (resolvable "
                "via doi.org). Zenodo carries no organism/assay fields, so platform "
                f"was detected as {plat} and cancer_type classified as {code} from "
                "the record title/description, non-human organism markers were "
                "screened out, and the type term is required in the title. Confirm "
                "the sample count, tissue detail, histology and human provenance, "
                f"and link the source paper before promoting past machine_draft.{gated}"
            )
            x = {
                "accession": doi,
                "title": title,
                "n_samples": None,
                "slug": f"zenodo-{m.group(1)}",
                "deposition_year": deposition.year_from_zenodo_record(r),
            }
            rid = g.write_draft(
                code,
                tissue,
                plat,
                x,
                note,
                args.dry_run,
                source="zenodo",
                access=access,
            )
            if rid:
                per_type[code] = per_type.get(code, 0) + 1
                drafted += 1
                if args.limit and drafted >= args.limit:
                    break
        time.sleep(THROTTLE)
        if args.limit and drafted >= args.limit:
            break

    verb = "would draft" if args.dry_run else "drafted"
    print(f"\nInspected {inspected}. Zenodo harvester {verb} {drafted} new record(s).")
    if per_type:
        print(
            "  by type: " + ", ".join(f"{k}+{v}" for k, v in sorted(per_type.items()))
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
