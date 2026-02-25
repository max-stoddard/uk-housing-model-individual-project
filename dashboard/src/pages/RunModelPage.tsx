import { useEffect, useMemo, useState } from 'react';
import type {
  KpiMetricSummary,
  ResultsCompareIndicator,
  ResultsComparePayload,
  ResultsFileManifestEntry,
  ResultsRunDetail,
  ResultsRunStatus,
  ResultsRunSummary
} from '../../shared/types';
import type { EChartsOption } from 'echarts';
import { EChart } from '../components/EChart';
import {
  API_RETRY_DELAY_MS,
  fetchResultsCompare,
  fetchResultsRunDetail,
  fetchResultsRunFiles,
  fetchResultsRuns,
  isRetryableApiError
} from '../lib/api';

const RUN_LIMIT = 5;

type CompareWindow = 'tail120' | 'full';
type SmoothWindow = 0 | 3 | 12;

function formatNumber(value: number | null, units: string): string {
  if (value === null) {
    return 'n/a';
  }

  if (units === 'GBP') {
    return `£${value.toLocaleString('en-GB', { maximumFractionDigits: 0 })}`;
  }
  if (units === '%' || units === 'rate') {
    return value.toLocaleString('en-GB', { maximumFractionDigits: 2 });
  }
  if (units === 'count' || units === 'count/month') {
    return value.toLocaleString('en-GB', { maximumFractionDigits: 0 });
  }
  return value.toLocaleString('en-GB', { maximumFractionDigits: 3 });
}

function formatSigned(value: number | null): string {
  if (value === null) {
    return 'n/a';
  }
  return `${value >= 0 ? '+' : ''}${value.toLocaleString('en-GB', { maximumFractionDigits: 3 })}`;
}

function statusClass(status: ResultsRunStatus): string {
  switch (status) {
    case 'complete':
      return 'status-pill complete';
    case 'partial':
      return 'status-pill partial';
    default:
      return 'status-pill invalid';
  }
}

function coverageClass(status: ResultsFileManifestEntry['coverageStatus']): string {
  switch (status) {
    case 'supported':
      return 'coverage-pill supported';
    case 'empty':
      return 'coverage-pill empty';
    case 'error':
      return 'coverage-pill error';
    default:
      return 'coverage-pill unsupported';
  }
}

function buildOverlayOption(indicatorPayload: ResultsCompareIndicator): EChartsOption {
  const xValues = indicatorPayload.seriesByRun[0]?.points.map((point) => String(point.modelTime)) ?? [];
  const series = indicatorPayload.seriesByRun.map((runSeries) => ({
    name: runSeries.runId,
    type: 'line' as const,
    showSymbol: false,
    smooth: false,
    connectNulls: false,
    data: runSeries.points.map((point) => point.value)
  }));

  return {
    animation: false,
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value: unknown) => {
        if (typeof value !== 'number' || Number.isNaN(value)) {
          return 'n/a';
        }
        return formatNumber(value, indicatorPayload.indicator.units);
      }
    },
    legend: {
      top: 4
    },
    grid: {
      left: 72,
      right: 20,
      top: 48,
      bottom: 42
    },
    xAxis: {
      type: 'category',
      data: xValues,
      name: 'Model Time (months)',
      nameLocation: 'middle',
      nameGap: 30,
      axisLabel: {
        formatter: (value: string, index: number) => {
          return index % 120 === 0 ? value : '';
        }
      }
    },
    yAxis: {
      type: 'value',
      name: indicatorPayload.indicator.units,
      nameLocation: 'middle',
      nameGap: 52,
      scale: true
    },
    series
  };
}

function sortKpis(kpis: KpiMetricSummary[]): KpiMetricSummary[] {
  return [...kpis].sort((left, right) => left.title.localeCompare(right.title));
}

export function RunModelPage() {
  const [runs, setRuns] = useState<ResultsRunSummary[]>([]);
  const [focusedRunId, setFocusedRunId] = useState<string>('');
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [detail, setDetail] = useState<ResultsRunDetail | null>(null);
  const [manifest, setManifest] = useState<ResultsFileManifestEntry[]>([]);
  const [selectedIndicatorIds, setSelectedIndicatorIds] = useState<string[]>([]);
  const [comparePayload, setComparePayload] = useState<ResultsComparePayload | null>(null);
  const [compareWindow, setCompareWindow] = useState<CompareWindow>('tail120');
  const [smoothWindow, setSmoothWindow] = useState<SmoothWindow>(0);
  const [loadError, setLoadError] = useState<string>('');
  const [selectionError, setSelectionError] = useState<string>('');
  const [isLoadingRuns, setIsLoadingRuns] = useState<boolean>(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState<boolean>(false);
  const [isLoadingCompare, setIsLoadingCompare] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    let retryTimer: number | undefined;

    const loadRuns = async () => {
      setLoadError('');
      setIsLoadingRuns(true);

      try {
        const payload = await fetchResultsRuns();
        if (cancelled) {
          return;
        }

        setRuns(payload);
        const firstRun = payload[0]?.runId ?? '';
        setFocusedRunId((current) => current || firstRun);
        setSelectedRunIds((current) => {
          if (current.length > 0) {
            return current.filter((runId) => payload.some((run) => run.runId === runId));
          }
          return firstRun ? [firstRun] : [];
        });
      } catch (error) {
        if (cancelled) {
          return;
        }

        if (isRetryableApiError(error)) {
          retryTimer = window.setTimeout(() => {
            void loadRuns();
          }, API_RETRY_DELAY_MS);
          return;
        }
        setLoadError((error as Error).message);
      } finally {
        if (!cancelled) {
          setIsLoadingRuns(false);
        }
      }
    };

    void loadRuns();

    return () => {
      cancelled = true;
      if (retryTimer !== undefined) {
        window.clearTimeout(retryTimer);
      }
    };
  }, []);

  useEffect(() => {
    if (!focusedRunId) {
      setDetail(null);
      setManifest([]);
      return;
    }

    let cancelled = false;
    setIsLoadingDetail(true);
    setLoadError('');

    void Promise.all([fetchResultsRunDetail(focusedRunId), fetchResultsRunFiles(focusedRunId)])
      .then(([runDetail, runFiles]) => {
        if (cancelled) {
          return;
        }
        setDetail(runDetail);
        setManifest(runFiles);
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setLoadError((error as Error).message);
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingDetail(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [focusedRunId]);

  useEffect(() => {
    if (!detail) {
      setSelectedIndicatorIds([]);
      return;
    }

    const availableIds = detail.indicators.filter((indicator) => indicator.available).map((indicator) => indicator.id);
    const availableSet = new Set(availableIds);
    const defaultCore = detail.indicators
      .filter((indicator) => indicator.available && indicator.source === 'core_indicator')
      .map((indicator) => indicator.id);
    const defaultAny = availableIds.slice(0, 8);

    setSelectedIndicatorIds((current) => {
      const filtered = current.filter((id) => availableSet.has(id));
      if (filtered.length > 0) {
        return filtered;
      }
      if (defaultCore.length > 0) {
        return defaultCore;
      }
      return defaultAny;
    });
  }, [detail]);

  useEffect(() => {
    if (selectedRunIds.length === 0 || selectedIndicatorIds.length === 0) {
      setComparePayload(null);
      return;
    }

    let cancelled = false;
    setIsLoadingCompare(true);
    setLoadError('');

    void fetchResultsCompare(selectedRunIds, selectedIndicatorIds, compareWindow, smoothWindow)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setComparePayload(payload);
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setLoadError((error as Error).message);
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingCompare(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedRunIds, selectedIndicatorIds, compareWindow, smoothWindow]);

  const availableIndicators = useMemo(() => detail?.indicators ?? [], [detail]);
  const sortedKpis = useMemo(() => sortKpis(detail?.kpiSummary ?? []), [detail]);
  const selectedRunSet = useMemo(() => new Set(selectedRunIds), [selectedRunIds]);

  const toggleRunSelection = (runId: string) => {
    setSelectionError('');
    setSelectedRunIds((current) => {
      if (current.includes(runId)) {
        if (current.length === 1) {
          setSelectionError('At least one run must remain selected.');
          return current;
        }
        return current.filter((id) => id !== runId);
      }

      if (current.length >= RUN_LIMIT) {
        setSelectionError(`Overlay limit reached (${RUN_LIMIT} runs).`);
        return current;
      }
      return [...current, runId];
    });
  };

  const toggleIndicatorSelection = (indicatorId: string) => {
    setSelectionError('');
    setSelectedIndicatorIds((current) => {
      if (current.includes(indicatorId)) {
        if (current.length === 1) {
          setSelectionError('Select at least one indicator.');
          return current;
        }
        return current.filter((id) => id !== indicatorId);
      }
      return [...current, indicatorId];
    });
  };

  return (
    <section className="results-layout">
      {loadError && <p className="error-banner">{loadError}</p>}
      {selectionError && <p className="waiting-banner">{selectionError}</p>}

      <div className="results-grid">
        <aside className="results-panel">
          <div className="results-panel-header">
            <h2>Runs</h2>
            <p>Newest first</p>
          </div>
          {isLoadingRuns && <p className="loading-banner">Loading runs...</p>}
          <ul className="run-list">
            {runs.map((run) => (
              <li key={run.runId} className={`run-item ${focusedRunId === run.runId ? 'focused' : ''}`}>
                <label className="run-select">
                  <input
                    type="checkbox"
                    checked={selectedRunSet.has(run.runId)}
                    onChange={() => toggleRunSelection(run.runId)}
                  />
                  <span>{run.runId}</span>
                </label>
                <button
                  type="button"
                  className="run-focus-btn"
                  onClick={() => setFocusedRunId(run.runId)}
                >
                  Focus
                </button>
                <div className="run-meta">
                  <span className={statusClass(run.status)}>{run.status}</span>
                  <span>{(run.sizeBytes / 1024 / 1024).toFixed(1)} MB</span>
                </div>
                <p>
                  Coverage: {run.parseCoverage.supportedCount}/{run.parseCoverage.requiredCount} supported
                </p>
              </li>
            ))}
          </ul>
        </aside>

        <div className="results-main">
          <article className="results-card">
            <div className="results-card-head">
              <h2>Run Explorer</h2>
              {detail && <span className={statusClass(detail.status)}>{detail.status}</span>}
            </div>
            <p>
              Selected runs: <strong>{selectedRunIds.join(', ') || 'none'}</strong>
            </p>
            <p>
              Window: <strong>{compareWindow === 'tail120' ? 'Tail 120 months' : 'Full history'}</strong> | Smoothing:{' '}
              <strong>{smoothWindow === 0 ? 'Off' : `${smoothWindow}-month moving average`}</strong>
            </p>
            <div className="results-controls">
              <label>
                Window
                <select
                  value={compareWindow}
                  onChange={(event) => setCompareWindow(event.target.value as CompareWindow)}
                >
                  <option value="tail120">tail120</option>
                  <option value="full">full</option>
                </select>
              </label>
              <label>
                Smoothing
                <select
                  value={String(smoothWindow)}
                  onChange={(event) => setSmoothWindow(Number.parseInt(event.target.value, 10) as SmoothWindow)}
                >
                  <option value="0">off</option>
                  <option value="3">3</option>
                  <option value="12">12</option>
                </select>
              </label>
            </div>
          </article>

          <article className="results-card">
            <h3>Indicators</h3>
            <p>Select indicators for overlay charts.</p>
            <div className="indicator-grid">
              {availableIndicators.map((indicator) => (
                <label
                  key={indicator.id}
                  className={`indicator-item ${indicator.available ? '' : 'disabled'}`}
                >
                  <input
                    type="checkbox"
                    disabled={!indicator.available}
                    checked={selectedIndicatorIds.includes(indicator.id)}
                    onChange={() => toggleIndicatorSelection(indicator.id)}
                  />
                  <span>{indicator.title}</span>
                  <small>
                    {indicator.units} · {indicator.source}
                  </small>
                </label>
              ))}
            </div>
          </article>

          <article className="results-card">
            <h3>KPI Summary (tail_120)</h3>
            {isLoadingDetail && <p className="loading-banner">Loading KPI summary...</p>}
            <div className="kpi-grid">
              {sortedKpis.map((kpi) => (
                <div key={kpi.indicatorId} className="kpi-card">
                  <p className="kpi-title">{kpi.title}</p>
                  <p className="kpi-value">Latest: {formatNumber(kpi.latest, kpi.units)}</p>
                  <p>Mean: {formatNumber(kpi.mean, kpi.units)}</p>
                  <p>YoY Δ: {formatSigned(kpi.yoyDelta)}</p>
                </div>
              ))}
            </div>
          </article>

          <article className="results-card">
            <h3>Indicator Overlays</h3>
            {isLoadingCompare && <p className="loading-banner">Loading overlays...</p>}
            <div className="overlay-grid">
              {comparePayload?.indicators.map((indicatorPayload) => (
                <div key={indicatorPayload.indicator.id} className="overlay-card">
                  <h4>{indicatorPayload.indicator.title}</h4>
                  <EChart option={buildOverlayOption(indicatorPayload)} className="chart" />
                </div>
              ))}
            </div>
          </article>

          <article className="results-card">
            <h3>File Manifest ({focusedRunId || 'No run selected'})</h3>
            {isLoadingDetail && <p className="loading-banner">Loading manifest...</p>}
            <div className="manifest-table-wrap">
              <table className="manifest-table">
                <thead>
                  <tr>
                    <th>File</th>
                    <th>Type</th>
                    <th>Size</th>
                    <th>Coverage</th>
                    <th>Note</th>
                  </tr>
                </thead>
                <tbody>
                  {manifest.map((file) => (
                    <tr key={file.filePath}>
                      <td>{file.fileName}</td>
                      <td>{file.fileType}</td>
                      <td>{(file.sizeBytes / 1024 / 1024).toFixed(2)} MB</td>
                      <td>
                        <span className={coverageClass(file.coverageStatus)}>{file.coverageStatus}</span>
                      </td>
                      <td>{file.note ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}
