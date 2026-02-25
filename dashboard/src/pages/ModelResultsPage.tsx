import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import type {
  KpiMetricSummary,
  ResultsCompareIndicator,
  ResultsComparePayload,
  ResultsFileManifestEntry,
  ResultsRunDetail,
  ResultsRunStatus,
  ResultsRunSummary,
  ResultsStorageSummary
} from '../../shared/types';
import type { EChartsOption } from 'echarts';
import { EChart } from '../components/EChart';
import { LoadingSkeleton, LoadingSkeletonGroup } from '../components/LoadingSkeleton';
import { StorageUsageBar } from '../components/StorageUsageBar';
import {
  API_RETRY_DELAY_MS,
  deleteResultsRun,
  fetchResultsCompare,
  fetchResultsRunDetail,
  fetchResultsRunFiles,
  fetchResultsRuns,
  fetchResultsStorageSummary,
  isRetryableApiError
} from '../lib/api';

const RUN_LIMIT = 5;
const PROTECTED_RESULTS_RUN_IDS = new Set(['v0-output', 'v1.0-output', 'v2.0-output', 'v3.7-output']);

type CompareWindow = 'post200' | 'tail120' | 'full';
type SmoothWindow = 0 | 3 | 12;
const SPIN_UP_CUTOFF_TICKS = 200;

function isProtectedResultsRun(runId: string): boolean {
  return PROTECTED_RESULTS_RUN_IDS.has(runId.trim());
}

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

function compareWindowLabel(window: CompareWindow): string {
  if (window === 'tail120') {
    return 'Tail 120 months';
  }
  if (window === 'full') {
    return 'Full history';
  }
  return `Post spin-up (t >= ${SPIN_UP_CUTOFF_TICKS})`;
}

interface ModelResultsPageProps {
  canWrite: boolean;
}

export function ModelResultsPage({ canWrite }: ModelResultsPageProps) {
  const [searchParams] = useSearchParams();
  const [runs, setRuns] = useState<ResultsRunSummary[]>([]);
  const [focusedRunId, setFocusedRunId] = useState<string>('');
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [detail, setDetail] = useState<ResultsRunDetail | null>(null);
  const [manifest, setManifest] = useState<ResultsFileManifestEntry[]>([]);
  const [selectedIndicatorIds, setSelectedIndicatorIds] = useState<string[]>([]);
  const [comparePayload, setComparePayload] = useState<ResultsComparePayload | null>(null);
  const [compareWindow, setCompareWindow] = useState<CompareWindow>('post200');
  const [smoothWindow, setSmoothWindow] = useState<SmoothWindow>(0);
  const [loadError, setLoadError] = useState<string>('');
  const [selectionError, setSelectionError] = useState<string>('');
  const [isLoadingRuns, setIsLoadingRuns] = useState<boolean>(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState<boolean>(false);
  const [isLoadingCompare, setIsLoadingCompare] = useState<boolean>(false);
  const [isDeletingRunId, setIsDeletingRunId] = useState<string>('');
  const [storageSummary, setStorageSummary] = useState<ResultsStorageSummary | null>(null);

  const loadRuns = useCallback(async () => {
    setLoadError('');
    setIsLoadingRuns(true);

    try {
      const [runsPayload, storagePayload] = await Promise.all([fetchResultsRuns(), fetchResultsStorageSummary()]);
      setRuns(runsPayload);
      setStorageSummary(storagePayload);
      const firstRun = runsPayload[0]?.runId ?? '';
      setFocusedRunId((current) => (runsPayload.some((run) => run.runId === current) ? current : firstRun));
      setSelectedRunIds((current) => {
        if (current.length > 0) {
          const filtered = current.filter((runId) => runsPayload.some((run) => run.runId === runId));
          if (filtered.length > 0) {
            return filtered;
          }
        }
        return firstRun ? [firstRun] : [];
      });
    } finally {
      setIsLoadingRuns(false);
    }
  }, []);

  const refreshStorageSummary = useCallback(async () => {
    try {
      const payload = await fetchResultsStorageSummary();
      setStorageSummary(payload);
    } catch (error) {
      if (!isRetryableApiError(error)) {
        setLoadError((error as Error).message);
      }
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    let retryTimer: number | undefined;

    const loadRunsWithRetry = async () => {
      try {
        await loadRuns();
      } catch (error) {
        if (cancelled) {
          return;
        }
        if (isRetryableApiError(error)) {
          retryTimer = window.setTimeout(() => {
            void loadRunsWithRetry();
          }, API_RETRY_DELAY_MS);
          return;
        }
        setLoadError((error as Error).message);
      }
    };

    void loadRunsWithRetry();

    return () => {
      cancelled = true;
      if (retryTimer !== undefined) {
        window.clearTimeout(retryTimer);
      }
    };
  }, [loadRuns]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void refreshStorageSummary();
    }, 5000);

    return () => {
      window.clearInterval(interval);
    };
  }, [refreshStorageSummary]);

  useEffect(() => {
    const requestedRunId = searchParams.get('runId')?.trim();
    if (!requestedRunId || runs.length === 0) {
      return;
    }

    if (!runs.some((run) => run.runId === requestedRunId)) {
      return;
    }

    setFocusedRunId(requestedRunId);
    setSelectedRunIds([requestedRunId]);
  }, [runs, searchParams]);

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
  const overlayIndicators = comparePayload?.indicators ?? [];
  const showRunsSkeleton = isLoadingRuns && runs.length === 0;
  const showRunsRefreshing = isLoadingRuns && runs.length > 0;
  const showIndicatorsSkeleton = isLoadingDetail && availableIndicators.length === 0;
  const showIndicatorsRefreshing = isLoadingDetail && availableIndicators.length > 0;
  const showKpiSkeleton = isLoadingDetail && sortedKpis.length === 0;
  const showKpiRefreshing = isLoadingDetail && sortedKpis.length > 0;
  const showOverlaySkeleton = isLoadingCompare && overlayIndicators.length === 0;
  const showOverlayRefreshing = isLoadingCompare && overlayIndicators.length > 0;
  const showManifestSkeleton = isLoadingDetail && manifest.length === 0;
  const showManifestRefreshing = isLoadingDetail && manifest.length > 0;

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

  const deleteRun = async (runId: string) => {
    if (!canWrite) {
      return;
    }
    if (isProtectedResultsRun(runId)) {
      setLoadError(`Run "${runId}" is protected and cannot be deleted from Model Results.`);
      return;
    }
    const confirmed = window.confirm(`Delete run "${runId}"? This permanently removes its Results folder.`);
    if (!confirmed) {
      return;
    }

    setSelectionError('');
    setLoadError('');
    setIsDeletingRunId(runId);
    try {
      await deleteResultsRun(runId);
      await loadRuns();
    } catch (error) {
      setLoadError((error as Error).message);
    } finally {
      setIsDeletingRunId('');
    }
  };

  return (
    <section className="results-layout">
      {loadError && <p className="error-banner">{loadError}</p>}
      {selectionError && <p className="waiting-banner">{selectionError}</p>}
      {storageSummary && <StorageUsageBar usedBytes={storageSummary.usedBytes} capBytes={storageSummary.capBytes} />}

      <div className="results-grid">
        <aside className="results-panel">
          <div className="results-panel-header">
            <h2>Runs</h2>
            <p>Newest first</p>
          </div>
          {showRunsRefreshing && (
            <LoadingSkeleton
              as="span"
              className="loading-skeleton-pill section-loading-row"
              ariaLabel="Refreshing runs"
            />
          )}
          {showRunsSkeleton ? (
            <LoadingSkeletonGroup
              className="run-list-skeleton"
              count={4}
              itemClassName="loading-skeleton-card run-item-skeleton"
              ariaLabel="Loading runs"
            />
          ) : (
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
                    {canWrite && (
                      <button
                        type="button"
                        className="danger-button"
                        disabled={isDeletingRunId === run.runId || isProtectedResultsRun(run.runId)}
                        onClick={() => void deleteRun(run.runId)}
                        title={isProtectedResultsRun(run.runId) ? 'Protected run cannot be deleted.' : undefined}
                      >
                        {isProtectedResultsRun(run.runId)
                          ? 'Protected'
                          : isDeletingRunId === run.runId
                            ? 'Deleting...'
                            : 'Delete'}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
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
              Window: <strong>{compareWindowLabel(compareWindow)}</strong> | Smoothing:{' '}
              <strong>{smoothWindow === 0 ? 'Off' : `${smoothWindow}-month moving average`}</strong>
            </p>
            <div className="results-controls">
              <label>
                Window
                <select
                  value={compareWindow}
                  onChange={(event) => setCompareWindow(event.target.value as CompareWindow)}
                >
                  <option value="post200">post200</option>
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
            {showIndicatorsRefreshing && (
              <LoadingSkeleton
                as="span"
                className="loading-skeleton-pill section-loading-row"
                ariaLabel="Refreshing indicators"
              />
            )}
            {showIndicatorsSkeleton ? (
              <LoadingSkeletonGroup
                className="indicator-grid"
                count={6}
                itemClassName="loading-skeleton-card indicator-item-skeleton"
                ariaLabel="Loading indicators"
              />
            ) : (
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
            )}
          </article>

          <article className="results-card">
            <h3>KPI Summary (tail_120)</h3>
            {showKpiRefreshing && (
              <LoadingSkeleton
                as="span"
                className="loading-skeleton-pill section-loading-row"
                ariaLabel="Refreshing KPI summary"
              />
            )}
            {showKpiSkeleton ? (
              <LoadingSkeletonGroup
                className="kpi-grid"
                count={4}
                itemClassName="loading-skeleton-card kpi-card-skeleton"
                ariaLabel="Loading KPI summary"
              />
            ) : (
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
            )}
          </article>

          <article className="results-card">
            <h3>Indicator Overlays</h3>
            {showOverlayRefreshing && (
              <LoadingSkeleton
                as="span"
                className="loading-skeleton-pill section-loading-row"
                ariaLabel="Refreshing indicator overlays"
              />
            )}
            {showOverlaySkeleton ? (
              <LoadingSkeletonGroup
                className="overlay-grid"
                count={2}
                itemClassName="loading-skeleton-card overlay-card-skeleton"
                ariaLabel="Loading indicator overlays"
              />
            ) : (
              <div className="overlay-grid">
                {overlayIndicators.map((indicatorPayload) => (
                  <div key={indicatorPayload.indicator.id} className="overlay-card">
                    <h4>{indicatorPayload.indicator.title}</h4>
                    <EChart option={buildOverlayOption(indicatorPayload)} className="chart" />
                  </div>
                ))}
              </div>
            )}
          </article>

          <article className="results-card">
            <h3>File Manifest ({focusedRunId || 'No run selected'})</h3>
            {showManifestRefreshing && (
              <LoadingSkeleton
                as="span"
                className="loading-skeleton-pill section-loading-row"
                ariaLabel="Refreshing file manifest"
              />
            )}
            {showManifestSkeleton ? (
              <LoadingSkeletonGroup
                className="manifest-skeleton"
                count={6}
                itemClassName="manifest-skeleton-row"
                ariaLabel="Loading file manifest"
              />
            ) : (
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
            )}
          </article>
        </div>
      </div>
    </section>
  );
}
