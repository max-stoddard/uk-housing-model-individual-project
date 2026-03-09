import type { KpiMetricSummary, ResultsCompareIndicator, ResultsIndicatorAvailability } from '../../shared/types';

export interface GroupedIndicatorSection {
  id: 'core_indicator' | 'output';
  title: string;
  items: ResultsIndicatorAvailability[];
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
