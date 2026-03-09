import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type {
  ResultsCompareIndicator,
  ResultsComparePayload,
  ResultsFileManifestEntry,
  ResultsRunDetail,
  ResultsRunStatus,
  ResultsRunSummary
} from '../../../../shared/types';
import type { EChartsOption } from 'echarts';
import { CollapsibleSection } from '../../../components/CollapsibleSection';
import { EChart } from '../../../components/EChart';
import { GroupedCheckboxSections } from '../../../components/GroupedCheckboxSections';
import { LoadingSkeleton, LoadingSkeletonGroup } from '../../../components/LoadingSkeleton';
import {
  API_RETRY_DELAY_MS,
  deleteResultsRun,
  fetchResultsCompare,
  fetchResultsRunDetail,
  fetchResultsRunFiles,
  fetchResultsRuns,
  isRetryableApiError
} from '../../../lib/api';
import {
  KPI_DETAIL_ROWS,
  computeKpiPercentDelta,
  getKpiMetricValue,
  groupIndicatorsBySource,
  resolveActiveIndicatorId,
  resolveManualRunSelection,
  resolveSelectedIndicatorIds,
  sortKpis
} from '../../../lib/manualResultsView';
import { buildExperimentsPath } from '../routeState';
import { DEFAULT_EXPERIMENT_ROUTE_STATE } from '../types';

const PROTECTED_RESULTS_RUN_IDS = new Set(['v0-output', 'v1.0-output', 'v2.0-output', 'v3.0-output', 'v4.0-output']);

type CompareWindow = 'post200' | 'tail120' | 'full';
type SmoothWindow = 0 | 3 | 12;
type ManifestTarget = 'baseline' | 'comparison';
type ManualResultsMode = 'single' | 'compare';

interface ManualResultsViewProps {
  canWrite: boolean;
  requestedBaselineRunId: string;
  requestedComparisonRunId: string;
  onManualSelectionChange: (selection: { baselineRunId: string; comparisonRunId: string }) => void;
  sidebarSubtitle: string;
}

interface InlineInfoTipProps {
  label: string;
  description: string;
}

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

function formatSignedPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return 'n/a';
  }

  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function deltaClassName(value: number | null): string {
  if (value === null || !Number.isFinite(value) || Math.abs(value) < 1e-12) {
    return 'neutral';
  }
  return value > 0 ? 'positive' : 'negative';
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

function getRunRoleLabel(runId: string, baselineRunId: string, comparisonRunId: string): string {
  if (runId === baselineRunId) {
    return 'Baseline';
  }
  if (comparisonRunId && runId === comparisonRunId) {
    return 'Comparison';
  }
  return runId;
}

function InlineInfoTip({ label, description }: InlineInfoTipProps) {
  return (
    <span className="manual-control-header">
      <span>{label}</span>
      <button type="button" className="manual-help-trigger" aria-label={`${label} help`}>
        <span aria-hidden="true" className="manual-help-icon">
          i
        </span>
        <span role="tooltip" className="manual-help-tooltip">
          {description}
        </span>
      </button>
    </span>
  );
}

function buildOverlayOption(
  indicatorPayload: ResultsCompareIndicator,
  baselineRunId: string,
  comparisonRunId: string
): EChartsOption {
  const xValues = indicatorPayload.seriesByRun[0]?.points.map((point) => String(point.modelTime)) ?? [];
  const series = indicatorPayload.seriesByRun.map((runSeries) => ({
    name: getRunRoleLabel(runSeries.runId, baselineRunId, comparisonRunId),
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

export function ManualResultsView({
  canWrite,
  requestedBaselineRunId,
  requestedComparisonRunId,
  onManualSelectionChange,
  sidebarSubtitle
}: ManualResultsViewProps) {
  const [runs, setRuns] = useState<ResultsRunSummary[]>([]);
  const [baselineDetail, setBaselineDetail] = useState<ResultsRunDetail | null>(null);
  const [comparisonDetail, setComparisonDetail] = useState<ResultsRunDetail | null>(null);
  const [manifest, setManifest] = useState<ResultsFileManifestEntry[]>([]);
  const [selectedIndicatorIds, setSelectedIndicatorIds] = useState<string[]>([]);
  const [activeIndicatorId, setActiveIndicatorId] = useState<string>('');
  const [showAllKpiDetails, setShowAllKpiDetails] = useState<boolean>(false);
  const [comparePayload, setComparePayload] = useState<ResultsComparePayload | null>(null);
  const [compareWindow, setCompareWindow] = useState<CompareWindow>('post200');
  const [smoothWindow, setSmoothWindow] = useState<SmoothWindow>(12);
  const [loadError, setLoadError] = useState<string>('');
  const [isLoadingRuns, setIsLoadingRuns] = useState<boolean>(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState<boolean>(false);
  const [isLoadingCompare, setIsLoadingCompare] = useState<boolean>(false);
  const [isLoadingManifest, setIsLoadingManifest] = useState<boolean>(false);
  const [isDeletingRunId, setIsDeletingRunId] = useState<string>('');
  const [isIndicatorSettingsOpen, setIsIndicatorSettingsOpen] = useState<boolean>(false);
  const [manifestTarget, setManifestTarget] = useState<ManifestTarget>('baseline');

  const resolvedSelection = useMemo(
    () => resolveManualRunSelection(runs, requestedBaselineRunId, requestedComparisonRunId),
    [requestedBaselineRunId, requestedComparisonRunId, runs]
  );
  const baselineRunId = resolvedSelection.baselineRunId;
  const comparisonRunId = resolvedSelection.comparisonRunId;
  const mode: ManualResultsMode = comparisonRunId ? 'compare' : 'single';
  const selectedRunIds = useMemo(
    () => (baselineRunId ? (comparisonRunId ? [baselineRunId, comparisonRunId] : [baselineRunId]) : []),
    [baselineRunId, comparisonRunId]
  );
  const manifestRunId = manifestTarget === 'comparison' && comparisonRunId ? comparisonRunId : baselineRunId;
  const manifestTargetLabel = manifestTarget === 'comparison' && comparisonRunId ? 'Comparison' : 'Baseline';

  useEffect(() => {
    if (
      requestedBaselineRunId === baselineRunId &&
      requestedComparisonRunId === comparisonRunId
    ) {
      return;
    }

    onManualSelectionChange({
      baselineRunId,
      comparisonRunId
    });
  }, [
    baselineRunId,
    comparisonRunId,
    onManualSelectionChange,
    requestedBaselineRunId,
    requestedComparisonRunId
  ]);

  const loadRuns = useCallback(async () => {
    setLoadError('');
    setIsLoadingRuns(true);

    try {
      const runsPayload = await fetchResultsRuns();
      setRuns(runsPayload);
    } finally {
      setIsLoadingRuns(false);
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
    if (!comparisonRunId && manifestTarget === 'comparison') {
      setManifestTarget('baseline');
    }
  }, [comparisonRunId, manifestTarget]);

  useEffect(() => {
    if (!baselineRunId) {
      setBaselineDetail(null);
      setComparisonDetail(null);
      return;
    }

    let cancelled = false;
    setIsLoadingDetail(true);
    setLoadError('');

    void Promise.all([
      fetchResultsRunDetail(baselineRunId),
      comparisonRunId ? fetchResultsRunDetail(comparisonRunId) : Promise.resolve(null)
    ])
      .then(([baselinePayload, comparisonPayload]) => {
        if (cancelled) {
          return;
        }
        setBaselineDetail(baselinePayload);
        setComparisonDetail(comparisonPayload);
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
  }, [baselineRunId, comparisonRunId]);

  useEffect(() => {
    if (!manifestRunId) {
      setManifest([]);
      return;
    }

    let cancelled = false;
    setIsLoadingManifest(true);
    setLoadError('');

    void fetchResultsRunFiles(manifestRunId)
      .then((files) => {
        if (!cancelled) {
          setManifest(files);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setLoadError((error as Error).message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingManifest(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [manifestRunId]);

  useEffect(() => {
    if (!baselineDetail) {
      setSelectedIndicatorIds([]);
      return;
    }

    setSelectedIndicatorIds((current) => resolveSelectedIndicatorIds(baselineDetail.indicators, current));
  }, [baselineDetail]);

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
        if (!cancelled) {
          setComparePayload(payload);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setLoadError((error as Error).message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingCompare(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [compareWindow, selectedIndicatorIds, selectedRunIds, smoothWindow]);

  const runById = useMemo(() => new Map(runs.map((run) => [run.runId, run])), [runs]);
  const baselineSummary = baselineRunId ? runById.get(baselineRunId) ?? null : null;
  const comparisonSummary = comparisonRunId ? runById.get(comparisonRunId) ?? null : null;
  const availableIndicators = useMemo(() => baselineDetail?.indicators ?? [], [baselineDetail]);
  const sortedKpis = useMemo(() => sortKpis(baselineDetail?.kpiSummary ?? []), [baselineDetail]);
  const comparisonKpiById = useMemo(
    () => new Map((comparisonDetail?.kpiSummary ?? []).map((kpi) => [kpi.indicatorId, kpi])),
    [comparisonDetail]
  );
  const groupedIndicatorSections = useMemo(
    () =>
      groupIndicatorsBySource(availableIndicators).map((section) => ({
        id: section.id,
        title: section.title,
        items: section.items.map((indicator) => ({
          id: indicator.id,
          label: indicator.title,
          description: `${indicator.units} · ${indicator.source}${indicator.note ? ` · ${indicator.note}` : ''}`,
          checked: selectedIndicatorIds.includes(indicator.id),
          disabled: !indicator.available
        }))
      })),
    [availableIndicators, selectedIndicatorIds]
  );
  const overlayIndicators = comparePayload?.indicators ?? [];
  const activeIndicatorOptions = useMemo(() => {
    if (overlayIndicators.length > 0) {
      return overlayIndicators.map((indicatorPayload) => ({
        id: indicatorPayload.indicator.id,
        title: indicatorPayload.indicator.title
      }));
    }

    const titleById = new Map(availableIndicators.map((indicator) => [indicator.id, indicator.title]));
    return selectedIndicatorIds.map((indicatorId) => ({
      id: indicatorId,
      title: titleById.get(indicatorId) ?? indicatorId
    }));
  }, [availableIndicators, overlayIndicators, selectedIndicatorIds]);
  const activeIndicatorPayload = useMemo(
    () => overlayIndicators.find((indicatorPayload) => indicatorPayload.indicator.id === activeIndicatorId) ?? null,
    [activeIndicatorId, overlayIndicators]
  );
  const showRunsSkeleton = isLoadingRuns && runs.length === 0;
  const showRunsRefreshing = isLoadingRuns && runs.length > 0;
  const showIndicatorsSkeleton = isLoadingDetail && availableIndicators.length === 0;
  const showIndicatorsRefreshing = isLoadingDetail && availableIndicators.length > 0;
  const showKpiSkeleton = isLoadingDetail && sortedKpis.length === 0;
  const showKpiRefreshing = isLoadingDetail && sortedKpis.length > 0;
  const showOverlaySkeleton = isLoadingCompare && overlayIndicators.length === 0 && selectedIndicatorIds.length > 0;
  const showOverlayRefreshing = isLoadingCompare && overlayIndicators.length > 0;
  const showManifestSkeleton = isLoadingManifest && manifest.length === 0;
  const showManifestRefreshing = isLoadingManifest && manifest.length > 0;

  useEffect(() => {
    setActiveIndicatorId((current) => resolveActiveIndicatorId(selectedIndicatorIds, overlayIndicators, current));
  }, [overlayIndicators, selectedIndicatorIds]);

  const updateSelection = useCallback(
    (nextBaselineRunId: string, nextComparisonRunId: string) => {
      onManualSelectionChange({
        baselineRunId: nextBaselineRunId,
        comparisonRunId:
          nextComparisonRunId && nextComparisonRunId !== nextBaselineRunId ? nextComparisonRunId : ''
      });
    },
    [onManualSelectionChange]
  );

  const setBaselineSelection = (runId: string) => {
    updateSelection(runId, comparisonRunId === runId ? '' : comparisonRunId);
  };

  const toggleComparisonSelection = (runId: string) => {
    if (!baselineRunId || runId === baselineRunId) {
      return;
    }

    updateSelection(baselineRunId, comparisonRunId === runId ? '' : runId);
  };

  const toggleIndicatorSelection = (indicatorId: string) => {
    setSelectedIndicatorIds((current) =>
      current.includes(indicatorId) ? current.filter((id) => id !== indicatorId) : [...current, indicatorId]
    );
  };

  const deleteRun = async (runId: string) => {
    if (!canWrite) {
      return;
    }
    if (isProtectedResultsRun(runId)) {
      setLoadError(`Run "${runId}" is protected and cannot be deleted from experiments.`);
      return;
    }
    const confirmed = window.confirm(`Delete run "${runId}"? This permanently removes its Results folder.`);
    if (!confirmed) {
      return;
    }

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
    <section className="results-layout manual-results-layout">
      {loadError && <p className="error-banner">{loadError}</p>}

      <div className="results-grid">
        <aside className="results-sidebar">
          <div className="results-panel">
            <CollapsibleSection
              title="Run Selection"
              defaultOpen={false}
              className="manual-results-disclosure"
              bodyClassName="manual-results-disclosure-body"
            >
              <p>{sidebarSubtitle}</p>
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
                  {runs.map((run) => {
                    const isBaselineSelected = baselineRunId === run.runId;
                    const isComparisonSelected = comparisonRunId === run.runId;
                    return (
                      <li
                        key={run.runId}
                        className={[
                          'run-item',
                          isBaselineSelected ? 'selected-baseline' : '',
                          isComparisonSelected ? 'selected-comparison' : ''
                        ]
                          .filter(Boolean)
                          .join(' ')}
                      >
                        <div className="run-item-head">
                          <strong>{run.runId}</strong>
                          <div className="run-role-chips">
                            {isBaselineSelected && <span className="run-role-chip">Baseline</span>}
                            {isComparisonSelected && <span className="run-role-chip comparison">Comparison</span>}
                          </div>
                        </div>

                        <div className="manual-run-action-row">
                          <button
                            type="button"
                            className={`run-select-btn ${isBaselineSelected ? 'active' : ''}`}
                            onClick={() => setBaselineSelection(run.runId)}
                          >
                            {isBaselineSelected ? 'Baseline selected' : 'Set baseline'}
                          </button>
                          <button
                            type="button"
                            className={`run-select-btn ${isComparisonSelected ? 'active' : ''}`}
                            onClick={() => toggleComparisonSelection(run.runId)}
                            disabled={!baselineRunId || isBaselineSelected}
                          >
                            {isComparisonSelected ? 'Clear comparison' : 'Set comparison'}
                          </button>
                        </div>

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
                    );
                  })}
                </ul>
              )}
            </CollapsibleSection>
          </div>

          <div className="results-panel">
            <div className="results-panel-header">
              <h2>Settings</h2>
              <p>{selectedIndicatorIds.length} indicators enabled</p>
            </div>
            <div className="results-controls results-controls-sidebar">
              <label>
                <InlineInfoTip
                  label="Window"
                  description="post200 shows all months after the spin-up cutoff at month 200. tail120 shows only the latest 120 months. full shows the entire run including spin-up."
                />
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
                <InlineInfoTip
                  label="Smoothing"
                  description="off shows raw monthly values. 3 shows a trailing 3-month average. 12 shows a trailing 12-month average."
                />
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

            <div className="settings-disclosure">
              <button
                type="button"
                className="result-group-header settings-disclosure-toggle"
                onClick={() => setIsIndicatorSettingsOpen((current) => !current)}
              >
                <span className="result-group-title">{isIndicatorSettingsOpen ? '▾' : '▸'} Indicators</span>
                <span className="result-group-counts">
                  <span className="unchanged">{selectedIndicatorIds.length} selected</span>
                </span>
              </button>
              {isIndicatorSettingsOpen && (
                <div className="settings-disclosure-body">
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
                    <GroupedCheckboxSections
                      sections={groupedIndicatorSections}
                      onToggle={toggleIndicatorSelection}
                      className="param-groups indicator-settings-groups"
                      sectionClassName="indicator-settings-section"
                    />
                  )}
                </div>
              )}
            </div>
          </div>
        </aside>

        <div className="results-main">
          <article className="results-card">
            <div className="results-card-head">
              <h2>Manual Results</h2>
              <span className="manual-results-mode-pill">{mode === 'compare' ? 'Compare mode' : 'Single mode'}</span>
            </div>
            <div className="summary-links">
              <Link
                className="summary-link-inline"
                to={buildExperimentsPath({
                  ...DEFAULT_EXPERIMENT_ROUTE_STATE,
                  type: 'sensitivity',
                  mode: 'view'
                })}
              >
                Open Sensitivity Results
              </Link>
            </div>

            <div className="manual-selection-summary">
              <div className="manual-selection-summary-row">
                <span className="manual-selection-summary-label">Baseline</span>
                <strong>{baselineRunId || 'none'}</strong>
                {baselineSummary && <span className={statusClass(baselineSummary.status)}>{baselineSummary.status}</span>}
              </div>
              <div className="manual-selection-summary-row">
                <span className="manual-selection-summary-label">Comparison</span>
                {comparisonRunId ? (
                  <>
                    <strong>{comparisonRunId}</strong>
                    {comparisonSummary && (
                      <span className={statusClass(comparisonSummary.status)}>{comparisonSummary.status}</span>
                    )}
                  </>
                ) : (
                  <span className="manual-selection-empty">None selected</span>
                )}
              </div>
            </div>

            <p>Compare window and indicator controls are available in the Settings panel.</p>
          </article>

          <article className="results-card">
            <div className="aggregate-results-head">
              <div>
                <h3>Aggregate Results</h3>
                <p>
                  {showAllKpiDetails
                    ? 'Detailed tables show mean plus all aggregate metrics for every KPI.'
                    : 'Mean is shown by default. Use More details to switch every KPI card to a detailed table.'}
                </p>
              </div>
              <button
                type="button"
                className="table-toggle aggregate-results-toggle"
                aria-pressed={showAllKpiDetails}
                onClick={() => setShowAllKpiDetails((current) => !current)}
              >
                {showAllKpiDetails ? 'Hide details' : 'More details'}
              </button>
            </div>
            {showKpiRefreshing && (
              <LoadingSkeleton
                as="span"
                className="loading-skeleton-pill section-loading-row"
                ariaLabel="Refreshing aggregate results"
              />
            )}
            {showKpiSkeleton ? (
              <LoadingSkeletonGroup
                className="kpi-grid"
                count={4}
                itemClassName="loading-skeleton-card kpi-card-skeleton"
                ariaLabel="Loading aggregate results"
              />
            ) : (
              <div
                id="aggregate-results-grid"
                className={['kpi-grid', showAllKpiDetails ? 'kpi-grid-detailed' : ''].filter(Boolean).join(' ')}
              >
                {sortedKpis.map((kpi) => {
                  const comparisonKpi = comparisonKpiById.get(kpi.indicatorId) ?? null;
                  const meanDelta = computeKpiPercentDelta(kpi.mean, comparisonKpi?.mean ?? null);
                  return (
                    <div key={kpi.indicatorId} className="kpi-card">
                      <p className="kpi-title">{kpi.title}</p>
                      {!showAllKpiDetails ? (
                        mode === 'single' ? (
                          <p className="kpi-value">Mean (month): {formatNumber(kpi.mean, kpi.units)}</p>
                        ) : (
                          <div className="manual-kpi-compare-grid">
                            <p>
                              <span>Baseline</span>
                              {formatNumber(kpi.mean, kpi.units)}
                            </p>
                            <p>
                              <span>Comparison</span>
                              {formatNumber(comparisonKpi?.mean ?? null, kpi.units)}
                            </p>
                            <p className={`manual-kpi-delta ${deltaClassName(meanDelta)}`}>
                              <span>% delta</span>
                              {formatSignedPercent(meanDelta)}
                            </p>
                          </div>
                        )
                      ) : (
                        <div className="manual-kpi-detail-table-wrap">
                          {mode === 'single' ? (
                            <table className="manual-kpi-detail-table single">
                              <thead>
                                <tr>
                                  <th>Metric</th>
                                  <th>Value</th>
                                </tr>
                              </thead>
                              <tbody>
                                {KPI_DETAIL_ROWS.map((row) => {
                                  const value = getKpiMetricValue(kpi, row.key);
                                  const units = row.units === 'dynamic' ? kpi.units : row.units;
                                  return (
                                    <tr key={row.key}>
                                      <td>{row.label}</td>
                                      <td>{formatNumber(value, units)}</td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          ) : (
                            <table className="manual-kpi-detail-table compare">
                              <thead>
                                <tr>
                                  <th>Metric</th>
                                  <th>Baseline</th>
                                  <th>Comparison</th>
                                  <th>% delta</th>
                                </tr>
                              </thead>
                              <tbody>
                                {KPI_DETAIL_ROWS.map((row) => {
                                  const baselineValue = getKpiMetricValue(kpi, row.key);
                                  const comparisonValue = getKpiMetricValue(comparisonKpi, row.key);
                                  const delta = computeKpiPercentDelta(baselineValue, comparisonValue);
                                  const units = row.units === 'dynamic' ? kpi.units : row.units;
                                  return (
                                    <tr key={row.key}>
                                      <td>{row.label}</td>
                                      <td>{formatNumber(baselineValue, units)}</td>
                                      <td>{formatNumber(comparisonValue, units)}</td>
                                      <td className={deltaClassName(delta)}>{formatSignedPercent(delta)}</td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </article>

          <article className="results-card">
            <div className="overlay-card-head">
              <h3>Indicator Overlays</h3>
              <label>
                Indicator
                <select
                  value={activeIndicatorId}
                  disabled={activeIndicatorOptions.length === 0}
                  onChange={(event) => setActiveIndicatorId(event.target.value)}
                >
                  {activeIndicatorOptions.map((indicator) => (
                    <option key={indicator.id} value={indicator.id}>
                      {indicator.title}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p>
              Overlay series are shown in raw units. {mode === 'compare' ? 'Baseline and comparison are labelled by role.' : 'Single-run view uses the baseline selection.'}
            </p>
            {showOverlayRefreshing && (
              <LoadingSkeleton
                as="span"
                className="loading-skeleton-pill section-loading-row"
                ariaLabel="Refreshing indicator overlays"
              />
            )}
            {selectedIndicatorIds.length === 0 ? (
              <p className="info-banner">Enable at least one indicator in Settings to view an overlay chart.</p>
            ) : showOverlaySkeleton ? (
              <LoadingSkeletonGroup
                className="overlay-grid"
                count={1}
                itemClassName="loading-skeleton-card overlay-card-skeleton"
                ariaLabel="Loading indicator overlays"
              />
            ) : !activeIndicatorPayload ? (
              <p className="info-banner">No overlay data is available for the current indicator selection yet.</p>
            ) : (
              <div className="overlay-grid">
                <div key={activeIndicatorPayload.indicator.id} className="overlay-card">
                  <h4>{activeIndicatorPayload.indicator.title}</h4>
                  <EChart
                    option={buildOverlayOption(activeIndicatorPayload, baselineRunId, comparisonRunId)}
                    className="chart"
                  />
                </div>
              </div>
            )}
          </article>

          <article className="results-card">
            <CollapsibleSection
              title="File Manifest"
              defaultOpen={false}
              summary={`${manifestTargetLabel}${manifestRunId ? ` · ${manifestRunId}` : ''}`}
              className="manual-results-disclosure"
              bodyClassName="manual-results-disclosure-body"
            >
              {mode === 'compare' && comparisonRunId && (
                <div className="manual-manifest-switcher">
                  <button
                    type="button"
                    className={`filter-pill ${manifestTarget === 'baseline' ? 'active' : ''}`}
                    onClick={() => setManifestTarget('baseline')}
                  >
                    Baseline
                  </button>
                  <button
                    type="button"
                    className={`filter-pill ${manifestTarget === 'comparison' ? 'active' : ''}`}
                    onClick={() => setManifestTarget('comparison')}
                  >
                    Comparison
                  </button>
                </div>
              )}
              <p>
                Showing {manifestTargetLabel.toLowerCase()} manifest for <strong>{manifestRunId || 'no run selected'}</strong>.
              </p>
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
            </CollapsibleSection>
          </article>
        </div>
      </div>
    </section>
  );
}
