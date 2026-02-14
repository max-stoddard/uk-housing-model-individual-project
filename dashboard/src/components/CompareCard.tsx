import { useMemo, useState } from 'react';
import type { EChartsOption } from 'echarts';
import type { CompareResult, JointCell, ScalarDatum } from '../../shared/types';
import { EChart } from './EChart';
import { getAxisSpec } from '../lib/chartAxes';

interface CompareCardProps {
  item: CompareResult;
  mode: 'single' | 'compare';
  defaultExpanded?: boolean;
}

function formatNumber(value: number): string {
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

function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return 'n/a';
  }
  return `${value.toFixed(2)}%`;
}

function formatCompact(value: number): string {
  if (Math.abs(value) >= 1000) {
    return value.toLocaleString('en-GB', { maximumFractionDigits: 0 });
  }
  return value.toLocaleString('en-GB', { maximumFractionDigits: 4 });
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
  return formatNumber(value);
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

function scalarOption(
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

function scalarSingleOption(values: ScalarDatum[], version: string, xAxisName: string, yAxisName: string): EChartsOption {
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

function binnedOption(item: CompareResult, xAxisName: string, yAxisName: string, deltaAxisName: string): EChartsOption {
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
        return `${axis}<br/>${item.leftVersion}: ${formatNumber(Number(left))}<br/>${item.rightVersion}: ${formatNumber(
          Number(right)
        )}<br/>Delta: ${formatNumber(Number(delta))}`;
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

function binnedSingleOption(item: CompareResult, xAxisName: string, yAxisName: string): EChartsOption {
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

function heatmapOption(
  title: string,
  cells: JointCell[],
  xLabels: string[],
  yLabels: string[],
  min: number,
  max: number,
  colors: string[],
  xAxisName: string,
  yAxisName: string
): EChartsOption {
  return {
    title: {
      text: title,
      left: 'center',
      textStyle: { fontSize: 12 }
    },
    tooltip: {
      trigger: 'item',
      formatter: (param: any) => {
        const [xIndex, yIndex, value] = param.data as [number, number, number];
        return `${xLabels[xIndex]} / ${yLabels[yIndex]}<br/>${formatCompact(value)}`;
      }
    },
    grid: { left: 124, right: 72, top: 42, bottom: 94, containLabel: true },
    xAxis: {
      type: 'category',
      data: xLabels,
      axisLabel: { rotate: 45, fontSize: 9, margin: 14 },
      name: xAxisName,
      nameLocation: 'middle',
      nameGap: 56,
      nameTextStyle: { fontSize: 11, fontWeight: 600, color: '#495057' }
    },
    yAxis: {
      type: 'category',
      data: yLabels,
      axisLabel: { fontSize: 9, margin: 10 },
      name: yAxisName,
      nameLocation: 'middle',
      nameGap: 104,
      nameTextStyle: { fontSize: 11, fontWeight: 600, color: '#495057' }
    },
    visualMap: {
      show: true,
      type: 'continuous',
      min,
      max,
      orient: 'vertical',
      right: 10,
      top: 'middle',
      calculable: false,
      realtime: true,
      showLabel: false,
      precision: 6,
      formatter: '{value}',
      itemWidth: 12,
      itemHeight: 168,
      text: ['High', 'Low'],
      textGap: 6,
      textStyle: { color: '#495057', fontSize: 10 },
      inRange: { color: colors }
    },
    series: [
      {
        type: 'heatmap',
        data: cells.map((cell) => [cell.xIndex, cell.yIndex, Number(cell.value.toFixed(10))]),
        emphasis: {
          itemStyle: {
            borderColor: '#212529',
            borderWidth: 1
          }
        }
      }
    ]
  };
}

function curveOption(
  leftVersion: string,
  rightVersion: string,
  leftSeries: Array<{ x: number; y: number }>,
  rightSeries: Array<{ x: number; y: number }>,
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
        const xText = valueFormatter ? valueFormatter(Number(xValue)) : formatNumber(Number(xValue));
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

function curveSingleOption(
  version: string,
  series: Array<{ x: number; y: number }>,
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
        const xText = valueFormatter ? valueFormatter(Number(xValue)) : formatNumber(Number(xValue));
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

function deltaClassName(value: number): string {
  if (Math.abs(value) < 1e-12) {
    return 'neutral';
  }
  return value > 0 ? 'positive' : 'negative';
}

function validationStatusLabel(status: string): string {
  return status === 'in_progress' ? 'In progress' : 'Complete';
}

function renderScalarTable(values: ScalarDatum[], mode: 'single' | 'compare') {
  if (mode === 'single') {
    return (
      <table className="param-table">
        <thead>
          <tr>
            <th>Parameter</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          {values.map((row) => (
            <tr key={row.key}>
              <td>{row.key}</td>
              <td>{formatNumber(row.right)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  return (
    <table className="param-table">
      <thead>
        <tr>
          <th>Parameter</th>
          <th>Left</th>
          <th>Right</th>
          <th>Delta</th>
          <th>Delta %</th>
        </tr>
      </thead>
      <tbody>
        {values.map((row) => (
          <tr key={row.key}>
            <td>{row.key}</td>
            <td>{formatNumber(row.left)}</td>
            <td>{formatNumber(row.right)}</td>
            <td className={deltaClassName(row.delta.absolute)}>{formatNumber(row.delta.absolute)}</td>
            <td className={deltaClassName(row.delta.absolute)}>{formatPercent(row.delta.percent)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function itemIsUpdated(item: CompareResult, mode: 'single' | 'compare'): boolean {
  return mode === 'single' ? item.changeOriginsInRange.length > 0 : !item.unchanged;
}

export function CompareCard({ item, mode, defaultExpanded = false }: CompareCardProps) {
  const [isExpanded, setIsExpanded] = useState<boolean>(defaultExpanded);
  const [isTableOpen, setIsTableOpen] = useState<boolean>(false);
  const [isMoreInfoOpen, setIsMoreInfoOpen] = useState<boolean>(false);

  const updated = itemIsUpdated(item, mode);
  const axisSpec = useMemo(() => getAxisSpec(item.id), [item.id]);

  const jointRanges = useMemo(() => {
    if (item.visualPayload.type !== 'joint_distribution') {
      return null;
    }

    const leftValues = item.visualPayload.matrix.left.map((cell) => cell.value);
    const rightValues = item.visualPayload.matrix.right.map((cell) => cell.value);
    const deltaValues = item.visualPayload.matrix.delta.map((cell) => cell.value);

    const sharedMin = Math.min(...leftValues, ...rightValues);
    const sharedMax = Math.max(...leftValues, ...rightValues);
    const deltaAbs = Math.max(...deltaValues.map((value) => Math.abs(value)), 0);

    return {
      sharedMin,
      sharedMax,
      deltaMin: -deltaAbs,
      deltaMax: deltaAbs
    };
  }, [item]);

  const tableRows = useMemo(() => {
    if (item.visualPayload.type === 'scalar') {
      return item.visualPayload.values;
    }
    if (item.visualPayload.type === 'binned_distribution') {
      return item.visualPayload.bins.map((bin) => ({
        key: bin.label,
        left: bin.left,
        right: bin.right,
        delta: {
          absolute: bin.delta,
          percent: Math.abs(bin.left) < 1e-12 ? null : (bin.delta / bin.left) * 100
        }
      }));
    }
    if (
      item.visualPayload.type === 'lognormal_pair' ||
      item.visualPayload.type === 'power_law_pair' ||
      item.visualPayload.type === 'buy_quad'
    ) {
      return item.visualPayload.parameters;
    }
    return [];
  }, [item]);

  return (
    <article className="compare-card">
      <header className="compare-card-header">
        <button type="button" className="card-toggle" onClick={() => setIsExpanded((current) => !current)}>
          <span className="card-toggle-indicator">{isExpanded ? '▾' : '▸'}</span>
          <span>
            <p className="group-chip">{item.group}</p>
            <h3>{item.title}</h3>
          </span>
        </button>
        <span className={`change-pill ${updated ? 'updated' : 'neutral'}`}>{updated ? 'Updated' : 'No change'}</span>
      </header>

      {isExpanded && (
        <>
          {(item.visualPayload.type === 'scalar' ||
            item.visualPayload.type === 'binned_distribution' ||
            item.visualPayload.type === 'lognormal_pair' ||
            item.visualPayload.type === 'power_law_pair' ||
            item.visualPayload.type === 'buy_quad') && (
            <div className="card-section">
              <button type="button" className="table-toggle" onClick={() => setIsTableOpen((current) => !current)}>
                {isTableOpen ? 'Hide parameter table' : 'Show parameter table'}
              </button>
              {isTableOpen && renderScalarTable(tableRows, mode)}
            </div>
          )}

          {item.visualPayload.type === 'scalar' && (
            <div className="card-section">
              <EChart
                option={
                  mode === 'single'
                    ? scalarSingleOption(
                        item.visualPayload.values,
                        item.rightVersion,
                        axisSpec.scalar.xTitle,
                        axisSpec.scalar.yTitle
                      )
                    : scalarOption(
                        item.visualPayload.values,
                        item.leftVersion,
                        item.rightVersion,
                        axisSpec.scalar.xTitle,
                        axisSpec.scalar.yTitle
                      )
                }
                className="chart"
              />
            </div>
          )}

          {item.visualPayload.type === 'binned_distribution' && (
            <div className="card-section">
              <EChart
                option={
                  mode === 'single'
                    ? binnedSingleOption(item, axisSpec.binned.xTitle, axisSpec.binned.yTitle)
                    : binnedOption(item, axisSpec.binned.xTitle, axisSpec.binned.yTitle, axisSpec.binned.yDeltaTitle)
                }
                className="chart"
              />
            </div>
          )}

          {item.visualPayload.type === 'joint_distribution' && jointRanges && (
            <div className="card-section">
              {mode === 'single' ? (
                <EChart
                  option={heatmapOption(
                    item.rightVersion,
                    item.visualPayload.matrix.right,
                    item.visualPayload.matrix.xAxis.labels,
                    item.visualPayload.matrix.yAxis.labels,
                    jointRanges.sharedMin,
                    jointRanges.sharedMax,
                    ['#eff6ff', '#1d4ed8'],
                    axisSpec.joint.xTitle,
                    axisSpec.joint.yTitle
                  )}
                  className="chart chart-heatmap"
                />
              ) : (
                <div className="heatmap-grid">
                  <EChart
                    option={heatmapOption(
                      item.leftVersion,
                      item.visualPayload.matrix.left,
                      item.visualPayload.matrix.xAxis.labels,
                      item.visualPayload.matrix.yAxis.labels,
                      jointRanges.sharedMin,
                      jointRanges.sharedMax,
                      ['#eff6ff', '#1d4ed8'],
                      axisSpec.joint.xTitle,
                      axisSpec.joint.yTitle
                    )}
                    className="chart chart-heatmap"
                  />
                  <EChart
                    option={heatmapOption(
                      item.rightVersion,
                      item.visualPayload.matrix.right,
                      item.visualPayload.matrix.xAxis.labels,
                      item.visualPayload.matrix.yAxis.labels,
                      jointRanges.sharedMin,
                      jointRanges.sharedMax,
                      ['#e8f7f6', '#18958b'],
                      axisSpec.joint.xTitle,
                      axisSpec.joint.yTitle
                    )}
                    className="chart chart-heatmap"
                  />
                  <EChart
                    option={heatmapOption(
                      'Delta',
                      item.visualPayload.matrix.delta,
                      item.visualPayload.matrix.xAxis.labels,
                      item.visualPayload.matrix.yAxis.labels,
                      jointRanges.deltaMin,
                      jointRanges.deltaMax,
                      ['#1d4ed8', '#f8fafc', '#18958b'],
                      axisSpec.joint.xTitle,
                      axisSpec.joint.yTitle
                    )}
                    className="chart chart-heatmap"
                  />
                </div>
              )}
            </div>
          )}

          {item.visualPayload.type === 'lognormal_pair' && (
            <div className="card-section">
              <EChart
                option={
                  mode === 'single'
                    ? curveSingleOption(
                        item.rightVersion,
                        item.visualPayload.curveRight,
                        axisSpec.curve.xTitle,
                        axisSpec.curve.yTitle,
                        (value) => formatNumber(value)
                      )
                    : curveOption(
                        item.leftVersion,
                        item.rightVersion,
                        item.visualPayload.curveLeft,
                        item.visualPayload.curveRight,
                        axisSpec.curve.xTitle,
                        axisSpec.curve.yTitle,
                        (value) => formatNumber(value)
                      )
                }
                className="chart"
              />
            </div>
          )}

          {item.visualPayload.type === 'power_law_pair' && (
            <div className="card-section">
              <EChart
                option={
                  mode === 'single'
                    ? curveSingleOption(
                        item.rightVersion,
                        item.visualPayload.curveRight,
                        axisSpec.curve.xTitle,
                        axisSpec.curve.yTitle,
                        (value) => formatNumber(value)
                      )
                    : curveOption(
                        item.leftVersion,
                        item.rightVersion,
                        item.visualPayload.curveLeft,
                        item.visualPayload.curveRight,
                        axisSpec.curve.xTitle,
                        axisSpec.curve.yTitle,
                        (value) => formatNumber(value)
                      )
                }
                className="chart"
              />
            </div>
          )}

          {item.visualPayload.type === 'buy_quad' && (
            <div className="card-section">
              <div className="kpi-inline">
                <p>Expected lognormal multiplier (E[exp(N)]):</p>
                {mode === 'single' ? (
                  <strong>{formatNumber(item.visualPayload.expectedMultiplier.right)}</strong>
                ) : (
                  <strong>
                    {formatNumber(item.visualPayload.expectedMultiplier.left)} vs{' '}
                    {formatNumber(item.visualPayload.expectedMultiplier.right)} ({' '}
                    {formatPercent(item.visualPayload.expectedMultiplier.delta.percent)})
                  </strong>
                )}
              </div>
              <EChart
                option={
                  mode === 'single'
                    ? curveSingleOption(
                        item.rightVersion,
                        item.visualPayload.budgetRight,
                        axisSpec.buyBudget.xTitle,
                        axisSpec.buyBudget.yTitle,
                        (value) => formatNumber(value)
                      )
                    : curveOption(
                        item.leftVersion,
                        item.rightVersion,
                        item.visualPayload.budgetLeft,
                        item.visualPayload.budgetRight,
                        axisSpec.buyBudget.xTitle,
                        axisSpec.buyBudget.yTitle,
                        (value) => formatNumber(value)
                      )
                }
                className="chart"
              />
              <EChart
                option={
                  mode === 'single'
                    ? curveSingleOption(
                        item.rightVersion,
                        item.visualPayload.multiplierRight,
                        axisSpec.buyMultiplier.xTitle,
                        axisSpec.buyMultiplier.yTitle,
                        (value) => formatNumber(value)
                      )
                    : curveOption(
                        item.leftVersion,
                        item.rightVersion,
                        item.visualPayload.multiplierLeft,
                        item.visualPayload.multiplierRight,
                        axisSpec.buyMultiplier.xTitle,
                        axisSpec.buyMultiplier.yTitle,
                        (value) => formatNumber(value)
                      )
                }
                className="chart"
              />
            </div>
          )}

          <div className="card-description">
            <p>{item.explanation}</p>
          </div>

          <div className="card-section">
            <button type="button" className="table-toggle" onClick={() => setIsMoreInfoOpen((current) => !current)}>
              {isMoreInfoOpen ? 'Hide provenance & sources' : 'Provenance & sources'}
            </button>
          </div>

          {isMoreInfoOpen && (
            <div className="card-meta">
              <div className="provenance-block">
                <h4>
                  {mode === 'single'
                    ? `Change provenance (through ${item.rightVersion})`
                    : `Change provenance (${item.leftVersion}, ${item.rightVersion}]`}
                </h4>
                {item.changeOriginsInRange.length === 0 ? (
                  <p className="provenance-empty">No tracked update metadata in selected scope.</p>
                ) : (
                  <ul className="provenance-list">
                    {item.changeOriginsInRange.map((origin) => (
                      <li key={`${item.id}-${origin.versionId}`}>
                        <div className="provenance-head">
                          <strong>{origin.versionId}</strong>
                          <span className={`validation-status ${origin.validationStatus}`}>
                            {validationStatusLabel(origin.validationStatus)}
                          </span>
                        </div>
                        <p>{origin.description}</p>
                        <p>
                          <b>Validation dataset:</b> {origin.validationDataset}
                        </p>
                        <p>
                          <b>Updated data sources:</b>{' '}
                          {origin.updatedDataSources.length > 0 ? origin.updatedDataSources.join(', ') : 'n/a'}
                        </p>
                        <p>
                          <b>Calibration files:</b> {origin.calibrationFiles.length > 0 ? origin.calibrationFiles.join(', ') : 'n/a'}
                        </p>
                        <p>
                          <b>Config parameters:</b> {origin.configParameters.length > 0 ? origin.configParameters.join(', ') : 'n/a'}
                        </p>
                        {origin.methodVariations.length > 0 && (
                          <div className="method-variation-block">
                            <p>
                              <b>Method improvements</b>
                            </p>
                            <ul>
                              {origin.methodVariations.map((variation, index) => (
                                <li key={`${origin.versionId}-variation-${index}`}>
                                  <p>
                                    <b>Scope:</b> {variation.configParameters.join(', ')}
                                  </p>
                                  <p>
                                    <b>Improvement:</b> {variation.improvementSummary}
                                  </p>
                                  <p>
                                    <b>Why:</b> {variation.whyChanged}
                                  </p>
                                  {variation.methodChosen && (
                                    <p>
                                      <b>Method chosen:</b> {variation.methodChosen}
                                    </p>
                                  )}
                                  {variation.decisionLogic && (
                                    <p>
                                      <b>Decision logic:</b> {variation.decisionLogic}
                                    </p>
                                  )}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <dl>
                <dt>Config keys</dt>
                <dd>{item.sourceInfo.configKeys.join(', ')}</dd>
                <dt>Left source</dt>
                <dd>
                  <code>{item.sourceInfo.configPathLeft}</code>
                  {item.sourceInfo.dataFilesLeft.map((file) => (
                    <div key={file}>
                      <code>{file}</code>
                    </div>
                  ))}
                </dd>
                <dt>Right source</dt>
                <dd>
                  <code>{item.sourceInfo.configPathRight}</code>
                  {item.sourceInfo.dataFilesRight.map((file) => (
                    <div key={file}>
                      <code>{file}</code>
                    </div>
                  ))}
                </dd>
              </dl>
            </div>
          )}
        </>
      )}
    </article>
  );
}
