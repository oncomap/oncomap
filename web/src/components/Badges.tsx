import {
  ACCESS_LABEL,
  MODALITY_LABEL,
  MODALITY_TIP,
  PLATFORM_DESC,
  STATUS_DESC,
  accessTip,
} from "../lib/format";

// The four header badges, ported from site/app.js. Tooltips use the CSS
// .has-tip / data-tip bubble so no JS tooltip library is needed.

export function ModalityBadge({ modality }: { modality: string }) {
  const key = modality || "unknown";
  const tip = MODALITY_TIP[key] ?? MODALITY_TIP.spatial_transcriptomics;
  return (
    <span
      className={`tag modality--${key} has-tip`}
      data-tip={tip}
      aria-label={tip}
    >
      {MODALITY_LABEL[key] || key}
    </span>
  );
}

export function PlatformTag({ platform }: { platform: string }) {
  const tip = PLATFORM_DESC[platform] || platform;
  return (
    <span className="tag tag--platform has-tip" data-tip={tip} aria-label={tip}>
      {platform}
    </span>
  );
}

export function AccessBadge({ access }: { access: string }) {
  const key = access || "unknown";
  const gated = key !== "open";
  const tip = accessTip(access);
  return (
    <span
      className={`tag access--${key} has-tip`}
      data-tip={tip}
      aria-label={tip}
    >
      {(gated ? "\u{1F512} " : "") + (ACCESS_LABEL[key] || key)}
    </span>
  );
}

export function StatusTag({ status }: { status: string }) {
  const tip = STATUS_DESC[status] || status;
  return (
    <span
      className={`tag status--${status} has-tip`}
      data-tip={tip}
      aria-label={tip}
    >
      {status}
    </span>
  );
}
