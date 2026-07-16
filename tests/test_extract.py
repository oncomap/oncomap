"""Offline unit tests for the extract/ drafter's pure logic.

No network: these exercise detect_platform / accession_kind / build_draft with
synthetic metadata, so they stay deterministic and run in the offline CI.
"""

import draft_from_geo as dfg


# --- detect_platform -------------------------------------------------------
def test_platform_visium():
    assert (
        dfg.detect_platform("processed according to the 10X Visium protocol")[0]
        == "visium"
    )


def test_platform_visium_hd_beats_visium():
    # "visium hd" must win over the bare "visium" substring
    assert (
        dfg.detect_platform("performed using the 10x Genomics Visium HD platform")[0]
        == "visium_hd"
    )


def test_platform_xenium():
    assert dfg.detect_platform("Xenium in situ gene expression on FFPE")[0] == "xenium"


def test_platform_stereo_seq():
    assert (
        dfg.detect_platform("Stereo-seq was performed on 11 tissues")[0] == "stereo_seq"
    )


def test_platform_spatial_transcriptomics_fallback():
    assert (
        dfg.detect_platform("spatial transcriptomics of the microenvironment")[0]
        == "visium"
    )


def test_platform_none_is_ambiguous():
    plat, reason = dfg.detect_platform("bulk RNA-seq and scRNA-seq of tumors")
    assert plat is None and reason.startswith("ambiguous_platform")


def test_platform_geomx_unsupported():
    plat, reason = dfg.detect_platform("NanoString GeoMx Digital Spatial Profiler")
    assert plat is None and reason.startswith("unsupported_platform")


def test_platform_multiple_is_ambiguous():
    plat, reason = dfg.detect_platform("benchmarking Xenium against CosMx and MERSCOPE")
    assert plat is None and reason.startswith("ambiguous_platform:multiple")


# --- accession_kind --------------------------------------------------------
def test_accession_kind():
    assert dfg.accession_kind("GSE268014") == "geo"
    assert dfg.accession_kind("PRJNA603101") == "bioproject"
    assert dfg.accession_kind("10.1038/s41586-020-0000-0") == "doi"
    assert dfg.accession_kind("https://example.org/x") == "url"
    assert dfg.accession_kind("not-an-id") == "unknown"


# --- build_draft -----------------------------------------------------------
def _meta(**over):
    base = dict(
        accession="GSE268014",
        title="Spatial transcriptomics of HNSCC",
        n_samples=39,
        taxon="Homo sapiens",
        is_superseries=False,
        design_text="processed according to the 10X Visium protocol",
        pmid="12345678",
        doi="10.1000/x",
        doi_ok=True,
        unresolved=False,
    )
    base.update(over)
    return base


def test_build_draft_clean_has_no_blockers():
    draft, blockers = dfg.build_draft(_meta())
    assert blockers == []
    assert draft["platform"] == "visium"
    assert draft["id"] == "visium-geo-gse268014"
    assert draft["accession"] == ["GSE268014"]
    assert draft["curation_status"] == "machine_draft"


def test_build_draft_always_leaves_curator_fields_empty():
    draft, _ = dfg.build_draft(_meta())
    # the error-prone judgement calls are never auto-filled
    assert draft["cancer_type"] == ""
    assert draft["tissue"] == ""


def test_build_draft_non_human_blocker():
    _, blockers = dfg.build_draft(_meta(taxon="Mus musculus"))
    assert any(b.startswith("non_human") for b in blockers)


def test_build_draft_superseries_blocker():
    _, blockers = dfg.build_draft(_meta(is_superseries=True))
    assert "superseries" in blockers


def test_build_draft_unresolved_blocker():
    _, blockers = dfg.build_draft(_meta(unresolved=True))
    assert "unresolved_accession" in blockers


def test_build_draft_bad_doi_blocker():
    _, blockers = dfg.build_draft(_meta(doi_ok=False))
    assert any(b.startswith("bad_doi") for b in blockers)


def test_build_draft_ambiguous_platform_blocker_and_empty_platform():
    draft, blockers = dfg.build_draft(_meta(design_text="bulk and single-cell only"))
    assert draft["platform"] == ""
    assert any(b.startswith("ambiguous_platform") for b in blockers)
