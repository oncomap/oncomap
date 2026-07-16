#!/usr/bin/env python3
"""Resolve a dataset's repository deposition/release YEAR from its accession.

Powers the growth-over-time stats: the catalog stores no per-dataset deposition
date, but every source registry exposes one. This dispatches by accession scheme
to the registry API and extracts a four-digit year:

  - GEO   (GSE...)      NCBI esearch (gds) -> esummary PDAT (release date)
  - Zenodo DOI          Zenodo record API -> metadata.publication_date
  - S-BIAD / E-MTAB     EBI BioStudies study -> ReleaseDate attribute
  - Synapse / CELLxGENE / 10X   best-effort, else None (no reliable public date)

Network-dependent, so it is NOT part of offline CI. Used by
build/backfill_deposition_year.py (existing records) and by the harvesters
(new drafts, from the response they already fetch). Set NCBI_API_KEY to raise the
E-utilities rate limit.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import time
import urllib.parse
import urllib.request

try:
    import certifi

    _SSL = ssl.create_default_context(cafile=certifi.where())
except ModuleNotFoundError:
    _SSL = None

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
ZENODO = "https://zenodo.org/api/records"
BIOSTUDIES = "https://www.ebi.ac.uk/biostudies/api/v1/studies"
API_KEY = os.environ.get("NCBI_API_KEY", "")
THROTTLE = 0.12 if API_KEY else 0.34
UA = {
    "User-Agent": "OncoMap-deposition/1.0 (+https://github.com/oncomap/oncomap)"
}

_YEAR = re.compile(r"(19|20)\d{2}")


def year_from_text(value: object) -> int | None:
    """First plausible four-digit year (1990-2099) in a date-ish string."""
    if not value:
        return None
    for m in _YEAR.finditer(str(value)):
        y = int(m.group(0))
        if 1990 <= y <= 2099:
            return y
    return None


def _get(url: str) -> dict:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45, context=_SSL) as r:  # noqa: S310
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if attempt == 2:
                return {}
            time.sleep(1.0 + attempt)
    return {}


def classify(acc: str) -> str:
    a = acc.strip().upper()
    if a.startswith(("GSE", "GDS")):
        return "geo"
    if a.startswith(("E-MTAB-", "E-GEOD-", "E-PROT-")):
        return "biostudies"
    if a.startswith("S-BIAD"):
        return "biostudies"
    if a.startswith("SYNAPSE:"):
        return "synapse"
    if a.startswith("CELLXGENE:"):
        return "cellxgene"
    if a.startswith("10X:"):
        return "tenx"
    if a.startswith("10.") and "zenodo" in acc.lower():
        return "zenodo"
    if a.startswith("10."):
        return "doi"
    return "other"


# ---- per-source extractors (parse a response already in hand) --------------


def year_from_geo_summary(row: dict) -> int | None:
    """GEO esummary row -> release year. Prefers PDAT, else any date-ish value."""
    if not isinstance(row, dict):
        return None
    for key in ("PDAT", "pdat", "releaseDate", "GDSPubDate"):
        y = year_from_text(row.get(key))
        if y:
            return y
    # fall back to scanning date-looking string values
    for v in row.values():
        if isinstance(v, str) and re.search(r"\d{4}[/-]\d{2}", v):
            y = year_from_text(v)
            if y:
                return y
    return None


def year_from_zenodo_record(rec: dict) -> int | None:
    md = rec.get("metadata", {}) if isinstance(rec, dict) else {}
    return year_from_text(md.get("publication_date")) or year_from_text(
        rec.get("created")
    )


def year_from_biostudies_attrs(attrs: dict) -> int | None:
    """attrs is a name->value map (case-insensitive) from a BioStudies study."""
    for name, value in attrs.items():
        if name.lower() in ("releasedate", "release date"):
            y = year_from_text(value)
            if y:
                return y
    return None


# ---- accession -> year (fetches the registry) ------------------------------


def _geo_year(acc: str) -> int | None:
    q = {"db": "gds", "term": f"{acc}[ACCN]", "retmode": "json", "retmax": "1"}
    if API_KEY:
        q["api_key"] = API_KEY
    hits = _get(f"{ESEARCH}?{urllib.parse.urlencode(q)}")
    ids = hits.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return None
    time.sleep(THROTTLE)
    s = {"db": "gds", "id": ids[0], "retmode": "json"}
    if API_KEY:
        s["api_key"] = API_KEY
    data = _get(f"{ESUMMARY}?{urllib.parse.urlencode(s)}")
    row = data.get("result", {}).get(ids[0], {})
    return year_from_geo_summary(row)


def _zenodo_year(acc: str) -> int | None:
    m = re.search(r"zenodo\.(\d+)", acc)
    if not m:
        return None
    return year_from_zenodo_record(_get(f"{ZENODO}/{m.group(1)}"))


def _biostudies_year(acc: str) -> int | None:
    d = _get(f"{BIOSTUDIES}/{acc}")
    if not isinstance(d, dict):
        return None
    # ReleaseDate lives in the study's TOP-LEVEL attributes (not section.attributes).
    sec = d.get("section", {}) or {}
    attrs = {
        a.get("name", ""): a.get("value", "")
        for a in (d.get("attributes", []) or []) + (sec.get("attributes", []) or [])
    }
    return year_from_biostudies_attrs(attrs)


def resolve_deposition_year(acc: str) -> int | None:
    """Best-effort deposition/release year for one accession (network call)."""
    kind = classify(acc)
    try:
        if kind == "geo":
            return _geo_year(acc)
        if kind == "zenodo":
            return _zenodo_year(acc)
        if kind == "biostudies":
            return _biostudies_year(acc)
    except Exception:
        return None
    return None  # synapse / cellxgene / tenx / doi / other: no reliable public date
