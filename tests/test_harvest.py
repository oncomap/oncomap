"""Offline unit tests for the multi-source harvesters.

No network: these exercise the integrity-critical pure logic - platform
detection, the model/methods/artifact exclude filters, the conservative disease
classifier, the id-slug construction and the Zenodo access mapping - with
synthetic strings, so they stay deterministic and run in the offline CI.
"""

import deposition as dep
import harvest_arrayexpress as ae
import harvest_geo as g
import harvest_zenodo as z


def classify(text):
    """Mirror the harvesters' first-match classifier over CLASSIFY."""
    for rx, code, tissue in g.CLASSIFY:
        if rx.search(text):
            return code, tissue
    return None


# --- platform detection (priority order) -----------------------------------
def test_detect_visium():
    assert g.detect_platform("10x Genomics Visium spatial") == "visium"


def test_detect_visium_hd_beats_visium():
    assert g.detect_platform("Visium HD and Visium libraries") == "visium_hd"


def test_detect_xenium_cosmx_stereo_slide():
    assert g.detect_platform("Xenium in situ") == "xenium"
    assert g.detect_platform("NanoString CosMx SMI") == "cosmx"
    assert g.detect_platform("Stereo-seq at subcellular resolution") == "stereo_seq"
    assert g.detect_platform("Slide-seqV2 beads") == "slide_seq"


def test_detect_none_when_no_named_platform():
    assert g.detect_platform("bulk RNA-seq of tumours") is None


# --- EXCLUDE: model systems / methods / benchmarks -------------------------
def test_exclude_drops_model_and_methods():
    for bad in (
        "patient-derived xenograft (PDX) model",
        "brain organoid model",
        "clear cell renal cell carcinoma patient-derived tumoroids",
        "mouse model of glioma",
        "a GBM cell line panel",
        "in silico reconstruction",
        "systematic benchmarking of platforms",
        "spatialGE web application",
    ):
        assert g.EXCLUDE.search(bad), bad


def test_exclude_passes_primary_tumour_text():
    assert not g.EXCLUDE.search(
        "Visium spatial transcriptomics of human colorectal cancer tissue"
    )


# --- classifier: distinctive terms map, ambiguous generics do not ----------
def test_classify_distinctive_terms():
    assert classify("clear cell renal cell carcinoma")[0] == "CCRCC"
    assert classify("glioblastoma multiforme")[0] == "GB"
    assert classify("pleural mesothelioma")[0] == "PLMESO"
    assert classify("high-grade serous ovarian cancer")[0] == "HGSOC"
    assert classify("ovarian clear cell carcinoma")[0] == "CCOV"


def test_classify_skips_ambiguous_generics():
    # subtype-unknown generics must NOT be guessed
    assert classify("renal cell carcinoma") is None
    assert classify("an unspecified lymphoma") is None
    assert classify("low-grade glioma of the brainstem") is None


def test_classify_hodgkin_guard():
    # "non-Hodgkin" must not be captured by the CHL Hodgkin rule (substring trap)
    assert classify("nodal B-cell non-Hodgkin lymphomas") is None
    assert classify("various Non-Hodgkins lymphomas") is None
    # genuine Hodgkin still classifies
    assert classify("classical Hodgkin lymphoma")[0] == "CHL"


# --- write_draft id-slug construction --------------------------------------
def _rid(**over):
    x = {"accession": "GSE99999999", "title": "t", "n_samples": None}
    x.update(over.pop("x", {}))
    return g.write_draft(
        over.get("code", "COADREAD"),
        over.get("tissue", "UBERON:0001155"),
        over.get("plat", "visium_hd"),
        x,
        "note",
        True,  # dry-run: returns the rid without writing
        source=over.get("source", "geo"),
    )


def test_write_draft_hyphenates_underscore_platform():
    assert _rid(plat="visium_hd") == "visium-hd-coadread-geo-gse99999999"
    assert _rid(plat="stereo_seq") == "stereo-seq-coadread-geo-gse99999999"


def test_write_draft_source_token_and_doi_slug():
    assert _rid(source="ae").endswith("-ae-gse99999999")
    rid = _rid(
        plat="visium",
        source="zenodo",
        x={"accession": "10.5281/zenodo.12345", "slug": "zenodo-12345"},
    )
    assert rid == "visium-coadread-zenodo-zenodo-12345"


# --- ArrayExpress / Zenodo source-specific guards --------------------------
def test_arrayexpress_malignancy_gate():
    assert ae.MALIGNANT.search("hepatocellular carcinoma")
    assert not ae.MALIGNANT.search("spatial reference of the healthy endometrium")


def test_zenodo_nonhuman_filter():
    for bad in ("mouse brain", "rat kidney", "zebrafish embryo", "C57BL/6 tissue"):
        assert z.NONHUMAN.search(bad), bad
    assert not z.NONHUMAN.search("human colorectal cancer")


def test_zenodo_artifact_filter_drops_byproducts_and_scrna():
    for bad in (
        "Xenium Breast Cancer Gene Count",
        "Factor Analysis of the cohort",
        "PDAC TLS Visium H&Es",
        "Chromium scRNA-seq data of tumours",
        "Supplementary Dataset and Code",
    ):
        assert z.ARTIFACT.search(bad), bad
    assert not z.ARTIFACT.search("Spatial Transcriptomics of Human Colorectal Cancer")


# --- spatial-proteomics modality extension (Phase 4) -----------------------
import json
from pathlib import Path

import jsonschema

_SCHEMA = json.loads(
    (
        Path(__file__).resolve().parent.parent / "schema" / "dataset.schema.json"
    ).read_text()
)
_PROTEOMICS = {"codex", "cycif", "mxif", "mihc", "mibi", "imc", "orion", "geomx"}


def test_platform_modality_covers_every_enum_value():
    enum = set(_SCHEMA["properties"]["platform"]["enum"])
    assert enum - set(g.PLATFORM_MODALITY) == set()  # no platform without a modality


def test_proteomics_platforms_map_to_proteomics():
    for p in _PROTEOMICS:
        assert g.PLATFORM_MODALITY[p] == "spatial_proteomics"
    for p in ("visium", "xenium", "cosmx", "merfish", "slide_seq", "stereo_seq"):
        assert g.PLATFORM_MODALITY[p] == "spatial_transcriptomics"


def test_confirm_platform_gate():
    # transcriptomics never needs confirmation
    assert g.confirm_platform("visium", "anything")
    # proteomics needs real protein/imaging context
    assert g.confirm_platform("codex", "CODEX multiplexed antibody imaging")
    assert not g.confirm_platform("imc", "RNA-seq of bladder cancer")


def test_proteomics_platform_detected_with_context():
    assert g.detect_platform("imaging mass cytometry of tumour tissue") == "imc"
    assert g.detect_platform("CODEX multiplexed imaging with antibodies") == "codex"


def test_proteomics_record_validates_against_schema():
    rec = {
        "id": "codex-brca-htan-testcenter",
        "title": "HTAN CODEX proteomics of BRCA",
        "cancer_type": "BRCA",
        "tissue": "UBERON:0000310",
        "modality": "spatial_proteomics",
        "platform": "codex",
        "access": "controlled",
        "curation_status": "machine_draft",
    }
    jsonschema.validate(rec, _SCHEMA)  # raises on invalid


# --- deposition year (growth-over-time support) ----------------------------
def test_deposition_classify():
    assert dep.classify("GSE123") == "geo"
    assert dep.classify("10.5281/zenodo.123") == "zenodo"
    assert dep.classify("S-BIAD1") == "biostudies"
    assert dep.classify("E-MTAB-1") == "biostudies"
    assert dep.classify("SYNAPSE:syn1") == "synapse"


def test_deposition_year_extractors():
    assert dep.year_from_geo_summary({"PDAT": "2024/05/01"}) == 2024
    assert dep.year_from_geo_summary({"summary": "no date here"}) is None
    assert (
        dep.year_from_zenodo_record({"metadata": {"publication_date": "2023-08-15"}})
        == 2023
    )
    assert dep.year_from_biostudies_attrs({"ReleaseDate": "2025-07-30"}) == 2025
    assert dep.year_from_biostudies_attrs({"Title": "x"}) is None


def test_write_draft_emits_deposition_year(tmp_path, monkeypatch):
    monkeypatch.setattr(g, "DATASETS", tmp_path)
    x = {"accession": "GSE999999", "title": "t", "n_samples": None, "deposition_year": 2024}
    rid = g.write_draft("COADREAD", "UBERON:0001155", "visium", x, "note", False)
    assert "deposition_year: 2024\n" in (tmp_path / f"{rid}.yaml").read_text()
    # omitted when absent
    x2 = {"accession": "GSE888888", "title": "t", "n_samples": None}
    rid2 = g.write_draft("COADREAD", "UBERON:0001155", "visium", x2, "note", False)
    assert "deposition_year" not in (tmp_path / f"{rid2}.yaml").read_text()


def test_deposition_year_record_validates_against_schema():
    rec = {
        "id": "visium-coadread-geo-gse1",
        "title": "Visium spatial transcriptomics of colorectal cancer",
        "cancer_type": "COADREAD",
        "tissue": "UBERON:0001155",
        "modality": "spatial_transcriptomics",
        "platform": "visium",
        "access": "open",
        "curation_status": "machine_draft",
        "deposition_year": 2024,
    }
    jsonschema.validate(rec, _SCHEMA)
    rec["deposition_year"] = 1980  # below minimum
    import pytest

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(rec, _SCHEMA)
