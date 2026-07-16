// Pure helpers ported from the original site/app.js. Framework-agnostic:
// accession links/labels, label maps, tooltip copy, the filter predicate, and
// the sort comparator. Kept behaviourally identical to the static view.
import type { Dataset } from "../types";

export function accessionLink(acc: string): string | null {
  const id = acc.trim();
  if (/^GSE\d+$/i.test(id))
    return `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=${id}`;
  if (/^10\.\d{4,9}\//.test(id)) return `https://doi.org/${id}`;
  if (/^PRJNA\d+$/i.test(id))
    return `https://www.ncbi.nlm.nih.gov/bioproject/${id}`;
  if (/^CELLxGENE:/i.test(id))
    return `https://cellxgene.cziscience.com/collections/${id.slice(id.indexOf(":") + 1)}`;
  if (/^10X:/i.test(id))
    return `https://www.10xgenomics.com/datasets/${id.slice(id.indexOf(":") + 1)}`;
  if (/^https?:\/\//.test(id)) return id;
  return null;
}

export function accessionLabel(acc: string): string {
  const id = acc.trim();
  if (/^CELLxGENE:/i.test(id))
    return "CELLxGENE:" + id.slice(id.indexOf(":") + 1, id.indexOf(":") + 9);
  if (/^10X:/i.test(id)) return "10X reference";
  if (/^https?:\/\//.test(id)) {
    try {
      return new URL(id).hostname.replace(/^www\./, "");
    } catch {
      return "link";
    }
  }
  return id;
}

export function accessionParts(accession: string): string[] {
  return (accession || "").split(";").filter(Boolean);
}

export function reuseBand(score: number): "high" | "mid" | "low" {
  return score >= 80 ? "high" : score >= 60 ? "mid" : "low";
}

export const ACCESS_LABEL: Record<string, string> = {
  open: "Open",
  on_request: "On request",
  controlled: "Controlled",
};

export const MODALITY_LABEL: Record<string, string> = {
  spatial_transcriptomics: "transcriptomics",
  spatial_proteomics: "proteomics",
};

export const MODALITY_TIP: Record<string, string> = {
  spatial_proteomics:
    "Spatial proteomics - multiplexed antibody / mass-spec imaging of protein markers in situ",
  spatial_transcriptomics:
    "Spatial transcriptomics - RNA measured in situ across the tissue",
};

export const STATUS_DESC: Record<string, string> = {
  machine_draft:
    "Machine-drafted from a source registry; accession and platform detected automatically, not yet human-reviewed (lowest trust tier)",
  human_reviewed:
    "A curator confirmed the accession resolves, the organism is human, and the platform is correct - not yet linked to a publication",
  verified:
    "Highest trust tier - human-reviewed, with a resolvable accession, a last_verified date, and a linked source publication",
};

export function accessTip(access: string): string {
  return access && access !== "open"
    ? "Record is public, but the data files are gated at source (obtain by request)"
    : "Data is openly downloadable";
}

export const PLATFORM_DESC: Record<string, string> = {
  st_array:
    "Spatial Transcriptomics arrays - the original spot-based ST assay (Visium's predecessor)",
  visium:
    "10x Genomics Visium - spot-based spatial transcriptomics (~55 um spots)",
  visium_hd:
    "10x Genomics Visium HD - continuous, 2 um-binned spatial transcriptomics",
  xenium:
    "10x Genomics Xenium - imaging-based single-cell in situ spatial transcriptomics",
  merfish:
    "MERFISH - multiplexed error-robust FISH; imaging-based single-molecule spatial",
  merscope: "Vizgen MERSCOPE - the commercial MERFISH imaging platform",
  cosmx:
    "NanoString/Bruker CosMx SMI - imaging-based in situ spatial molecular imaging",
  slide_seq:
    "Slide-seq - bead-based spatial transcriptomics at ~10 um resolution",
  stereo_seq:
    "Stereo-seq - DNA-nanoball spatial transcriptomics at subcellular resolution",
  codex:
    "CODEX / PhenoCycler (Akoya) - cyclic antibody multiplexed imaging (spatial proteomics)",
  cycif:
    "t-CyCIF - tissue cyclic immunofluorescence; multiplexed antibody imaging (spatial proteomics)",
  mxif: "Multiplexed immunofluorescence (MxIF) - antibody imaging (spatial proteomics)",
  mihc: "Multiplex immunohistochemistry (mIHC) - antibody imaging (spatial proteomics)",
  mibi: "MIBI - Multiplexed Ion Beam Imaging; mass-spectrometry antibody imaging (spatial proteomics)",
  imc: "Imaging Mass Cytometry (IMC, Fluidigm/Standard BioTools) - metal-tagged antibody imaging (spatial proteomics)",
  orion:
    "RareCyte Orion - multiplexed immunofluorescence imaging (spatial proteomics)",
  geomx:
    "NanoString GeoMx Digital Spatial Profiler - region-based protein (or RNA) profiling",
};

// URL-backed catalog filter state. Field-mapped params keep landing deep-links
// (e.g. ?cancer=BRCA&platform=imc) shareable and reload-safe.
export interface Filters {
  modality: string;
  platform: string;
  cancer: string;
  access: string;
  status: string;
  q: string;
}

export const EMPTY_FILTERS: Filters = {
  modality: "",
  platform: "",
  cancer: "",
  access: "",
  status: "",
  q: "",
};

export function matches(d: Dataset, f: Filters): boolean {
  if (f.modality && d.modality !== f.modality) return false;
  if (f.platform && d.platform !== f.platform) return false;
  if (f.cancer && d.cancer_type !== f.cancer) return false;
  if (f.access && d.access !== f.access) return false;
  if (f.status && d.curation_status !== f.status) return false;
  if (f.q) {
    const hay = [
      d.title,
      d.cancer_type,
      d.cancer_type_name,
      d.tissue,
      d.tissue_label,
      d.accession,
      d.platform,
    ]
      .join(" ")
      .toLowerCase();
    if (!hay.includes(f.q.toLowerCase())) return false;
  }
  return true;
}

export function sortRows(rows: Dataset[], key: string): Dataset[] {
  return [...rows].sort((a, b) => {
    const x = a[key as keyof Dataset];
    const y = b[key as keyof Dataset];
    const nx = Number(x);
    const ny = Number(y);
    if (x !== "" && y !== "" && !isNaN(nx) && !isNaN(ny)) return nx - ny;
    return String(x).localeCompare(String(y));
  });
}

// Windowed page numbers: all when few, else first/last two + current +/-1 with
// "gap" markers so the strip stays short.
export function pageWindow(total: number, current: number): (number | "gap")[] {
  if (total <= 9) return Array.from({ length: total }, (_, i) => i + 1);
  const keep = new Set([
    1,
    2,
    total - 1,
    total,
    current - 1,
    current,
    current + 1,
  ]);
  const nums = [...keep]
    .filter((p) => p >= 1 && p <= total)
    .sort((a, b) => a - b);
  const out: (number | "gap")[] = [];
  let prev = 0;
  for (const p of nums) {
    if (p - prev > 1) out.push("gap");
    out.push(p);
    prev = p;
  }
  return out;
}
