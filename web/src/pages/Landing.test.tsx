import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Landing from "./Landing";
import { SiteContext } from "../data";
import { STATUS_DESC } from "../lib/format";
import type { Dataset, SiteData } from "../types";

function dsLite(cancer_type: string, cancer_type_name: string): Dataset {
  return {
    id: `d-${cancer_type}-${Math.random()}`,
    title: "t",
    cancer_type,
    cancer_type_name,
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
  };
}

const SITE: SiteData = {
  generated_at: "2026-07-15",
  version: "0.1.0",
  counts: { datasets: 1234, cancer_types: 42 },
  facets: {
    modality: ["spatial_transcriptomics", "spatial_proteomics"],
    platform: ["visium", "xenium", "imc", "somethingelse"],
    cancer_type: ["BRCA", "GB"],
    access: ["open"],
    curation_status: ["verified"],
  },
  datasets: [
    dsLite("BRCA", "Breast"),
    dsLite("BRCA", "Breast"),
    dsLite("GB", "Glioblastoma"),
  ],
};

function renderLanding(site: SiteData = SITE) {
  return render(
    <MemoryRouter>
      <SiteContext.Provider value={site}>
        <Landing />
      </SiteContext.Provider>
    </MemoryRouter>,
  );
}

describe("Landing", () => {
  it("renders the hero headline and subhead", () => {
    renderLanding();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toMatch(
      /curated catalog of public spatial-omics data for oncology/i,
    );
    expect(
      screen.getByText(/whether you can\s+actually reuse it/i),
    ).toBeInTheDocument();
  });

  it("shows live stats from site data, comma-formatted", () => {
    const { container } = renderLanding();
    const stats = container.querySelector(".hero-stats")!;
    const text = stats.textContent || "";
    expect(text).toContain("Datasets");
    expect(text).toContain("1,234"); // toLocaleString of counts.datasets
    expect(text).toContain("Cancer types");
    expect(text).toContain("42");
    expect(text).toContain("Platforms");
    expect(text).toContain("Modalities");
    expect(container.querySelector(".hero-meta")?.textContent).toMatch(
      /2026-07-15/,
    );
  });

  it("routes the primary CTAs and the GitHub icon correctly", () => {
    renderLanding();
    expect(
      screen
        .getByRole("link", { name: /Explore the catalog/i })
        .getAttribute("href"),
    ).toBe("/catalog");
    expect(
      screen
        .getByRole("link", { name: /How it.s curated/i })
        .getAttribute("href"),
    ).toBe("/about");
    const gh = screen.getByRole("link", { name: "GitHub repository" });
    expect(gh.getAttribute("href")).toBe("https://github.com/oncomap/oncomap");
    expect(gh.getAttribute("target")).toBe("_blank");
    expect(gh.getAttribute("rel")).toContain("noopener");
  });

  it("deep-links the browse-by chips into pre-filtered catalog views", () => {
    renderLanding();
    // cancer chips from topCancerTypes (BRCA has 2, GB has 1) - scope to the
    // cancer-type nav so example cards ("Breast cancer + IMC") don't collide.
    const cancerNav = screen.getByRole("navigation", {
      name: "Browse by cancer type",
    });
    expect(
      within(cancerNav)
        .getByRole("link", { name: /Breast/ })
        .getAttribute("href"),
    ).toBe("/catalog?cancer=BRCA");
    expect(
      within(cancerNav)
        .getByRole("link", { name: /Glioblastoma/ })
        .getAttribute("href"),
    ).toBe("/catalog?cancer=GB");
    // modality chips (labels via MODALITY_LABEL)
    expect(
      screen
        .getByRole("link", { name: "transcriptomics" })
        .getAttribute("href"),
    ).toBe("/catalog?modality=spatial_transcriptomics");
    // platform chips filtered to KEY_PLATFORMS present in facets (imc yes, somethingelse no)
    expect(
      screen.getByRole("link", { name: "visium" }).getAttribute("href"),
    ).toBe("/catalog?platform=visium");
    expect(screen.getByRole("link", { name: "imc" }).getAttribute("href")).toBe(
      "/catalog?platform=imc",
    );
    expect(screen.queryByRole("link", { name: "somethingelse" })).toBeNull();
  });

  it("renders the four example-query deep links", () => {
    renderLanding();
    expect(
      screen
        .getByRole("link", { name: /Breast cancer \+ IMC/ })
        .getAttribute("href"),
    ).toBe("/catalog?cancer=BRCA&platform=imc");
    expect(
      screen
        .getByRole("link", { name: /Verified datasets only/ })
        .getAttribute("href"),
    ).toBe("/catalog?status=verified");
    expect(
      screen
        .getByRole("link", { name: /Glioblastoma proteomics/ })
        .getAttribute("href"),
    ).toBe("/catalog?cancer=GB&modality=spatial_proteomics");
  });

  it("explains the three curation tiers and links to verified", () => {
    const { container } = renderLanding();
    const tiers = container.querySelector(".tier-list")!;
    expect(
      within(tiers as HTMLElement).getByText(STATUS_DESC.verified),
    ).toBeInTheDocument();
    expect(
      within(tiers as HTMLElement).getByText(STATUS_DESC.machine_draft),
    ).toBeInTheDocument();
    expect(
      screen
        .getByRole("link", { name: /Jump to verified datasets/ })
        .getAttribute("href"),
    ).toBe("/catalog?status=verified");
  });

  it("keeps the document title as the bare site name", () => {
    renderLanding();
    expect(document.title).toBe("OncoMap");
  });
});
