import type { Growth } from "../../lib/stats";

// Cumulative stacked-area growth over years. Hand-rolled SVG, no chart library.
const W = 720;
const H = 340;
const ML = 44;
const MR = 14;
const MT = 14;
const MB = 30;
const PW = W - ML - MR;
const PH = H - MT - MB;

function niceTicks(max: number, count = 4): number[] {
  if (max <= 0) return [0];
  const raw = max / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step =
    [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || mag;
  const ticks: number[] = [];
  for (let v = 0; v <= max + 1e-9; v += step) ticks.push(Math.round(v));
  return ticks;
}

export default function StackedAreaChart({
  growth,
  unitLabel = "datasets",
}: {
  growth: Growth;
  unitLabel?: string;
}) {
  const { years, series } = growth;
  const n = years.length;
  if (n === 0) return <p className="resultline">No dated records to chart.</p>;

  const maxY =
    Math.max(
      1,
      ...years.map((_, i) => series.reduce((s, se) => s + se.values[i], 0)),
    ) || 1;
  const ticks = niceTicks(maxY);
  const top = ticks[ticks.length - 1];

  const x = (i: number) => (n === 1 ? ML + PW / 2 : ML + (i / (n - 1)) * PW);
  const y = (v: number) => MT + PH - (v / top) * PH;

  // stack the cumulative series bottom-to-top
  const lower = years.map(() => 0);
  const areas = series.map((se) => {
    const upper = se.values.map((v, i) => lower[i] + v);
    const pts =
      upper.map((v, i) => `${x(i)},${y(v)}`).join(" ") +
      " " +
      [...lower]
        .map((v, i) => `${x(i)},${y(v)}`)
        .reverse()
        .join(" ");
    for (let i = 0; i < lower.length; i++) lower[i] = upper[i];
    return { key: se.key, color: se.color, points: pts };
  });

  const totalNow = series.reduce((s, se) => s + se.values[n - 1], 0);

  return (
    <svg
      className="growth-chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`Cumulative ${unitLabel} deposited per year, stacked by category`}
    >
      <title>Cumulative growth per year</title>
      <desc>
        {`${totalNow} ${unitLabel} with a deposition year, from ${years[0]} to ${years[n - 1]}.`}
      </desc>
      {/* y gridlines + labels */}
      {ticks.map((t) => (
        <g key={t}>
          <line x1={ML} y1={y(t)} x2={W - MR} y2={y(t)} className="grid-line" />
          <text x={ML - 6} y={y(t) + 3} className="axis-label" textAnchor="end">
            {t}
          </text>
        </g>
      ))}
      {/* stacked areas */}
      {areas.map((a) => (
        <polygon
          key={a.key}
          points={a.points}
          fill={a.color}
          fillOpacity={0.85}
        />
      ))}
      {/* x labels */}
      {years.map((yr, i) => (
        <text
          key={yr}
          x={x(i)}
          y={H - 10}
          className="axis-label"
          textAnchor="middle"
        >
          {yr}
        </text>
      ))}
    </svg>
  );
}
