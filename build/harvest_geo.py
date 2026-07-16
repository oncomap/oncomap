#!/usr/bin/env python3
"""Harvest human solid-tumour spatial-transcriptomics series from GEO.

Scales the manual curation loop into a repeatable sweep. For each cancer type in
a curated spec table, it runs an NCBI E-utilities search restricted to spatial
assays and Homo sapiens, reads the GEO-provided series title + summary, and
detects the spatial platform from that text. A candidate is drafted only when:

  - the record's GEO accession is new (not already in records/datasets/),
  - the series taxon is Homo sapiens,
  - a known spatial platform keyword appears in the GEO title/summary, and
  - at least one cancer keyword for the queried type appears in the title/summary
    (guards against studies that merely mention the tissue in passing).

Every drafted record carries curation_status: machine_draft. The platform,
cancer_type (OncoTree) and tissue (UBERON) are all membership-checked before a
file is written, so nothing that would fail validate.py is emitted. A human still
promotes each record to human_reviewed / verified later (confirm sample counts,
link the paper); this only removes the manual discovery + transcription step.

Usage:
  uv run python build/harvest_geo.py                 # draft all new candidates
  uv run python build/harvest_geo.py --limit 40      # stop after N new drafts
  uv run python build/harvest_geo.py --dry-run       # report, write nothing
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

import deposition  # sibling; repository deposition-year resolver
import validate  # sibling; reuse loaders + vocab

try:
    import certifi

    _SSL = ssl.create_default_context(cafile=certifi.where())
except ModuleNotFoundError:
    _SSL = None

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
API_KEY = os.environ.get("NCBI_API_KEY", "")
THROTTLE = 0.12 if API_KEY else 0.34
UA = {"User-Agent": "OncoMap-geo-harvester/1.0 (+https://oncomap.org)"}
ROOT = Path(__file__).resolve().parent.parent
DATASETS = ROOT / "records" / "datasets"

# Platform detection: ordered so the more specific label wins (Visium HD before
# Visium). Each entry is (platform_enum, compiled keyword regex over title+summary).
# Transcriptomics platforms first, then spatial-proteomics platforms.
PLATFORMS = [
    ("visium_hd", re.compile(r"visium\s*hd", re.I)),
    ("xenium", re.compile(r"\bxenium\b", re.I)),
    ("cosmx", re.compile(r"\bcosmx\b", re.I)),
    ("merscope", re.compile(r"\bmerscope\b", re.I)),
    ("merfish", re.compile(r"\bmerfish\b", re.I)),
    ("stereo_seq", re.compile(r"stereo[\s-]?seq", re.I)),
    ("slide_seq", re.compile(r"slide[\s-]?seq", re.I)),
    ("visium", re.compile(r"\bvisium\b", re.I)),
    # spatial proteomics (imaging)
    ("codex", re.compile(r"\bcodex\b|phenocycler|co-detection by indexing", re.I)),
    ("cycif", re.compile(r"\bt?-?cycif\b|cyclic immunofluoresc", re.I)),
    ("mibi", re.compile(r"\bmibi\b|multiplexed ion beam", re.I)),
    # bare "IMC" is too ambiguous (matches many acronyms); require the full name.
    ("imc", re.compile(r"imaging mass cytometry", re.I)),
    ("orion", re.compile(r"rarecyte orion|\borion\b", re.I)),
    ("geomx", re.compile(r"geomx|digital spatial profil", re.I)),
    ("mxif", re.compile(r"\bmxif\b|multiplex(ed)? immunofluoresc", re.I)),
    (
        "mihc",
        re.compile(
            r"\bm-?ihc\b|multiplex(ed)? ihc|multiplex(ed)? immunohistochem", re.I
        ),
    ),
]

# Every platform's modality, derived in one place. Proteomics platforms map to
# spatial_proteomics; everything else to spatial_transcriptomics. GeoMx can carry
# an RNA or protein panel; it defaults to proteomics and the draft note asks the
# curator to confirm the panel type.
PLATFORM_MODALITY = {
    "st_array": "spatial_transcriptomics",
    "visium": "spatial_transcriptomics",
    "visium_hd": "spatial_transcriptomics",
    "xenium": "spatial_transcriptomics",
    "merfish": "spatial_transcriptomics",
    "merscope": "spatial_transcriptomics",
    "cosmx": "spatial_transcriptomics",
    "slide_seq": "spatial_transcriptomics",
    "stereo_seq": "spatial_transcriptomics",
    "codex": "spatial_proteomics",
    "cycif": "spatial_proteomics",
    "mxif": "spatial_proteomics",
    "mihc": "spatial_proteomics",
    "mibi": "spatial_proteomics",
    "imc": "spatial_proteomics",
    "orion": "spatial_proteomics",
    "geomx": "spatial_proteomics",
}

# Proteomics-platform names (CODEX, IMC, MIBI, CyCIF) are ambiguous words that
# also appear in RNA-seq/scRNA studies. When a proteomics platform is detected,
# require the text to actually describe protein/antibody/imaging profiling; a
# transcriptomics platform never needs this confirmation.
PROTEOMICS_CONFIRM = re.compile(
    r"antibod|immunofluoresc|immunohistochem|mass cytometry|phenocycler|"
    r"proteom|multiplexed (protein|imag|immun|antibod)|highly multiplexed|"
    r"co-detection by indexing|marker panel|in situ protein",
    re.I,
)


def confirm_platform(plat: str, blob: str) -> bool:
    """True unless a proteomics platform lacks protein/imaging context."""
    if PLATFORM_MODALITY.get(plat) != "spatial_proteomics":
        return True
    return bool(PROTEOMICS_CONFIRM.search(blob))


# Curated cancer-type spec. Each: OncoTree code, UBERON tissue (must be in the
# frozen seed), the GEO search phrase, and a keyword regex confirming the study
# is really about that cancer. Codes/tissues are re-checked against the frozen
# vocabularies at runtime, so a typo is skipped rather than written.
CANCERS = [
    ("BRCA", "UBERON:0000310", "breast cancer", r"breast"),
    ("LUAD", "UBERON:0002048", "lung adenocarcinoma", r"lung|adenocarcinoma"),
    ("LUSC", "UBERON:0002048", "lung squamous cell carcinoma", r"lung|squamous"),
    ("NSCLC", "UBERON:0002048", "non-small cell lung cancer", r"lung|nsclc"),
    ("SCLC", "UBERON:0002048", "small cell lung cancer", r"lung|small cell"),
    (
        "COADREAD",
        "UBERON:0001155",
        "colorectal cancer",
        r"colorectal|colon|rectal|colonic",
    ),
    ("PAAD", "UBERON:0001264", "pancreatic ductal adenocarcinoma", r"pancrea"),
    ("STAD", "UBERON:0000945", "gastric cancer", r"gastric|stomach"),
    ("HCC", "UBERON:0002107", "hepatocellular carcinoma", r"hepatocellular|liver|hcc"),
    ("CHOL", "UBERON:0002394", "cholangiocarcinoma", r"cholangi|biliary|bile duct"),
    (
        "ESCC",
        "UBERON:0001043",
        "esophageal squamous cell carcinoma",
        r"esophag|oesophag",
    ),
    ("SKCM", "UBERON:0002097", "melanoma", r"melanoma"),
    ("GB", "UBERON:0000955", "glioblastoma", r"glioblastoma|glioma|gbm"),
    ("LGG", "UBERON:0000955", "low grade glioma", r"glioma"),
    ("PRAD", "UBERON:0002367", "prostate cancer", r"prostate|prostatic"),
    ("CCRCC", "UBERON:0002113", "clear cell renal cell carcinoma", r"renal|kidney"),
    ("BLCA", "UBERON:0001255", "bladder cancer", r"bladder|urothelial"),
    (
        "HNSC",
        "UBERON:0000167",
        "head and neck squamous cell carcinoma",
        r"head and neck|oral|squamous",
    ),
    ("HGSOC", "UBERON:0000992", "ovarian cancer", r"ovarian|ovary"),
    ("UCEC", "UBERON:0000995", "endometrial cancer", r"endometrial|endometrium"),
    ("CESC", "UBERON:0000002", "cervical cancer", r"cervical|cervix"),
    ("THCA", "UBERON:0002046", "thyroid cancer", r"thyroid"),
    ("THPA", "UBERON:0002046", "papillary thyroid carcinoma", r"papillary thyroid"),
    ("DLBCLNOS", "UBERON:0000029", "diffuse large B-cell lymphoma", r"lymphoma"),
    ("PCM", "UBERON:0002371", "multiple myeloma", r"myeloma"),
    ("OS", "UBERON:0001474", "osteosarcoma", r"osteosarcoma"),
    ("ES", "UBERON:0001474", "Ewing sarcoma", r"ewing"),
    ("NPC", "UBERON:0001728", "nasopharyngeal carcinoma", r"nasopharyng"),
    ("MCC", "UBERON:0002097", "Merkel cell carcinoma", r"merkel"),
    (
        "CSCC",
        "UBERON:0002097",
        "cutaneous squamous cell carcinoma",
        r"cutaneous squamous|skin squamous",
    ),
    ("BCC", "UBERON:0002097", "basal cell carcinoma", r"basal cell"),
    ("ACC", "UBERON:0001235", "adrenocortical carcinoma", r"adrenocortical|adrenal"),
    ("GIST", "UBERON:0000945", "gastrointestinal stromal tumor", r"stromal tumor|gist"),
    ("PANET", "UBERON:0001264", "pancreatic neuroendocrine tumor", r"neuroendocrine"),
    ("CCOV", "UBERON:0000992", "ovarian clear cell carcinoma", r"clear cell|ovarian"),
    ("UCS", "UBERON:0000995", "uterine carcinosarcoma", r"carcinosarcoma|uterine"),
    (
        "PRCC",
        "UBERON:0002113",
        "papillary renal cell carcinoma",
        r"papillary renal|renal",
    ),
    (
        "CHRCC",
        "UBERON:0002113",
        "chromophobe renal cell carcinoma",
        r"chromophobe|renal",
    ),
    ("WT", "UBERON:0002113", "Wilms tumor", r"wilms|nephroblastoma"),
    ("FL", "UBERON:0000029", "follicular lymphoma", r"follicular lymphoma"),
    ("MCL", "UBERON:0000029", "mantle cell lymphoma", r"mantle cell"),
    ("BL", "UBERON:0000029", "Burkitt lymphoma", r"burkitt"),
    ("MZL", "UBERON:0000029", "marginal zone lymphoma", r"marginal zone"),
    ("CHL", "UBERON:0000029", "classical Hodgkin lymphoma", r"(?<!non.)hodgkin"),
    (
        "PCNSL",
        "UBERON:0000955",
        "central nervous system lymphoma",
        r"cns lymphoma|central nervous system lymphoma",
    ),
    ("SEM", "UBERON:0000473", "seminoma", r"seminoma|testicular"),
    ("PHC", "UBERON:0001235", "pheochromocytoma", r"pheochromocytoma"),
    ("ESCA", "UBERON:0001043", "esophageal adenocarcinoma", r"esophag|oesophag"),
    ("MBL", "UBERON:0000955", "medulloblastoma", r"medulloblastoma"),
    ("EPM", "UBERON:0000955", "ependymoma", r"ependymoma"),
    ("MNG", "UBERON:0000955", "meningioma", r"meningioma"),
    ("READ", "UBERON:0001155", "rectal adenocarcinoma", r"rectal|rectum"),
    ("SARCNOS", "UBERON:0002384", "soft tissue sarcoma", r"sarcoma"),
    ("LMS", "UBERON:0002384", "leiomyosarcoma", r"leiomyosarcoma"),
    (
        "UPS",
        "UBERON:0002384",
        "undifferentiated pleomorphic sarcoma",
        r"pleomorphic sarcoma",
    ),
    ("DDLS", "UBERON:0002384", "dedifferentiated liposarcoma", r"liposarcoma"),
    ("SYNS", "UBERON:0002384", "synovial sarcoma", r"synovial sarcoma"),
    ("RMS", "UBERON:0002384", "rhabdomyosarcoma", r"rhabdomyosarcoma"),
    ("MFS", "UBERON:0002384", "myxofibrosarcoma", r"myxofibrosarcoma"),
    ("PLMESO", "UBERON:0000977", "malignant pleural mesothelioma", r"mesothelioma"),
    ("MESO", "UBERON:0000977", "mesothelioma", r"mesothelioma"),
    ("UM", "UBERON:0001768", "uveal melanoma", r"uveal"),
    ("THYM", "UBERON:0002370", "thymoma", r"thymoma|thymic"),
    ("THYC", "UBERON:0002370", "thymic carcinoma", r"thymic carcinoma"),
    ("GBC", "UBERON:0002110", "gallbladder cancer", r"gallbladder"),
    ("GBAD", "UBERON:0002110", "gallbladder adenocarcinoma", r"gallbladder"),
    ("PITAD", "UBERON:0000007", "pituitary adenoma", r"pituitary"),
]

# Negative filter: drop model-system, methods/tool and benchmark studies that are
# not primary human tumour tissue, so they never reach the catalog even as drafts.
EXCLUDE = re.compile(
    r"organoid|tumoroid|xenograft|\bPDX\b|\bGEMM\b|genetically engineered|mouse model|"
    r"murine|\bmice\b|\bmouse\b|cell line|in silico|benchmark|web application|"
    r"user-friendly|simulation|\bspatialGE\b|a platform for|imaging platform",
    re.I,
)

# Conservative disease classifier for the platform-driven sweep. Ordered; first
# match wins. Each entry maps a DISTINCTIVE disease term to a single OncoTree code
# and UBERON tissue. Ambiguous generics (renal NOS, lymphoma NOS, glioma NOS) are
# deliberately absent so those series are skipped rather than mislabelled. Two
# dominant-entity generalisations are allowed and flagged in the draft note:
# generic lung cancer -> NSCLC, generic ovarian cancer -> HGSOC.
CLASSIFY = [
    (r"small cell lung|\bsclc\b", "SCLC", "UBERON:0002048"),
    (r"lung squamous|squamous cell lung", "LUSC", "UBERON:0002048"),
    (r"lung adenocarcinoma", "LUAD", "UBERON:0002048"),
    (
        r"non[- ]small cell lung|\bnsclc\b|lung cancer|lung carcinoma|lung tumou?r",
        "NSCLC",
        "UBERON:0002048",
    ),
    (
        r"triple[- ]negative breast|breast cancer|breast carcinoma|breast tumou?r|mammary carcinoma",
        "BRCA",
        "UBERON:0000310",
    ),
    (
        r"colorectal|colon cancer|colon adenocarcinoma|colonic|rectal cancer|rectal adenocarcinoma",
        "COADREAD",
        "UBERON:0001155",
    ),
    (
        r"pancreatic ductal|pancreatic cancer|pancreatic adenocarcinoma|\bpdac\b",
        "PAAD",
        "UBERON:0001264",
    ),
    (
        r"gastric cancer|gastric adenocarcinoma|stomach cancer|stomach adenocarcinoma",
        "STAD",
        "UBERON:0000945",
    ),
    (r"hepatocellular|\bhcc\b|liver cancer", "HCC", "UBERON:0002107"),
    (
        r"cholangiocarcinoma|biliary tract cancer|bile duct cancer",
        "CHOL",
        "UBERON:0002394",
    ),
    (r"gallbladder", "GBAD", "UBERON:0002110"),
    (r"esophageal squamous|oesophageal squamous", "ESCC", "UBERON:0001043"),
    (r"esophageal adenocarcinoma|oesophageal adenocarcinoma", "ESCA", "UBERON:0001043"),
    (r"uveal melanoma", "UM", "UBERON:0001768"),
    (r"melanoma", "SKCM", "UBERON:0002097"),
    (r"glioblastoma|\bgbm\b", "GB", "UBERON:0000955"),
    (r"medulloblastoma", "MBL", "UBERON:0000955"),
    (r"ependymoma", "EPM", "UBERON:0000955"),
    (r"meningioma", "MNG", "UBERON:0000955"),
    (
        r"prostate cancer|prostate adenocarcinoma|prostatic adenocarcinoma",
        "PRAD",
        "UBERON:0002367",
    ),
    (r"clear cell renal", "CCRCC", "UBERON:0002113"),
    (r"papillary renal", "PRCC", "UBERON:0002113"),
    (r"chromophobe renal", "CHRCC", "UBERON:0002113"),
    (r"wilms|nephroblastoma", "WT", "UBERON:0002113"),
    (
        r"bladder cancer|urothelial carcinoma|urothelial cancer|muscle-invasive bladder",
        "BLCA",
        "UBERON:0001255",
    ),
    (
        r"head and neck squamous|\bhnscc\b|oral squamous|oral cavity squamous",
        "HNSC",
        "UBERON:0000167",
    ),
    (r"nasopharyngeal", "NPC", "UBERON:0001728"),
    (r"high[- ]grade serous|\bhgsoc\b", "HGSOC", "UBERON:0000992"),
    (r"ovarian clear cell", "CCOV", "UBERON:0000992"),
    (r"ovarian cancer|ovarian carcinoma|ovary cancer", "HGSOC", "UBERON:0000992"),
    (r"endometrial|endometrium|uterine corpus", "UCEC", "UBERON:0000995"),
    (r"cervical cancer|cervical carcinoma|cervical squamous", "CESC", "UBERON:0000002"),
    (r"merkel cell", "MCC", "UBERON:0002097"),
    (r"basal cell carcinoma", "BCC", "UBERON:0002097"),
    (r"cutaneous squamous", "CSCC", "UBERON:0002097"),
    (r"diffuse large b[- ]cell|\bdlbcl\b", "DLBCLNOS", "UBERON:0000029"),
    (r"follicular lymphoma", "FL", "UBERON:0000029"),
    (r"mantle cell lymphoma", "MCL", "UBERON:0000029"),
    (r"(?<!non.)hodgkin", "CHL", "UBERON:0000029"),
    (r"marginal zone lymphoma", "MZL", "UBERON:0000029"),
    (r"burkitt", "BL", "UBERON:0000029"),
    (r"multiple myeloma|plasma cell myeloma", "PCM", "UBERON:0002371"),
    (r"osteosarcoma", "OS", "UBERON:0001474"),
    (r"ewing", "ES", "UBERON:0001474"),
    (r"rhabdomyosarcoma", "RMS", "UBERON:0002384"),
    (r"leiomyosarcoma", "LMS", "UBERON:0002384"),
    (r"liposarcoma", "DDLS", "UBERON:0002384"),
    (r"synovial sarcoma", "SYNS", "UBERON:0002384"),
    (r"mesothelioma", "PLMESO", "UBERON:0000977"),
    (r"thymic carcinoma", "THYC", "UBERON:0002370"),
    (r"thymoma", "THYM", "UBERON:0002370"),
    (r"adrenocortical", "ACC", "UBERON:0001235"),
    (r"nasopharyng", "NPC", "UBERON:0001728"),
]
CLASSIFY = [(re.compile(rx, re.I), code, tis) for rx, code, tis in CLASSIFY]

# Platform-sweep queries: one broad human-cancer query per platform keyword.
# Transcriptomics only. GEO is a sequencing archive: imaging-based spatial
# PROTEOMICS data (CODEX/IMC/MIBI/CyCIF are images) live in image repositories
# (HTAN, BioImage Archive, IDR), not GEO. Verified 2026-07: every GEO hit on a
# proteomics keyword was the RNA companion deposit of a multi-omics study (or a
# model system), so proteomics is deliberately not swept here - only the
# esummary blob is visible to the sweep and cannot tell those apart. The
# detect_platform proteomics entries remain for the Zenodo/ArrayExpress
# harvesters, which resolve full-record assay context.
PLATFORM_QUERIES = [
    ("Visium", 220),
    ("Xenium", 90),
    ("CosMx", 45),
    ("Stereo-seq", 12),
    ("MERFISH", 15),
    ("Slide-seq", 6),
]

SPATIAL_TERMS = (
    "(Visium[All Fields] OR Xenium[All Fields] OR CosMx[All Fields] OR "
    '"Stereo-seq"[All Fields] OR MERFISH[All Fields] OR MERSCOPE[All Fields] OR '
    '"Slide-seq"[All Fields])'
)


def _get_json(url: str) -> dict:
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


def _key():
    return f"&api_key={API_KEY}" if API_KEY else ""


def existing_gses() -> set[str]:
    have = set()
    for f in DATASETS.glob("*.yaml"):
        have |= set(re.findall(r"GSE\d+", f.read_text()))
    return have


def esearch(term: str, retmax: int) -> list[str]:
    url = (
        f"{EUTILS}/esearch.fcgi?db=gds&term={urllib.parse.quote(term)}"
        f"&retmax={retmax}&sort=relevance&retmode=json{_key()}"
    )
    return _get_json(url).get("esearchresult", {}).get("idlist", [])


def esummary(ids: list[str]) -> dict:
    if not ids:
        return {}
    url = f"{EUTILS}/esummary.fcgi?db=gds&id={','.join(ids)}&retmode=json{_key()}"
    return _get_json(url).get("result", {})


def detect_platform(text: str) -> str | None:
    for plat, rx in PLATFORMS:
        if rx.search(text):
            return plat
    return None


def q(t: str) -> str:
    return '"' + t.replace('"', "").strip() + '"'


def write_draft(
    code, tissue, plat, x, note, dry, source="geo", access="open"
) -> str | None:
    """Write one machine_draft dataset from an esummary row; return rid or None.

    ``source`` is the provenance token embedded in the id (geo, ae, cxg, ...).
    ``access`` is the data-classification value (open / controlled / on_request);
    callers must pass on_request/controlled when the source's files are gated
    (e.g. a Zenodo deposit whose files are restricted or embargoed) so the
    catalog never advertises gated data as open.
    """
    acc = x.get("accession", "")
    plat_slug = plat.replace("_", "-")
    # id tail: a clean slug when the accession carries illegal chars (e.g. a DOI
    # with '/' and '.'); otherwise the accession itself (GSE / E-MTAB are clean).
    tail = x.get("slug") or acc.lower()
    rid = f"{plat_slug}-{code.lower()}-{source}-{tail}"
    path = DATASETS / f"{rid}.yaml"
    if path.exists():
        return None
    title = (x.get("title") or "").strip()
    n = x.get("n_samples")
    nline = f"n_samples: {n}\n" if isinstance(n, int) and n > 0 else ""
    dy = x.get("deposition_year")
    dyline = f"deposition_year: {dy}\n" if isinstance(dy, int) else ""
    modality = PLATFORM_MODALITY.get(plat, "spatial_transcriptomics")
    body = (
        f"id: {rid}\n"
        f"title: {q(title) if title else q(acc + ' spatial omics')}\n"
        f"cancer_type: {code}\n"
        f'tissue: "{tissue}"\n'
        f"modality: {modality}\n"
        f"platform: {plat}\n"
        f"{nline}"
        f"accession:\n  - {acc}\n"
        f"access: {access}\n"
        f"reuse_notes: >-\n  {note}\n"
        f"{dyline}"
        f"curation_status: machine_draft\n"
    )
    if dry:
        print(f"  [dry] {rid}  n={n}  {title[:50]}")
    else:
        path.write_text(body)
        print(f"  [+]   {rid}  n={n}  {title[:50]}")
    return rid


def run_platform_mode(args, oncotree, uberon, have) -> int:
    """Read every human cancer series per platform and classify conservatively."""
    seen: set[str] = set()
    drafted = 0
    per_type: dict[str, int] = {}
    valid_tissue = set(uberon)
    for plat_kw, retmax in PLATFORM_QUERIES:
        term = (
            f"{plat_kw}[All Fields] AND (cancer[All Fields] OR carcinoma[All Fields] "
            f"OR tumor[All Fields] OR tumour[All Fields] OR sarcoma[All Fields] OR "
            f'lymphoma[All Fields] OR melanoma[All Fields]) AND "Homo sapiens"[Organism] '
            f"AND gse[ETYP]"
        )
        ids = esearch(term, retmax)
        time.sleep(THROTTLE)
        for i in range(0, len(ids), 100):
            rows = esummary(ids[i : i + 100])
            for uid in rows.get("uids", []):
                x = rows[uid]
                acc = x.get("accession", "")
                if x.get("entrytype") != "GSE" or not acc.startswith("GSE"):
                    continue
                if acc in have or acc in seen:
                    continue
                if "homo sapiens" not in (x.get("taxon", "") or "").lower():
                    continue
                blob = f"{(x.get('title') or '')} {(x.get('summary') or '')}"
                if EXCLUDE.search(blob):
                    continue
                plat = detect_platform(blob)
                if not plat or not confirm_platform(plat, blob):
                    continue
                code = tissue = None
                for rx, c, t in CLASSIFY:
                    if rx.search(blob):
                        code, tissue = c, t
                        break
                if not code or code not in oncotree or tissue not in valid_tissue:
                    continue
                note = (
                    "Machine-drafted by the GEO platform sweep. Accession returned "
                    "live by NCBI E-utilities (organism Homo sapiens). Platform "
                    f"detected as {plat} and cancer_type classified as {code} from a "
                    "distinctive disease term in the GEO series title/summary. "
                    "n_samples is the GEO series total and may include non-spatial "
                    "assays; confirm the spatial-only count, tissue detail and "
                    "histology, and link the source paper before promoting past "
                    "machine_draft."
                )
                seen.add(acc)
                x["deposition_year"] = deposition.year_from_geo_summary(x)
                rid = write_draft(code, tissue, plat, x, note, args.dry_run)
                if rid:
                    per_type[code] = per_type.get(code, 0) + 1
                    drafted += 1
                    if args.limit and drafted >= args.limit:
                        print(f"\nHit --limit {args.limit}.")
                        _summary(drafted, per_type, args.dry_run)
                        return 0
                    time.sleep(THROTTLE)
    _summary(drafted, per_type, args.dry_run)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="stop after N new drafts")
    ap.add_argument("--retmax", type=int, default=25, help="GEO hits per cancer type")
    ap.add_argument(
        "--mode",
        choices=["type", "platform"],
        default="type",
        help="type: exact-phrase per cancer type; platform: broad sweep + classifier",
    )
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = ap.parse_args(argv)

    oncotree = validate.load_oncotree()
    uberon = validate.load_uberon()
    have = existing_gses()
    if args.mode == "platform":
        return run_platform_mode(args, oncotree, uberon, have)
    seen: set[str] = set()
    drafted = 0
    per_type: dict[str, int] = {}

    for code, tissue, name, kw in CANCERS:
        if code not in oncotree:
            print(f"  skip type {code}: not in OncoTree snapshot")
            continue
        if tissue not in uberon:
            print(f"  skip type {code}: tissue {tissue} not in UBERON seed")
            continue
        ck = re.compile(kw, re.I)
        term = (
            f'"{name}"[All Fields] AND {SPATIAL_TERMS} AND '
            f'"Homo sapiens"[Organism] AND gse[ETYP]'
        )
        ids = esearch(term, args.retmax)
        time.sleep(THROTTLE)
        rows = esummary(ids)
        for uid in rows.get("uids", []):
            x = rows[uid]
            acc = x.get("accession", "")
            if x.get("entrytype") != "GSE" or not acc.startswith("GSE"):
                continue
            if acc in have or acc in seen:
                continue
            if "homo sapiens" not in (x.get("taxon", "") or "").lower():
                continue
            title = (x.get("title") or "").strip()
            summary = (x.get("summary") or "").strip()
            blob = f"{title} {summary}"
            plat = detect_platform(blob)
            if not plat:
                continue
            if not ck.search(blob):
                continue
            if EXCLUDE.search(blob):
                continue
            seen.add(acc)
            # id pattern forbids underscores; slug the platform with hyphens
            # (visium_hd -> visium-hd), matching the existing record ids.
            plat_slug = plat.replace("_", "-")
            rid = f"{plat_slug}-{code.lower()}-geo-{acc.lower()}"
            path = DATASETS / f"{rid}.yaml"
            if path.exists():
                continue
            n = x.get("n_samples")
            nline = f"n_samples: {n}\n" if isinstance(n, int) and n > 0 else ""
            dy = deposition.year_from_geo_summary(x)
            dyline = f"deposition_year: {dy}\n" if isinstance(dy, int) else ""
            note = (
                "Machine-drafted by the GEO spatial harvester. Accession returned "
                f"live by NCBI E-utilities (organism Homo sapiens). Platform "
                f"detected as {plat} from the GEO series title/summary "
                f'("{name}" query). n_samples is the GEO series total and may '
                "include non-spatial assays; confirm the spatial-only count, "
                "tissue detail and histology, and link the source paper before "
                "promoting past machine_draft."
            )
            body = (
                f"id: {rid}\n"
                f"title: {q(title) if title else q(name + ' spatial transcriptomics (' + acc + ')')}\n"
                f"cancer_type: {code}\n"
                f'tissue: "{tissue}"\n'
                f"modality: spatial_transcriptomics\n"
                f"platform: {plat}\n"
                f"{nline}"
                f"accession:\n  - {acc}\n"
                f"access: open\n"
                f"reuse_notes: >-\n  {note}\n"
                f"{dyline}"
                f"curation_status: machine_draft\n"
            )
            per_type[code] = per_type.get(code, 0) + 1
            drafted += 1
            if args.dry_run:
                print(f"  [dry] {rid}  n={n}  {title[:52]}")
            else:
                path.write_text(body)
                print(f"  [+]   {rid}  n={n}  {title[:52]}")
            if args.limit and drafted >= args.limit:
                print(f"\nHit --limit {args.limit}.")
                _summary(drafted, per_type, args.dry_run)
                return 0
            time.sleep(THROTTLE)

    _summary(drafted, per_type, args.dry_run)
    return 0


def _summary(drafted: int, per_type: dict[str, int], dry: bool) -> None:
    verb = "would draft" if dry else "drafted"
    print(f"\nHarvester {verb} {drafted} new record(s).")
    if per_type:
        print(
            "  by type: " + ", ".join(f"{k}+{v}" for k, v in sorted(per_type.items()))
        )


if __name__ == "__main__":
    raise SystemExit(main())
