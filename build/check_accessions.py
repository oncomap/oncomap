#!/usr/bin/env python3
"""Check that every dataset accession still resolves.

Turns the curation trust gate from structural into real: validate.py enforces
that a `verified` record HAS an accession; this confirms the accession actually
resolves at its source registry, catching link rot (SPEC 7 metadata-rot guard).

Resolution by scheme:
  - GEO   (GSE...)      NCBI E-utilities esearch on the gds database
  - SRA   (SRP/SRR...)  NCBI E-utilities esearch on the sra database
  - BioProject (PRJNA)  NCBI E-utilities esearch on the bioproject database
  - DOI   (10.x/...)    doi.org resolution; Zenodo DOIs via the record API
                        (doi.org redirects Zenodo DOIs to a /doi/ landing path
                        that 404s even for live records)
  - Synapse (SYNAPSE:)  Synapse entity API: a live entity is 200 or 403
                        (private-by-default, auth-gated), a missing one is 404
  - other              best-effort HTTP GET

Network-dependent, so this is NOT part of the offline validate CI; it runs on a
schedule (freshness workflow) and locally before promoting a record to
`verified`. Set NCBI_API_KEY to raise the E-utilities rate limit.

Usage:
  uv run python build/check_accessions.py                 # all datasets
  uv run python build/check_accessions.py --status verified  # only verified
  uv run python build/check_accessions.py --json report.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import runlog  # sibling; structured run logging
import validate  # sibling module; reuse record loaders

try:
    import certifi

    _SSL = ssl.create_default_context(cafile=certifi.where())
except ModuleNotFoundError:
    _SSL = None

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
API_KEY = os.environ.get("NCBI_API_KEY", "")
THROTTLE = 0.12 if API_KEY else 0.34  # respect ~10/s with key, ~3/s without
UA = {
    "User-Agent": "OncoMap-accession-check/1.0 (+https://github.com/oncomap/oncomap)"
}


def classify(acc: str) -> str:
    a = acc.strip()
    if a.upper().startswith("GSE") or a.upper().startswith("GDS"):
        return "geo"
    if a.upper().startswith(("SRP", "SRR", "SRX", "SRS")):
        return "sra"
    if a.upper().startswith("PRJNA"):
        return "bioproject"
    if a.upper().startswith(("E-MTAB-", "E-GEOD-", "E-PROT-")):
        return "arrayexpress"
    if a.upper().startswith("SYNAPSE:"):
        return "synapse"
    if a.upper().startswith("CELLXGENE:"):
        return "cellxgene"
    if a.upper().startswith("10X:"):
        return "tenx"
    if a.startswith("10.") and "/" in a:
        return "doi"
    return "other"


def _eutils_hit(db: str, term: str) -> bool:
    q = {"db": db, "term": term, "retmode": "json", "retmax": "1"}
    if API_KEY:
        q["api_key"] = API_KEY
    url = f"{EUTILS}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45, context=_SSL) as resp:  # noqa: S310
        data = json.loads(resp.read().decode("utf-8"))
    return bool(data.get("esearchresult", {}).get("idlist"))


def _http_alive(url: str) -> bool:
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, headers=UA, method=method)
            with urllib.request.urlopen(
                req, timeout=45, context=_SSL
            ) as resp:  # noqa: S310
                return 200 <= resp.status < 400
        except urllib.error.HTTPError as e:
            if e.code in (403, 405) and method == "HEAD":
                continue  # some hosts refuse HEAD; try GET
            return False
        except Exception:
            if method == "GET":
                return False
    return False


def _synapse_alive(syn: str) -> bool:
    # Synapse entities are private-by-default: a live one returns 200 (public) or
    # 403 (exists but auth-gated); only a missing entity returns 404. So existence
    # -- not readability -- is what we assert here.
    url = f"https://repo-prod.prod.sagebase.org/repo/v1/entity/{syn}"
    try:
        req = urllib.request.Request(url, headers=UA, method="GET")
        with urllib.request.urlopen(
            req, timeout=45, context=_SSL
        ) as resp:  # noqa: S310
            return resp.status in (200, 403)
    except urllib.error.HTTPError as e:
        return e.code == 403
    except Exception:
        return False


def _doi_alive(acc: str) -> bool:
    # doi.org redirects a Zenodo DOI to a /doi/ landing route that 404s even when
    # the deposit is live, so resolve those through the record API instead.
    m = re.search(r"zenodo\.(\d+)", acc)
    if m:
        return _http_alive(f"https://zenodo.org/api/records/{m.group(1)}")
    return _http_alive(f"https://doi.org/{acc}")


def check_one(acc: str) -> tuple[bool, str]:
    """Return (alive, detail) for a single accession."""
    kind = classify(acc)
    try:
        if kind == "geo":
            return _eutils_hit("gds", f"{acc}[ACCN]"), "geo"
        if kind == "sra":
            return _eutils_hit("sra", f"{acc}[ACCN]"), "sra"
        if kind == "bioproject":
            return _eutils_hit("bioproject", f"{acc}[Project Accession]"), "bioproject"
        if kind == "doi":
            return _doi_alive(acc), "doi"
        if kind == "synapse":
            return _synapse_alive(acc.split(":", 1)[1]), "synapse"
        if kind == "arrayexpress":
            return (
                _http_alive(f"https://www.ebi.ac.uk/biostudies/studies/{acc}"),
                "arrayexpress",
            )
        if kind == "cellxgene":
            cid = acc.split(":", 1)[1]
            return (
                _http_alive(f"https://cellxgene.cziscience.com/collections/{cid}"),
                "cellxgene",
            )
        if kind == "tenx":
            slug = acc.split(":", 1)[1]
            return _http_alive(f"https://www.10xgenomics.com/datasets/{slug}"), "tenx"
        return _http_alive(acc if acc.startswith("http") else f"https://{acc}"), "other"
    except Exception as e:  # network error, not a dead link per se
        return False, f"{kind}:error:{type(e).__name__}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--status", help="only check datasets with this curation_status")
    ap.add_argument("--json", metavar="PATH", help="write a JSON report to PATH")
    args = ap.parse_args(argv)

    datasets = validate.load_records("datasets")
    results = []
    dead = 0
    checked = 0

    for rid, (_, d) in sorted(datasets.items()):
        if args.status and d.get("curation_status") != args.status:
            continue
        for acc in d.get("accession", []) or []:
            alive, detail = check_one(acc)
            checked += 1
            if not alive:
                dead += 1
            results.append(
                {"dataset": rid, "accession": acc, "kind": detail, "alive": alive}
            )
            mark = "ok " if alive else "DEAD"
            print(f"  [{mark}] {acc:<28} {detail:<12} {rid}")
            time.sleep(THROTTLE)

    scope = f"status={args.status}" if args.status else "all datasets"
    print(
        f"\nChecked {checked} accession(s) across {scope}: {dead} dead, {checked - dead} alive."
    )

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2) + "\n")
        print(f"Report written to {args.json}")

    runlog.log(
        "check_accessions",
        status="fail" if dead else "ok",
        checked=checked,
        dead=dead,
        scope=args.status or "all",
    )
    return 1 if dead else 0


if __name__ == "__main__":
    raise SystemExit(main())
