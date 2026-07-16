// Annual (non-cumulative) additions per year as vertical bars. Hand-rolled SVG.
const W = 720;
const H = 200;
const ML = 40;
const MR = 14;
const MT = 12;
const MB = 26;
const PW = W - ML - MR;
const PH = H - MT - MB;

export default function ColumnChart({
  years,
  values,
  color = "var(--primary)",
  unitLabel = "datasets",
}: {
  years: number[];
  values: number[];
  color?: string;
  unitLabel?: string;
}) {
  const n = years.length;
  if (n === 0) return null;
  const max = Math.max(1, ...values);
  const band = PW / n;
  const bw = band * 0.62;
  const y = (v: number) => MT + PH - (v / max) * PH;

  return (
    <svg
      className="growth-chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`New ${unitLabel} deposited each year`}
    >
      <title>Datasets deposited per year</title>
      <line
        x1={ML}
        y1={MT + PH}
        x2={W - MR}
        y2={MT + PH}
        className="grid-line"
      />
      {values.map((v, i) => {
        const cx = ML + band * i + (band - bw) / 2;
        return (
          <g key={years[i]}>
            <rect
              x={cx}
              y={y(v)}
              width={bw}
              height={MT + PH - y(v)}
              fill={color}
              rx={2}
            />
            {v > 0 && (
              <text
                x={cx + bw / 2}
                y={y(v) - 4}
                className="axis-label"
                textAnchor="middle"
              >
                {v}
              </text>
            )}
            <text
              x={cx + bw / 2}
              y={H - 8}
              className="axis-label"
              textAnchor="middle"
            >
              {years[i]}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
