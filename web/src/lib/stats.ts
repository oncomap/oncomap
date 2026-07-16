// Client-side aggregation for the /stats page. Everything is derived from the
// datasets already in site.json - no separate stats payload. detectSource mirrors
// source_of() in build/compile.py so the two stay in lockstep.
import type { Dataset } from "../types";

export type SourceKey =
  | "geo"
  | "zenodo"
  | "htan"
  | "biad"
  | "cellxgene"
  | "arrayexpress"
  | "tenx"
  | "unknown";

export function detectSource(d: Dataset): SourceKey {
  const id = (d.id || "").toLowerCase();
  const acc = (d.accession || "").toUpperCase();
  if (acc.startsWith("GSE") || id.includes("-geo-")) return "geo";
  if (acc.includes("ZENODO") || id.includes("zenodo")) return "zenodo";
  if (acc.startsWith("SYNAPSE:") || id.includes("-htan-")) return "htan";
  if (acc.startsWith("S-BIAD") || id.includes("-biad-")) return "biad";
  if (acc.startsWith("E-MTAB") || id.includes("-ae-")) return "arrayexpress";
  if (acc.startsWith("CELLXGENE:") || id.includes("-cxg-")) return "cellxgene";
  if (acc.startsWith("10X:") || id.includes("-tenx-") || id.includes("-10x-"))
    return "tenx";
  return "unknown";
}

// Ordered largest-first (matches the by_source distribution) with a label + a
// distinct categorical color per source.
export const SOURCES: { key: SourceKey; label: string; color: string }[] = [
  { key: "geo", label: "GEO", color: "#00639a" },
  { key: "zenodo", label: "Zenodo", color: "#6b3fa0" },
  { key: "htan", label: "HTAN", color: "#1a7f52" },
  { key: "biad", label: "BioImage Archive", color: "#c2410c" },
  { key: "cellxgene", label: "CELLxGENE", color: "#0891b2" },
  { key: "arrayexpress", label: "ArrayExpress", color: "#9a6700" },
  { key: "tenx", label: "10x Genomics", color: "#64748b" },
];

export const MODALITY_SERIES: { key: string; label: string; color: string }[] =
  [
    {
      key: "spatial_transcriptomics",
      label: "Transcriptomics",
      color: "#00639a",
    },
    { key: "spatial_proteomics", label: "Proteomics", color: "#6b3fa0" },
  ];

export function depositionYear(d: Dataset): number | null {
  const y =
    typeof d.deposition_year === "number"
      ? d.deposition_year
      : Number(d.deposition_year);
  return Number.isFinite(y) && y > 0 ? y : null;
}

export interface CountRow {
  key: string;
  count: number;
}

// Counts by an arbitrary key, sorted descending; optionally capped to top N.
export function countBy(
  datasets: Dataset[],
  keyFn: (d: Dataset) => string,
  top = 0,
): CountRow[] {
  const m = new Map<string, number>();
  for (const d of datasets) {
    const k = keyFn(d);
    m.set(k, (m.get(k) || 0) + 1);
  }
  const rows = [...m.entries()]
    .map(([key, count]) => ({ key, count }))
    .sort((a, b) => b.count - a.count);
  return top > 0 ? rows.slice(0, top) : rows;
}

export interface GrowthSeries {
  key: string;
  label: string;
  color: string;
  values: number[]; // cumulative count at each year in `years`
}

export interface Growth {
  years: number[];
  series: GrowthSeries[];
  annualTotals: number[]; // datasets deposited in each year (non-cumulative)
  covered: number; // datasets with a deposition year
  total: number;
}

// Cumulative growth over years, stacked by the given ordered groups. Datasets
// without a deposition year are excluded (reported via `covered`).
export function growth(
  datasets: Dataset[],
  groupFn: (d: Dataset) => string,
  groups: { key: string; label: string; color: string }[],
): Growth {
  const dated = datasets
    .map((d) => ({ d, year: depositionYear(d) }))
    .filter((r): r is { d: Dataset; year: number } => r.year !== null);
  const years =
    dated.length === 0
      ? []
      : (() => {
          const min = Math.min(...dated.map((r) => r.year));
          const max = Math.max(...dated.map((r) => r.year));
          return Array.from({ length: max - min + 1 }, (_, i) => min + i);
        })();
  const yearIndex = new Map(years.map((y, i) => [y, i]));

  // per-group annual additions, then accumulate
  const annual: Record<string, number[]> = {};
  for (const g of groups) annual[g.key] = years.map(() => 0);
  const annualTotals = years.map(() => 0);
  for (const { d, year } of dated) {
    const gi = yearIndex.get(year)!;
    const gk = groupFn(d);
    if (annual[gk]) annual[gk][gi] += 1;
    annualTotals[gi] += 1;
  }
  const series: GrowthSeries[] = groups.map((g) => {
    let run = 0;
    const values = annual[g.key].map((n) => (run += n));
    return { key: g.key, label: g.label, color: g.color, values };
  });
  return {
    years,
    series,
    annualTotals,
    covered: dated.length,
    total: datasets.length,
  };
}
