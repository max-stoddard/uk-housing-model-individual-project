import type {
  KpiMetricSummary,
  ResultsCompareIndicator,
  ResultsIndicatorAvailability,
  ResultsRunSummary
} from '../../shared/types';

export const DEFAULT_MANUAL_BASELINE_RUN_ID = 'v0-output';
export const DEFAULT_MANUAL_COMPARISON_RUN_ID = 'v4.0-output';
const KPI_BASELINE_EPSILON = 1e-12;

export interface GroupedIndicatorSection {
  id: 'core_indicator' | 'output';
  title: string;
  items: ResultsIndicatorAvailability[];
}

export interface ManualRunSelection {
  baselineRunId: string;
  comparisonRunId: string;
}

export function groupIndicatorsBySource(
  indicators: ResultsIndicatorAvailability[]
): GroupedIndicatorSection[] {
  const groups: GroupedIndicatorSection[] = [
    { id: 'core_indicator', title: 'Core indicators', items: [] },
    { id: 'output', title: 'Output', items: [] }
  ];

  for (const indicator of indicators) {
    const group = groups.find((entry) => entry.id === indicator.source);
    if (group) {
      group.items.push(indicator);
    }
  }

  return groups.filter((group) => group.items.length > 0);
}

export function resolveSelectedIndicatorIds(
  indicators: ResultsIndicatorAvailability[],
  current: string[]
): string[] {
  const availableIds = indicators.filter((indicator) => indicator.available).map((indicator) => indicator.id);
  const availableSet = new Set(availableIds);
  const filtered = current.filter((id) => availableSet.has(id));
  return filtered.length > 0 ? filtered : availableIds;
}

export function resolveActiveIndicatorId(
  selectedIndicatorIds: string[],
  compareIndicators: ResultsCompareIndicator[],
  current: string
): string {
  const compareIds = compareIndicators.map((indicatorPayload) => indicatorPayload.indicator.id);
  const selectableIds = compareIds.length > 0 ? compareIds : selectedIndicatorIds;
  if (selectableIds.length === 0) {
    return '';
  }
  return selectableIds.includes(current) ? current : selectableIds[0];
}

export function sortKpis(kpis: KpiMetricSummary[]): KpiMetricSummary[] {
  return [...kpis].sort((left, right) => left.title.localeCompare(right.title));
}

function findPreferredRunId(
  runs: ResultsRunSummary[],
  preferredRunId: string,
  excludeRunId = ''
): string {
  const matched = runs.find((run) => run.runId === preferredRunId && run.runId !== excludeRunId);
  return matched?.runId ?? '';
}

function findFirstDistinctRunId(runs: ResultsRunSummary[], excludeRunId = ''): string {
  return runs.find((run) => run.runId !== excludeRunId)?.runId ?? '';
}

export function resolveManualRunSelection(
  runs: ResultsRunSummary[],
  requestedBaselineRunId: string,
  requestedComparisonRunId: string
): ManualRunSelection {
  if (runs.length === 0) {
    return {
      baselineRunId: '',
      comparisonRunId: ''
    };
  }

  const availableRunIds = new Set(runs.map((run) => run.runId));
  const hasRequestedBaseline = requestedBaselineRunId.trim().length > 0;
  const hasRequestedComparison = requestedComparisonRunId.trim().length > 0;
  const requestedBaseline = availableRunIds.has(requestedBaselineRunId) ? requestedBaselineRunId : '';
  const requestedComparison = availableRunIds.has(requestedComparisonRunId) ? requestedComparisonRunId : '';

  if (requestedBaseline) {
    return {
      baselineRunId: requestedBaseline,
      comparisonRunId: requestedComparison && requestedComparison !== requestedBaseline ? requestedComparison : ''
    };
  }

  if (hasRequestedBaseline || hasRequestedComparison) {
    return {
      baselineRunId:
        findPreferredRunId(runs, DEFAULT_MANUAL_BASELINE_RUN_ID) || findFirstDistinctRunId(runs),
      comparisonRunId: ''
    };
  }

  const baselineRunId =
    findPreferredRunId(runs, DEFAULT_MANUAL_BASELINE_RUN_ID) || findFirstDistinctRunId(runs);
  const comparisonRunId =
    findPreferredRunId(runs, DEFAULT_MANUAL_COMPARISON_RUN_ID, baselineRunId) ||
    findFirstDistinctRunId(runs, baselineRunId);

  return {
    baselineRunId,
    comparisonRunId
  };
}

export function computeKpiPercentDelta(
  baselineValue: number | null,
  comparisonValue: number | null
): number | null {
  if (
    baselineValue === null ||
    comparisonValue === null ||
    !Number.isFinite(baselineValue) ||
    !Number.isFinite(comparisonValue) ||
    Math.abs(baselineValue) < KPI_BASELINE_EPSILON
  ) {
    return null;
  }

  return ((comparisonValue - baselineValue) / baselineValue) * 100;
}
