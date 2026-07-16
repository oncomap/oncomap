import { describe, it, expect } from "vitest";
import {
  accessionLink,
  accessionLabel,
  accessionParts,
  reuseBand,
  matches,
  sortRows,
  pageWindow,
  EMPTY_FILTERS,
  type Filters,
} from "./format";
import type { Dataset } from "../types";

describe("accessionLink", () => {
  it("maps known schemes to canonical URLs", () => {
    expect(accessionLink("GSE123")).toBe(
      "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE123",
    );
    expect(accessionLink("10.5281/zenodo.42")).toBe(
      "https://doi.org/10.5281/zenodo.42",
    );
    expect(accessionLink("PRJNA9")).toBe(
      "https://www.ncbi.nlm.nih.gov/bioproject/PRJNA9",
    );
    expect(accessionLink("CELLxGENE:abc")).toBe(
      "https://cellxgene.cziscience.com/collections/abc",
    );
    expect(accessionLink("10X:foo")).toBe(
      "https://www.10xgenomics.com/datasets/foo",
    );
    expect(accessionLink("https://example.org/x")).toBe(
      "https://example.org/x",
    );
  });

  it("returns null for unrecognized / unsafe input (no javascript: or bare text)", () => {
    expect(accessionLink("S-BIAD123")).toBeNull();
    expect(accessionLink("just text")).toBeNull();
    expect(accessionLink("javascript:alert(1)")).toBeNull();
    expect(accessionLink("SYNAPSE:syn1")).toBeNull();
  });
});

describe("accessionLabel / accessionParts", () => {
  it("labels a plain accession as itself and a URL by hostname", () => {
    expect(accessionLabel("GSE123")).toBe("GSE123");
    expect(accessionLabel("https://www.ebi.ac.uk/x")).toBe("ebi.ac.uk");
  });
  it("splits a semicolon-joined accession string", () => {
    expect(accessionParts("GSE1;GSE2")).toEqual(["GSE1", "GSE2"]);
    expect(accessionParts("")).toEqual([]);
  });
});

describe("reuseBand", () => {
  it("thresholds at 80 (high) and 60 (mid)", () => {
    expect(reuseBand(80)).toBe("high");
    expect(reuseBand(79)).toBe("mid");
    expect(reuseBand(60)).toBe("mid");
    expect(reuseBand(59)).toBe("low");
    expect(reuseBand(0)).toBe("low");
  });
});

function ds(over: Partial<Dataset> = {}): Dataset {
  return {
    id: "x",
    title: "Visium of breast cancer",
    cancer_type: "BRCA",
    cancer_type_name: "Breast",
    cancer_type_ncit: "",
    tissue: "UBERON:1",
    tissue_label: "breast",
    modality: "spatial_transcriptomics",
    platform: "visium",
    sequencer: "",
    n_samples: 3,
    n_patients: 2,
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

describe("matches", () => {
  const base: Filters = { ...EMPTY_FILTERS };
  it("passes everything with empty filters", () => {
    expect(matches(ds(), base)).toBe(true);
  });
  it("filters by each faceted field", () => {
    expect(matches(ds(), { ...base, platform: "xenium" })).toBe(false);
    expect(matches(ds(), { ...base, cancer: "GB" })).toBe(false);
    expect(matches(ds(), { ...base, modality: "spatial_proteomics" })).toBe(
      false,
    );
    expect(matches(ds(), { ...base, access: "controlled" })).toBe(false);
    expect(matches(ds(), { ...base, status: "machine_draft" })).toBe(false);
    expect(
      matches(ds({ platform: "xenium" }), { ...base, platform: "xenium" }),
    ).toBe(true);
  });
  it("free-text search is case-insensitive across title/cancer/tissue/accession/platform", () => {
    expect(matches(ds(), { ...base, q: "BREAST" })).toBe(true);
    expect(matches(ds(), { ...base, q: "gse1" })).toBe(true);
    expect(matches(ds(), { ...base, q: "nomatch" })).toBe(false);
  });
});

describe("sortRows", () => {
  it("sorts numerically when both values are numbers, else lexically", () => {
    const rows = [
      ds({ id: "a", n_samples: 10 }),
      ds({ id: "b", n_samples: 2 }),
    ];
    expect(sortRows(rows, "n_samples").map((r) => r.id)).toEqual(["b", "a"]);
    const byTitle = [
      ds({ id: "a", title: "Zebra" }),
      ds({ id: "b", title: "Apple" }),
    ];
    expect(sortRows(byTitle, "title").map((r) => r.id)).toEqual(["b", "a"]);
  });
  it("does not mutate the input array", () => {
    const rows = [ds({ id: "a", n_samples: 2 }), ds({ id: "b", n_samples: 1 })];
    sortRows(rows, "n_samples");
    expect(rows.map((r) => r.id)).toEqual(["a", "b"]);
  });
});

describe("pageWindow", () => {
  it("lists all pages when few", () => {
    expect(pageWindow(3, 1)).toEqual([1, 2, 3]);
  });
  it("windows with gaps when many", () => {
    const w = pageWindow(20, 10);
    expect(w[0]).toBe(1);
    expect(w).toContain(10);
    expect(w).toContain("gap");
    expect(w[w.length - 1]).toBe(20);
  });
});
