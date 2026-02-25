interface StorageUsageBarProps {
  usedBytes: number;
  capBytes: number;
  title?: string;
}

type UsageTone = 'green' | 'orange' | 'red';

function formatMb(valueBytes: number): string {
  return `${(valueBytes / (1024 * 1024)).toFixed(1)} MB`;
}

function resolveTone(percent: number): UsageTone {
  if (percent >= 100) {
    return 'red';
  }
  if (percent >= 90) {
    return 'orange';
  }
  return 'green';
}

function resolveToneLabel(tone: UsageTone): string {
  if (tone === 'red') {
    return 'Over cap';
  }
  if (tone === 'orange') {
    return 'Near cap';
  }
  return 'Healthy';
}

export function StorageUsageBar({ usedBytes, capBytes, title = 'Results storage' }: StorageUsageBarProps) {
  const usagePercentRaw = capBytes > 0 ? (usedBytes / capBytes) * 100 : 0;
  const usagePercent = Number.isFinite(usagePercentRaw) ? usagePercentRaw : 0;
  const fillPercent = Math.max(0, Math.min(100, usagePercent));
  const tone = resolveTone(usagePercent);

  return (
    <article className={`results-card storage-usage-card storage-usage-${tone}`}>
      <div className="storage-usage-head">
        <h3>{title}</h3>
        <span className={`storage-usage-pill storage-usage-pill-${tone}`}>{resolveToneLabel(tone)}</span>
      </div>
      <div className="storage-usage-track" role="img" aria-label={`${title}: ${usagePercent.toFixed(1)}% used`}>
        <span className={`storage-usage-fill storage-usage-fill-${tone}`} style={{ width: `${fillPercent}%` }} />
      </div>
      <p className="storage-usage-meta">
        <strong>{formatMb(usedBytes)}</strong> / {formatMb(capBytes)} ({usagePercent.toFixed(1)}%)
      </p>
    </article>
  );
}
