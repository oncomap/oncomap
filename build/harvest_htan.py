#!/usr/bin/env python3
"""Harvest human tumour spatial-transcriptomics datasets from HTAN.

The Human Tumor Atlas Network publishes its file-level metadata as public JSON on
the Data Portal (data.humantumoratlas.org/processed_syn_data.json) - no GCP,
BigQuery or Synapse auth needed for the metadata (the data files themselves are
largely access-controlled, so records are cataloged as pointers with access:
controlled, per the data-classification policy).

This reads that metadata (downloaded once to a local path), keeps the in-scope
spatial-transcriptomics assays (10X Visium, MERFISH, Slide-seq), groups files
into datasets by (atlas x platform x cancer type), derives the cancer type from
the ICD-O organ + morphology, and drafts one record per group. The accession is
a resolvable Synapse id pointer; n_patients / n_samples are the distinct HTAN
participants / biospecimens in the group. Records land at curation_status
machine_draft for human promotion.

Usage:
  uv run python build/harvest_htan.py --json /path/to/processed_syn_data.json --dry-run
  uv run python build/harvest_htan.py --json /path/to/processed_syn_data.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import validate

DATASETS = validate.RECORDS_DIR / "datasets"
# HTAN assayName -> (platform, modality). Spatial transcriptomics + the
# imaging-based spatial-proteomics assays (Phase 4). Other HTAN assays
# (scRNA-seq, bulk, H&E, generic Imaging, Electron Microscopy) are out of scope.
ASSAY = {
    "10X Visium": ("visium", "spatial_transcriptomics"),
    "MERFISH": ("merfish", "spatial_transcriptomics"),
    "Slide-seq": ("slide_seq", "spatial_transcriptomics"),
    "CODEX": ("codex", "spatial_proteomics"),
    "CyCIF": ("cycif", "spatial_proteomics"),
    "MxIF": ("mxif", "spatial_proteomics"),
    "mIHC": ("mihc", "spatial_proteomics"),
    "MIBI": ("mibi", "spatial_proteomics"),
    "IMC": ("imc", "spatial_proteomics"),
    "RareCyte Orion": ("orion", "spatial_proteomics"),
    "NanoString GeoMX DSP": ("geomx", "spatial_proteomics"),
}


# (cancer_type OncoTree, UBERON tissue) derived from organ + morphology. Ordered;
# first match wins. Conservative - ambiguous organs/morphologies fall through to
# None and are skipped rather than guessed (e.g. nasal-cavity melanoma,
# neuroblastoma, unknown/Not-Reported organ).
def classify(organ: str, morph: str):
    o = (organ or "").lower()
    m = (morph or "").lower()
    if "melanoma" in m and "skin" in o:
        return "SKCM", "UBERON:0002097"
    if "breast" in o and ("carcinoma" in m or "ductal" in m or "lobular" in m):
        return "BRCA", "UBERON:0000310"
    if "ovary" in o and "carcinosarcoma" in m:
        return "OCS", "UBERON:0000992"
    if "ovary" in o and "serous" in m:
        return "HGSOC", "UBERON:0000992"
    if ("uterus" in o or "endometri" in o or "endometri" in m) and "carcinoma" in m:
        return "UCEC", "UBERON:0000995"
    if "pancreas" in o and (
        "adenocarcinoma" in m
        or "ductal" in m
        or "carcinoma" in m
        or "pancreatobiliary" in m
    ):
        return "PAAD", "UBERON:0001264"
    if "lung" in o and "adenocarcinoma" in m:
        return "LUAD", "UBERON:0002048"
    if "kidney" in o and "renal cell" in m:
        return "CCRCC", "UBERON:0002113"
    if (
        "colon" in o or "sigmoid" in o or "rectal" in o or "rectum" in o or "cecum" in o
    ) and ("adenocarcinoma" in m or "intestinal" in m):
        return "COADREAD", "UBERON:0001155"
    return None, None


def atlas_slug(name: str) -> str:
    # "HTAN HTAPP" -> "htapp", "HTAN WUSTL" -> "wustl"
    return re.sub(
        r"[^a-z0-9]+", "-", (name or "").lower().replace("htan", "").strip()
    ).strip("-")


def participant(biospecimen_id: str) -> str:
    # "HTA1_336_5221304" -> participant "HTA1_336"
    m = re.match(r"(HTA\d+_\d+)", biospecimen_id or "")
    return m.group(1) if m else (biospecimen_id or "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", required=True, type=Path, help="processed_syn_data.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    d = json.loads(args.json.read_text())
    files = d["files"]
    diag = d["diagnosisByParticipantID"]

    # group spatial files by (atlas, platform, cancer_type)
    groups: dict[tuple, dict] = defaultdict(
        lambda: {
            "participants": set(),
            "biospecimens": set(),
            "syn": None,
            "tissue": None,
        }
    )
    for f in files:
        pm = ASSAY.get(f.get("assayName"))
        if not pm:
            continue
        plat, modality = pm
        organ = morph = None
        for did in f.get("diagnosisIds") or []:
            r = diag.get(did)
            if r:
                organ = r.get("TissueorOrganofOrigin")
                morph = r.get("PrimaryDiagnosis")
                break
        code, tissue = classify(organ, morph)
        if not code:
            continue
        atlas = f.get("atlas_name") or "HTAN"
        g = groups[(atlas, plat, code)]
        g["tissue"] = tissue
        g["modality"] = modality
        for b in f.get("biospecimenIds") or []:
            g["biospecimens"].add(b)
            g["participants"].add(participant(b))
        if g["syn"] is None and f.get("synapseId"):
            g["syn"] = f["synapseId"]

    oncotree = validate.load_oncotree()
    uberon = set(validate.load_uberon())
    drafted = 0
    per_type: dict[str, int] = {}
    for (atlas, plat, code), g in sorted(groups.items()):
        if code not in oncotree or g["tissue"] not in uberon or not g["syn"]:
            continue
        rid = f"{plat.replace('_', '-')}-{code.lower()}-htan-{atlas_slug(atlas)}"
        path = DATASETS / f"{rid}.yaml"
        if path.exists():
            continue
        npat = len(g["participants"])
        nsamp = len(g["biospecimens"])
        modality = g["modality"]
        mod_word = modality.replace("spatial_", "spatial ")
        geomx_note = (
            " GeoMx DSP can carry an RNA or protein panel; confirm the panel type."
            if plat == "geomx"
            else ""
        )
        note = (
            f"Machine-drafted from the public HTAN Data Portal metadata "
            f"(data.humantumoratlas.org). {atlas} {plat} {mod_word}; "
            f"cancer_type {code} derived from the ICD-O organ + morphology of "
            f"{npat} participant(s) / {nsamp} biospecimen(s). The HTAN data files "
            f"are largely access-controlled (dbGaP), so this is a pointer: the "
            f"accession is a resolvable Synapse entity, obtain data via HTAN. "
            f"Confirm the spatial-only sample count and any subtype before promoting."
            f"{geomx_note}"
        )
        body = (
            f"id: {rid}\n"
            f"title: \"HTAN {atlas.replace('HTAN ','')} {plat} {mod_word} of {code}\"\n"
            f"cancer_type: {code}\n"
            f'tissue: "{g["tissue"]}"\n'
            f"modality: {modality}\n"
            f"platform: {plat}\n"
            f"n_patients: {npat}\n"
            f"accession:\n  - SYNAPSE:{g['syn']}\n"
            f"access: controlled\n"
            f"reuse_notes: >-\n  {note}\n"
            f"curation_status: machine_draft\n"
        )
        per_type[code] = per_type.get(code, 0) + 1
        drafted += 1
        if args.dry_run:
            print(f"  [dry] {rid}  n_patients={npat} n_biospec={nsamp}")
        else:
            path.write_text(body)
            print(f"  [+]   {rid}  n_patients={npat} n_biospec={nsamp}")

    verb = "would draft" if args.dry_run else "drafted"
    print(f"\nHTAN harvester {verb} {drafted} dataset record(s).")
    if per_type:
        print(
            "  by type: " + ", ".join(f"{k}+{v}" for k, v in sorted(per_type.items()))
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
