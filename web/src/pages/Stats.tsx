import { useState } from "react";
import { Link } from "react-router-dom";
import { useSite } from "../data";
import {
  SOURCES,
  MODALITY_SERIES,
  detectSource,
  countBy,
  growth,
} from "../lib/stats";
import StackedAreaChart from "../components/charts/StackedAreaChart";
import ColumnChart from "../components/charts/ColumnChart";
import BarChart, { type BarRow } from "../components/charts/BarChart";
import Legend from "../components/charts/Legend";

const CURATION = [
  { key: "verified", label: "verified", color: "var(--verified)" },
  { key: "human_reviewed", label: "human_reviewed", color: "var(--reviewed)" },
  { key: "machine_draft", label: "machine_draft", color: "var(--draft)" },
];
const ACCESS = [
  { key: "open", label: "open", color: "var(--verified)" },
  { key: "on_request", label: "on_request", color: "var(--draft)" },
  { key: "controlled", label: "controlled", color: "#9a2222" },
];

export default function Stats() {
  const { counts, facets, datasets } = useSite();
  const [by, setBy] = useState<"source" | "modality">("source");

  const total = datasets.length;
  const verified = datasets.filter(
    (d) => d.curation_status === "verified",
  ).length;

  const g =
    by === "source"
      ? growth(datasets, detectSource, SOURCES)
      : growth(datasets, (d) => d.modality, MODALITY_SERIES);
  const legendItems = (by === "source" ? SOURCES : MODALITY_SERIES).map(
    (s) => ({
      label: s.label,
      color: s.color,
    }),
  );

  // category breakdowns
  const sourceRows: BarRow[] = SOURCES.map((s) => ({
    label: s.label,
    color: s.color,
    count: datasets.filter((d) => detectSource(d) === s.key).length,
  }))
    .filter((r) => r.count > 0)
    .sort((a, b) => b.count - a.count);

  const cancerRows: BarRow[] = countBy(
    datasets,
    (d) => d.cancer_type_name || d.cancer_type,
    12,
  ).map((r) => ({ label: r.key, count: r.count }));

  const platformRows: BarRow[] = countBy(datasets, (d) => d.platform).map(
    (r) => ({
      label: r.key,
      count: r.count,
    }),
  );

  const modalityRows: BarRow[] = MODALITY_SERIES.map((s) => ({
    label: s.label,
    color: s.color,
    count: datasets.filter((d) => d.modality === s.key).length,
  }));

  const orderRows = (
    order: { key: string; label: string; color: string }[],
    field: (d: (typeof datasets)[number]) => string,
  ): BarRow[] =>
    order
      .map((o) => ({
        label: o.label,
        color: o.color,
        count: datasets.filter((d) => field(d) === o.key).length,
      }))
      .filter((r) => r.count > 0);

  const tiles: [string, number | string][] = [
    ["Datasets", counts.datasets],
    ["Cancer types", counts.cancer_types],
    ["Platforms", facets.platform.length],
    ["Sources", sourceRows.length],
    ["Verified", `${Math.round((verified / total) * 100)}%`],
  ];

  return (
    <main className="wrap stats-page">
      <h1 className="page-title">Catalog statistics</h1>

      <dl className="stat-tiles">
        {tiles.map(([label, val]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{val}</dd>
          </div>
        ))}
      </dl>

      <section className="band">
        <div className="band-head">
          <h2 className="band-title">Growth over time</h2>
          <div
            className="seg-toggle"
            role="group"
            aria-label="Break down growth by"
          >
            {(["source", "modality"] as const).map((k) => (
              <button
                key={k}
                type="button"
                className={"seg-btn" + (by === k ? " is-active" : "")}
                onClick={() => setBy(k)}
              >
                by {k}
              </button>
            ))}
          </div>
        </div>
        <p className="chart-caption">
          Cumulative datasets by repository deposition year. {g.covered} of{" "}
          {g.total} records carry a deposition year; HTAN, CELLxGENE and 10x
          expose no public deposition date and are omitted from the timeline.
        </p>
        <StackedAreaChart growth={g} />
        <Legend items={legendItems} />
        <h3 className="chart-subtitle">New datasets deposited each year</h3>
        <ColumnChart years={g.years} values={g.annualTotals} />
      </section>

      <section className="band">
        <h2 className="band-title">By source repository</h2>
        <BarChart rows={sourceRows} total={total} />
      </section>

      <div className="stats-grid">
        <section className="band">
          <h2 className="band-title">Top cancer types</h2>
          <BarChart rows={cancerRows} total={total} />
        </section>
        <section className="band">
          <h2 className="band-title">By platform</h2>
          <BarChart rows={platformRows} total={total} />
        </section>
        <section className="band">
          <h2 className="band-title">By modality</h2>
          <BarChart rows={modalityRows} total={total} />
        </section>
        <section className="band">
          <h2 className="band-title">By curation tier</h2>
          <BarChart
            rows={orderRows(CURATION, (d) => d.curation_status)}
            total={total}
          />
        </section>
        <section className="band">
          <h2 className="band-title">By access</h2>
          <BarChart rows={orderRows(ACCESS, (d) => d.access)} total={total} />
        </section>
      </div>

      <p className="prose">
        <Link to="/catalog" className="acc">
          Explore the catalog &rarr;
        </Link>
      </p>
    </main>
  );
}
