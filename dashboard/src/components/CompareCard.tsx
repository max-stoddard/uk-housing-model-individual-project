import { useMemo, useState } from 'react';
import type { EChartsOption } from 'echarts';
import type { CompareResult, JointCell, ScalarDatum } from '../../shared/types';
import { EChart } from './EChart';

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

function scalarOption(values: ScalarDatum[], leftVersion: string, rightVersion: string): EChartsOption {
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 40, right: 24, top: 36, bottom: 70 },
    xAxis: {
      type: 'category',
      data: values.map((entry) => entry.key),
      axisLabel: { rotate: 25 }
    },
    yAxis: { type: 'value' },
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

function scalarSingleOption(values: ScalarDatum[], version: string): EChartsOption {
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 40, right: 24, top: 36, bottom: 70 },
    xAxis: {
      type: 'category',
      data: values.map((entry) => entry.key),
      axisLabel: { rotate: 25 }
    },
    yAxis: { type: 'value' },
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

function binnedOption(item: CompareResult): EChartsOption {
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
    grid: { left: 48, right: 42, top: 36, bottom: 80 },
    xAxis: {
      type: 'category',
      data: item.visualPayload.bins.map((bin) => bin.label),
      axisLabel: { rotate: 35 }
    },
    yAxis: [
      { type: 'value', name: 'Value' },
      { type: 'value', name: 'Delta', position: 'right' }
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

function binnedSingleOption(item: CompareResult): EChartsOption {
  if (item.visualPayload.type !== 'binned_distribution') {
    return {};
  }

  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 48, right: 24, top: 36, bottom: 80 },
    xAxis: {
      type: 'category',
      data: item.visualPayload.bins.map((bin) => bin.label),
      axisLabel: { rotate: 35 }
    },
    yAxis: [{ type: 'value', name: 'Value' }],
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
  colors: string[]
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
    grid: { left: 92, right: 16, top: 34, bottom: 118, containLabel: false },
    xAxis: {
      type: 'category',
      data: xLabels,
      axisLabel: { rotate: 45, fontSize: 9, margin: 14 }
    },
    yAxis: {
      type: 'category',
      data: yLabels,
      axisLabel: { fontSize: 9, margin: 10 }
    },
    visualMap: {
      min,
      max,
      orient: 'horizontal',
      left: 'center',
      bottom: 10,
      calculable: false,
      precision: 6,
      formatter: '{value}',
      itemWidth: 12,
      itemHeight: 180,
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
        return `${xLabel}: ${xText}<br/>${leftVersion}: ${formatNumber(left)}<br/>${rightVersion}: ${formatNumber(right)}`;
      }
    },
    legend: { top: 0 },
    grid: { left: 56, right: 28, top: 36, bottom: 56 },
    xAxis: {
      type: 'value',
      name: xLabel,
      nameLocation: 'middle',
      nameGap: 34
    },
    yAxis: {
      type: 'value',
      name: yLabel,
      nameLocation: 'middle',
      nameGap: 42
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
        return `${xLabel}: ${xText}<br/>${version}: ${formatNumber(value)}`;
      }
    },
    legend: { top: 0 },
    grid: { left: 56, right: 28, top: 36, bottom: 56 },
    xAxis: {
      type: 'value',
      name: xLabel,
      nameLocation: 'middle',
      nameGap: 34
    },
    yAxis: {
      type: 'value',
      name: yLabel,
      nameLocation: 'middle',
      nameGap: 42
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
                    ? scalarSingleOption(item.visualPayload.values, item.rightVersion)
                    : scalarOption(item.visualPayload.values, item.leftVersion, item.rightVersion)
                }
                className="chart"
              />
            </div>
          )}

          {item.visualPayload.type === 'binned_distribution' && (
            <div className="card-section">
              <EChart option={mode === 'single' ? binnedSingleOption(item) : binnedOption(item)} className="chart" />
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
                    ['#eff6ff', '#1d4ed8']
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
                      ['#eff6ff', '#1d4ed8']
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
                      ['#e8f7f6', '#18958b']
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
                      ['#1d4ed8', '#f8fafc', '#18958b']
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
                    ? curveSingleOption(item.rightVersion, item.visualPayload.curveRight, 'Value', 'Density', (value) =>
                        formatNumber(value)
                      )
                    : curveOption(
                        item.leftVersion,
                        item.rightVersion,
                        item.visualPayload.curveLeft,
                        item.visualPayload.curveRight,
                        'Value',
                        'Density',
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
                    ? curveSingleOption(item.rightVersion, item.visualPayload.curveRight, 'Income', 'Desired Rent', (value) =>
                        formatNumber(value)
                      )
                    : curveOption(
                        item.leftVersion,
                        item.rightVersion,
                        item.visualPayload.curveLeft,
                        item.visualPayload.curveRight,
                        'Income',
                        'Desired Rent',
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
                    ? curveSingleOption(item.rightVersion, item.visualPayload.budgetRight, 'Income', 'Buy Budget', (value) =>
                        formatNumber(value)
                      )
                    : curveOption(
                        item.leftVersion,
                        item.rightVersion,
                        item.visualPayload.budgetLeft,
                        item.visualPayload.budgetRight,
                        'Income',
                        'Buy Budget',
                        (value) => formatNumber(value)
                      )
                }
                className="chart"
              />
              <EChart
                option={
                  mode === 'single'
                    ? curveSingleOption(item.rightVersion, item.visualPayload.multiplierRight, 'Multiplier', 'Density', (value) =>
                        formatNumber(value)
                      )
                    : curveOption(
                        item.leftVersion,
                        item.rightVersion,
                        item.visualPayload.multiplierLeft,
                        item.visualPayload.multiplierRight,
                        'Multiplier',
                        'Density',
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
