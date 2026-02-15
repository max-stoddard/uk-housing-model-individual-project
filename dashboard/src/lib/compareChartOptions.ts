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
  deltaAxisName: string
): EChartsOption {
  if (item.visualPayload.type !== 'binned_distribution') {
    return {};
  }

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (rawParams: unknown) => {
        const rows = Array.isArray(rawParams) ? rawParams : [rawParams];
        const axis = String((rows[0] as any)?.axisValueLabel ?? (rows[0] as any)?.axisValue ?? '');
        const left = (rows.find((entry: any) => entry.seriesName === item.leftVersion) as any)?.data ?? 0;
        const right = (rows.find((entry: any) => entry.seriesName === item.rightVersion) as any)?.data ?? 0;
        const delta = (rows.find((entry: any) => entry.seriesName === 'Delta') as any)?.data ?? 0;
        return `${axis}<br/>${item.leftVersion}: ${formatChartNumber(Number(left))}<br/>${item.rightVersion}: ${formatChartNumber(
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
        name: item.leftVersion,
        type: 'bar',
        data: item.visualPayload.bins.map((bin) => bin.left),
        barGap: '-100%',
        itemStyle: { color: 'rgba(20, 84, 214, 0.55)' }
      },
      {
        name: item.rightVersion,
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

export function binnedSingleOption(item: CompareResult, xAxisName: string, yAxisName: string): EChartsOption {
  if (item.visualPayload.type !== 'binned_distribution') {
    return {};
  }

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
        name: item.rightVersion,
        type: 'bar',
        data: item.visualPayload.bins.map((bin) => bin.right),
        itemStyle: { color: 'rgba(11, 114, 133, 0.72)' }
      }
    ]
  };
}

export function jointLayoutOverrides(itemId: string): JointHeatmapLayoutOverrides | undefined {
  if (itemId === 'wealth_given_income_joint') {
    return {
      xAxisNameGap: 70,
      gridBottom: 108
    };
  }
  return undefined;
}

export function curveOption(
  leftVersion: string,
  rightVersion: string,
  leftSeries: CurvePoint[],
  rightSeries: CurvePoint[],
  xLabel: string,
  yLabel: string,
  valueFormatter?: (value: number) => string
): EChartsOption {
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
    grid: { left: 82, right: 36, top: 44, bottom: 82, containLabel: true },
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
      nameGap: 58,
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
        smooth: true,
        data: leftSeries.map((point) => [point.x, point.y]),
        lineStyle: { color: '#0b7285', width: 2 }
      },
      {
        name: rightVersion,
        type: 'line',
        showSymbol: false,
        smooth: true,
        data: rightSeries.map((point) => [point.x, point.y]),
        lineStyle: { color: '#18958b', width: 2 }
      }
    ]
  };
}

export function curveSingleOption(
  version: string,
  series: CurvePoint[],
  xLabel: string,
  yLabel: string,
  valueFormatter?: (value: number) => string
): EChartsOption {
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
    grid: { left: 82, right: 36, top: 44, bottom: 82, containLabel: true },
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
      nameGap: 58,
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
        smooth: true,
        data: series.map((point) => [point.x, point.y]),
        lineStyle: { color: '#0b7285', width: 2 }
      }
    ]
  };
}
