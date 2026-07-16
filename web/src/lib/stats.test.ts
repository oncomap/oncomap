import { describe, it, expect } from "vitest";
import {
  detectSource,
  depositionYear,
  countBy,
  growth,
  SOURCES,
} from "./stats";
import type { Dataset } from "../types";

function ds(over: Partial<Dataset> = {}): Dataset {
  return {
    id: "visium-brca-geo-gse1",
    title: "t",
    cancer_type: "BRCA",
    cancer_type_name: "Breast",
    cancer_type_ncit: "",
    tissue: "",
    tissue_label: "",
    modality: "spatial_transcriptomics",
    platform: "visium",
    sequencer: "",
    n_samples: "",
    n_patients: "",
    accession: "GSE1",
    access: "open",
    curation_status: "verified",
    last_verified: "",
    deposition_year: 2024,
    source_paper: "",
    paper_doi: "",
    paper_year: "",
    lab: "",
    lab_name: "",
    pipeline_ref: "",
    method_name: "",
    reuse_notes: "",
    ...over,
  };
}

describe("detectSource", () => {
  it("classifies each source from id/accession", () => {
    expect(detectSource(ds({ accession: "GSE9" }))).toBe("geo");
    expect(
      detectSource(ds({ id: "x-zenodo-1", accession: "10.5281/zenodo.9" })),
    ).toBe("zenodo");
    expect(
      detectSource(ds({ id: "x-htan-1", accession: "SYNAPSE:syn9" })),
    ).toBe("htan");
    expect(detectSource(ds({ id: "x-biad-1", accession: "S-BIAD9" }))).toBe(
      "biad",
    );
    expect(detectSource(ds({ id: "x-ae-1", accession: "E-MTAB-9" }))).toBe(
      "arrayexpress",
    );
    expect(detectSource(ds({ id: "x-cxg-1", accession: "CELLxGENE:9" }))).toBe(
      "cellxgene",
    );
    expect(detectSource(ds({ id: "x-tenx-1", accession: "10X:9" }))).toBe(
      "tenx",
    );
  });
  it("every SOURCES entry has a label and colour", () => {
    for (const s of SOURCES) {
      expect(s.label).toBeTruthy();
      expect(s.color).toMatch(/^#/);
    }
  });
});

describe("depositionYear", () => {
  it("returns a positive year or null", () => {
    expect(depositionYear(ds({ deposition_year: 2024 }))).toBe(2024);
    expect(depositionYear(ds({ deposition_year: "2022" }))).toBe(2022);
    expect(depositionYear(ds({ deposition_year: "" }))).toBeNull();
  });
});

describe("countBy", () => {
  it("counts and sorts descending, with optional top-N cap", () => {
    const rows = [
      ds({ cancer_type: "BRCA" }),
      ds({ cancer_type: "BRCA" }),
      ds({ cancer_type: "GB" }),
    ];
    const c = countBy(rows, (d) => d.cancer_type);
    expect(c[0]).toEqual({ key: "BRCA", count: 2 });
    expect(c[1]).toEqual({ key: "GB", count: 1 });
    expect(countBy(rows, (d) => d.cancer_type, 1)).toHaveLength(1);
  });
});

describe("growth", () => {
  it("builds cumulative per-group series over the year range", () => {
    const rows = [
      ds({ deposition_year: 2022, modality: "spatial_transcriptomics" }),
      ds({ deposition_year: 2024, modality: "spatial_transcriptomics" }),
      ds({ deposition_year: 2024, modality: "spatial_proteomics" }),
      ds({ deposition_year: "" }), // undated -> excluded
    ];
    const groups = [
      { key: "spatial_transcriptomics", label: "T", color: "#000" },
      { key: "spatial_proteomics", label: "P", color: "#111" },
    ];
    const g = growth(rows, (d) => d.modality, groups);
    expect(g.years).toEqual([2022, 2023, 2024]);
    expect(g.covered).toBe(3);
    expect(g.total).toBe(4);
    const t = g.series.find((s) => s.key === "spatial_transcriptomics")!;
    expect(t.values).toEqual([1, 1, 2]); // cumulative
    const p = g.series.find((s) => s.key === "spatial_proteomics")!;
    expect(p.values).toEqual([0, 0, 1]);
    expect(g.annualTotals).toEqual([1, 0, 2]);
  });
  it("handles no dated rows", () => {
    const g = growth([ds({ deposition_year: "" })], (d) => d.modality, []);
    expect(g.years).toEqual([]);
    expect(g.covered).toBe(0);
  });
});
