// Author: Max Stoddard
import type { EChartsOption } from 'echarts';
import type { CompareResult, CurvePoint, ScalarDatum } from '../../shared/types';
import type { JointHeatmapLayoutOverrides } from './jointHeatmapOption';

export function formatChartNumber(value: number): string {
  if (Math.abs(value) >= 1_000_000) {
    return value.toLocaleString('en-GB', { maximumFractionDigits: 0 });
  }
  if (Math.abs(value) >= 1000) {
    return value.toLocaleString('en-GB', { maximumFractionDigits: 2 });
  }
  if (Math.abs(value) >= 1) {
    return value.toLocaleString('en-GB', { maximumFractionDigits: 4 });
  }
  return value.toLocaleString('en-GB', { maximumFractionDigits: 8 });
}

function formatScientific(value: number, digits = 2): string {
  const [mantissa, exponent] = value.toExponential(digits).split('e');
  const trimmedMantissa = mantissa.replace(/\.?0+$/, '');
  const normalizedExponent = exponent.replace('+', '').replace(/^(-?)0+(\d)/, '$1$2');
  return `${trimmedMantissa}e${normalizedExponent}`;
}

function formatCurveValue(value: number): string {
  const absolute = Math.abs(value);
  if (absolute < 1e-12) {
    return '0';
  }
  if (absolute < 0.001) {
    return formatScientific(value, 2);
  }
  if (absolute < 1) {
    return value.toLocaleString('en-GB', { maximumFractionDigits: 6 });
  }
  return formatChartNumber(value);
}

function formatAxisTick(value: number): string {
  const absolute = Math.abs(value);
  if (absolute < 1e-12) {
    return '0';
  }
  if (absolute >= 1) {
    return value.toLocaleString('en-GB', { maximumFractionDigits: 2 });
  }
  if (absolute >= 0.01) {
    return value.toLocaleString('en-GB', { maximumFractionDigits: 3 });
  }
  if (absolute >= 0.001) {
    return value.toLocaleString('en-GB', { maximumFractionDigits: 4 });
  }
  return formatScientific(value, 1);
}

export interface CurveLayoutOverrides {
  gridLeft?: number;
  gridRight?: number;
  yAxisNameGap?: number;
}

interface CurveVerticalMarker {
  x: number;
  label?: string;
  color?: string;
}

interface CurveLegendMarker {
  x: number;
  name: string;
  color?: string;
}

function resolveCurveYExtent(seriesGroups: CurvePoint[][]): [number, number] {
  const yValues: number[] = [];
  for (const series of seriesGroups) {
    for (const point of series) {
      if (Number.isFinite(point.y)) {
        yValues.push(point.y);
      }
    }
  }

  if (yValues.length === 0) {
    return [0, 1];
  }

  let yMin = Math.min(...yValues);
  let yMax = Math.max(...yValues);
  if (Math.abs(yMax - yMin) < 1e-12) {
    const padding = Math.max(Math.abs(yMin) * 0.05, 1e-6);
    yMin -= padding;
    yMax += padding;
  }

  return [yMin, yMax];
}

function buildVerticalMarker(marker: CurveVerticalMarker | undefined, fallbackColor = '#495057') {
  if (!marker || !Number.isFinite(marker.x)) {
    return undefined;
  }
  const color = marker.color ?? fallbackColor;
  return {
    symbol: 'none',
    silent: true,
    lineStyle: { type: 'dashed' as const, width: 1.5, color },
    label: {
      formatter: marker.label ?? `x=${formatChartNumber(marker.x)}`,
      position: 'insideEndTop' as const,
      color
    },
    data: [{ xAxis: marker.x }]
  };
}

function buildLegendMarkerSeries(
  legendMarkers: CurveLegendMarker[] | undefined,
  yMin: number,
  yMax: number
): Array<Record<string, unknown>> {
  if (!legendMarkers || legendMarkers.length === 0) {
    return [];
  }

  return legendMarkers
    .filter((marker) => Number.isFinite(marker.x))
    .map((marker) => ({
      name: marker.name,
      type: 'line',
      silent: true,
      clip: true,
      showSymbol: false,
      tooltip: { show: false },
      emphasis: { disabled: true },
      data: [
        [marker.x, yMin],
        [marker.x, yMax]
      ],
      lineStyle: {
        type: 'dashed' as const,
        width: 1.5,
        color: marker.color ?? '#495057'
      }
    }));
}

export function scalarOption(
  values: ScalarDatum[],
  leftVersion: string,
  rightVersion: string,
  xAxisName: string,
  yAxisName: string
): EChartsOption {
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 74, right: 34, top: 44, bottom: 98, containLabel: true },
    xAxis: {
      type: 'category',
      data: values.map((entry) => entry.key),
      axisLabel: { rotate: 25 },
      name: xAxisName,
      nameLocation: 'middle',
      nameGap: 66,
      nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' }
    },
    yAxis: {
      type: 'value',
      name: yAxisName,
      nameLocation: 'middle',
      nameGap: 58,
      nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' }
    },
    series: [
      {
        name: leftVersion,
        type: 'bar',
        data: values.map((entry) => entry.left),
        itemStyle: { color: '#0b7285' }
      },
      {
        name: rightVersion,
        type: 'bar',
        data: values.map((entry) => entry.right),
        itemStyle: { color: '#18958b' }
      }
    ]
  };
}

export function scalarSingleOption(
  values: ScalarDatum[],
  version: string,
  xAxisName: string,
  yAxisName: string
): EChartsOption {
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 74, right: 34, top: 44, bottom: 98, containLabel: true },
    xAxis: {
      type: 'category',
      data: values.map((entry) => entry.key),
      axisLabel: { rotate: 25 },
      name: xAxisName,
      nameLocation: 'middle',
      nameGap: 66,
      nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' }
    },
    yAxis: {
      type: 'value',
      name: yAxisName,
      nameLocation: 'middle',
      nameGap: 58,
      nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' }
    },
    series: [
      {
        name: version,
        type: 'bar',
        data: values.map((entry) => entry.right),
        itemStyle: { color: '#0b7285' }
      }
    ]
  };
}

export function binnedOption(
  item: CompareResult,
  xAxisName: string,
  yAxisName: string,
  deltaAxisName: string,
  labels?: { leftLabel?: string; rightLabel?: string }
): EChartsOption {
  if (item.visualPayload.type !== 'binned_distribution') {
    return {};
  }

  const leftLabel = labels?.leftLabel ?? item.leftVersion;
  const rightLabel = labels?.rightLabel ?? item.rightVersion;

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (rawParams: unknown) => {
        const rows = Array.isArray(rawParams) ? rawParams : [rawParams];
        const axis = String((rows[0] as any)?.axisValueLabel ?? (rows[0] as any)?.axisValue ?? '');
        const left = (rows.find((entry: any) => entry.seriesName === leftLabel) as any)?.data ?? 0;
        const right = (rows.find((entry: any) => entry.seriesName === rightLabel) as any)?.data ?? 0;
        const delta = (rows.find((entry: any) => entry.seriesName === 'Delta') as any)?.data ?? 0;
        return `${axis}<br/>${leftLabel}: ${formatChartNumber(Number(left))}<br/>${rightLabel}: ${formatChartNumber(
          Number(right)
        )}<br/>Delta: ${formatChartNumber(Number(delta))}`;
      }
    },
    legend: { top: 0 },
    grid: { left: 78, right: 76, top: 44, bottom: 108, containLabel: true },
    xAxis: {
      type: 'category',
      data: item.visualPayload.bins.map((bin) => bin.label),
      axisLabel: { rotate: 35 },
      name: xAxisName,
      nameLocation: 'middle',
      nameGap: 70,
      nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' }
    },
    yAxis: [
      {
        type: 'value',
        name: yAxisName,
        nameLocation: 'middle',
        nameGap: 64,
        nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' }
      },
      {
        type: 'value',
        name: deltaAxisName,
        position: 'right',
        nameLocation: 'middle',
        nameGap: 64,
        nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' }
      }
    ],
    series: [
      {
        name: leftLabel,
        type: 'bar',
        data: item.visualPayload.bins.map((bin) => bin.left),
        barGap: '-100%',
        itemStyle: { color: 'rgba(20, 84, 214, 0.55)' }
      },
      {
        name: rightLabel,
        type: 'bar',
        data: item.visualPayload.bins.map((bin) => bin.right),
        itemStyle: { color: 'rgba(24, 149, 139, 0.55)' }
      },
      {
        name: 'Delta',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        data: item.visualPayload.bins.map((bin) => bin.delta),
        lineStyle: { color: '#5c7cfa', width: 2 }
      }
    ]
  };
}

export function binnedSingleOption(
  item: CompareResult,
  xAxisName: string,
  yAxisName: string,
  versionLabel?: string
): EChartsOption {
  if (item.visualPayload.type !== 'binned_distribution') {
    return {};
  }

  const label = versionLabel ?? item.rightVersion;

  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 78, right: 34, top: 44, bottom: 108, containLabel: true },
    xAxis: {
      type: 'category',
      data: item.visualPayload.bins.map((bin) => bin.label),
      axisLabel: { rotate: 35 },
      name: xAxisName,
      nameLocation: 'middle',
      nameGap: 70,
      nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' }
    },
    yAxis: [
      {
        type: 'value',
        name: yAxisName,
        nameLocation: 'middle',
        nameGap: 64,
        nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' }
      }
    ],
    series: [
      {
        name: label,
        type: 'bar',
        data: item.visualPayload.bins.map((bin) => bin.right),
        itemStyle: { color: 'rgba(11, 114, 133, 0.72)' }
      }
    ]
  };
}

export function jointLayoutOverrides(itemId: string): JointHeatmapLayoutOverrides | undefined {
  void itemId;
  return undefined;
}

export function curveOption(
  leftVersion: string,
  rightVersion: string,
  leftSeries: CurvePoint[],
  rightSeries: CurvePoint[],
  xLabel: string,
  yLabel: string,
  valueFormatter?: (value: number) => string,
  verticalMarkerX?: number,
  verticalMarkerLabel?: string,
  layoutOverrides?: CurveLayoutOverrides,
  legendMarkers?: CurveLegendMarker[]
): EChartsOption {
  const resolvedGridLeft = layoutOverrides?.gridLeft ?? 82;
  const resolvedGridRight = layoutOverrides?.gridRight ?? 36;
  const resolvedYAxisNameGap = layoutOverrides?.yAxisNameGap ?? 58;

  const marker = buildVerticalMarker(
    verticalMarkerX !== undefined ? { x: verticalMarkerX, label: verticalMarkerLabel } : undefined
  );
  const [yMin, yMax] = resolveCurveYExtent([leftSeries, rightSeries]);
  const legendMarkerSeries = buildLegendMarkerSeries(legendMarkers, yMin, yMax);

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (rawParams: unknown) => {
        const rows = Array.isArray(rawParams) ? rawParams : [rawParams];
        const xValue = Number((rows[0] as any)?.axisValue ?? 0);
        const xText = valueFormatter ? valueFormatter(Number(xValue)) : formatChartNumber(Number(xValue));
        const leftSeriesData = (rows.find((entry: any) => entry.seriesName === leftVersion) as any)?.data;
        const rightSeriesData = (rows.find((entry: any) => entry.seriesName === rightVersion) as any)?.data;
        const left = Array.isArray(leftSeriesData) ? Number(leftSeriesData[1]) : 0;
        const right = Array.isArray(rightSeriesData) ? Number(rightSeriesData[1]) : 0;
        return `${xLabel}: ${xText}<br/>${leftVersion}: ${formatCurveValue(left)}<br/>${rightVersion}: ${formatCurveValue(right)}`;
      }
    },
    legend: { top: 0 },
    grid: { left: resolvedGridLeft, right: resolvedGridRight, top: 44, bottom: 82, containLabel: true },
    xAxis: {
      type: 'value',
      name: xLabel,
      nameLocation: 'middle',
      nameGap: 52,
      nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' }
    },
    yAxis: {
      type: 'value',
      name: yLabel,
      nameLocation: 'middle',
      nameGap: resolvedYAxisNameGap,
      nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' },
      axisLabel: {
        formatter: (rawValue: number) => formatAxisTick(Number(rawValue))
      }
    },
    series: [
      {
        name: leftVersion,
        type: 'line',
        showSymbol: false,
        clip: true,
        smooth: true,
        data: leftSeries.map((point) => [point.x, point.y]),
        lineStyle: { color: '#0b7285', width: 2 }
      },
      {
        name: rightVersion,
        type: 'line',
        showSymbol: false,
        clip: true,
        smooth: true,
        data: rightSeries.map((point) => [point.x, point.y]),
        lineStyle: { color: '#18958b', width: 2 },
        ...(marker ? { markLine: marker } : {})
      },
      ...legendMarkerSeries
    ]
  };
}

export function curveSingleOption(
  version: string,
  series: CurvePoint[],
  xLabel: string,
  yLabel: string,
  valueFormatter?: (value: number) => string,
  verticalMarkerX?: number,
  verticalMarkerLabel?: string,
  layoutOverrides?: CurveLayoutOverrides,
  legendMarkers?: CurveLegendMarker[]
): EChartsOption {
  const resolvedGridLeft = layoutOverrides?.gridLeft ?? 82;
  const resolvedGridRight = layoutOverrides?.gridRight ?? 36;
  const resolvedYAxisNameGap = layoutOverrides?.yAxisNameGap ?? 58;

  const marker =
    verticalMarkerX !== undefined && Number.isFinite(verticalMarkerX)
      ? {
          symbol: 'none',
          silent: true,
          lineStyle: { type: 'dashed' as const, width: 1.5, color: '#495057' },
          label: {
            formatter: verticalMarkerLabel ?? `x=${formatChartNumber(verticalMarkerX)}`,
            position: 'insideEndTop' as const,
            color: '#495057'
          },
          data: [{ xAxis: verticalMarkerX }]
        }
      : undefined;
  const [yMin, yMax] = resolveCurveYExtent([series]);
  const legendMarkerSeries = buildLegendMarkerSeries(legendMarkers, yMin, yMax);

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (rawParams: unknown) => {
        const rows = Array.isArray(rawParams) ? rawParams : [rawParams];
        const xValue = Number((rows[0] as any)?.axisValue ?? 0);
        const xText = valueFormatter ? valueFormatter(Number(xValue)) : formatChartNumber(Number(xValue));
        const seriesData = (rows.find((entry: any) => entry.seriesName === version) as any)?.data;
        const value = Array.isArray(seriesData) ? Number(seriesData[1]) : 0;
        return `${xLabel}: ${xText}<br/>${version}: ${formatCurveValue(value)}`;
      }
    },
    legend: { top: 0 },
    grid: { left: resolvedGridLeft, right: resolvedGridRight, top: 44, bottom: 82, containLabel: true },
    xAxis: {
      type: 'value',
      name: xLabel,
      nameLocation: 'middle',
      nameGap: 52,
      nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' }
    },
    yAxis: {
      type: 'value',
      name: yLabel,
      nameLocation: 'middle',
      nameGap: resolvedYAxisNameGap,
      nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' },
      axisLabel: {
        formatter: (rawValue: number) => formatAxisTick(Number(rawValue))
      }
    },
    series: [
      {
        name: version,
        type: 'line',
        showSymbol: false,
        clip: true,
        smooth: true,
        data: series.map((point) => [point.x, point.y]),
        lineStyle: { color: '#0b7285', width: 2 },
        ...(marker ? { markLine: marker } : {})
      },
      ...legendMarkerSeries
    ]
  };
}
