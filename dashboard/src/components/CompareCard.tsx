import { useMemo, useState } from 'react';
import type { CompareResult, ScalarDatum } from '../../shared/types';
import { EChart } from './EChart';
import { getAxisSpec } from '../lib/chartAxes';
import { jointHeatmapOption, resolveAdaptiveHeatmapLayout } from '../lib/jointHeatmapOption';
import {
  binnedOption,
  binnedSingleOption,
  curveOption,
  curveSingleOption,
  formatChartNumber,
  jointLayoutOverrides,
  scalarOption,
  scalarSingleOption
} from '../lib/compareChartOptions';

interface CompareCardProps {
  item: CompareResult;
  mode: 'single' | 'compare';
  inProgressVersions: string[];
  defaultExpanded?: boolean;
}

const formatNumber = formatChartNumber;

function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return 'n/a';
  }
  return `${value.toFixed(2)}%`;
}

function formatProbability(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

function formatProbabilityDelta(value: number): string {
  const percentagePoints = value * 100;
  const sign = percentagePoints >= 0 ? '+' : '';
  return `${sign}${percentagePoints.toFixed(2)} pp`;
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

function withInProgressLabel(version: string, inProgressVersions: Set<string>): string {
  return inProgressVersions.has(version) ? `${version} (In progress)` : version;
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

function buildAdaptiveHeatmapLayout(
  context: 'compare' | 'single' | 'preview',
  item: CompareResult,
  axisSpec: ReturnType<typeof getAxisSpec>,
  xLabels: string[],
  yLabels: string[]
) {
  const baseLayout = jointLayoutOverrides(item.id);
  return resolveAdaptiveHeatmapLayout({
    context,
    xLabels,
    yLabels,
    xAxisName: axisSpec.joint.xTitle,
    yAxisName: axisSpec.joint.yTitle,
    layout: baseLayout
  });
}

export function CompareCard({ item, mode, inProgressVersions, defaultExpanded = false }: CompareCardProps) {
  const [isExpanded, setIsExpanded] = useState<boolean>(defaultExpanded);
  const [isTableOpen, setIsTableOpen] = useState<boolean>(false);
  const [isMoreInfoOpen, setIsMoreInfoOpen] = useState<boolean>(false);

  const updated = itemIsUpdated(item, mode);
  const inProgressVersionSet = useMemo(() => new Set(inProgressVersions), [inProgressVersions]);
  const leftVersionLabel = useMemo(
    () => withInProgressLabel(item.leftVersion, inProgressVersionSet),
    [item.leftVersion, inProgressVersionSet]
  );
  const rightVersionLabel = useMemo(
    () => withInProgressLabel(item.rightVersion, inProgressVersionSet),
    [item.rightVersion, inProgressVersionSet]
  );
  const hasInProgressOrigin = useMemo(
    () => item.changeOriginsInRange.some((origin) => origin.validationStatus === 'in_progress'),
    [item.changeOriginsInRange]
  );
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
      item.visualPayload.type === 'gaussian_pair' ||
      item.visualPayload.type === 'hpa_expectation_line' ||
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
        <div className="card-status-pills">
          {hasInProgressOrigin && <span className="status-pill-in-progress">In progress</span>}
          <span className={`change-pill ${updated ? 'updated' : 'neutral'}`}>{updated ? 'Updated' : 'No change'}</span>
        </div>
      </header>

      {isExpanded && (
        <>
          {(item.visualPayload.type === 'scalar' ||
            item.visualPayload.type === 'binned_distribution' ||
            item.visualPayload.type === 'lognormal_pair' ||
            item.visualPayload.type === 'power_law_pair' ||
            item.visualPayload.type === 'gaussian_pair' ||
            item.visualPayload.type === 'hpa_expectation_line' ||
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
                        rightVersionLabel,
                        axisSpec.scalar.xTitle,
                        axisSpec.scalar.yTitle
                      )
                    : scalarOption(
                        item.visualPayload.values,
                        leftVersionLabel,
                        rightVersionLabel,
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
                    ? binnedSingleOption(item, axisSpec.binned.xTitle, axisSpec.binned.yTitle, rightVersionLabel)
                    : binnedOption(item, axisSpec.binned.xTitle, axisSpec.binned.yTitle, axisSpec.binned.yDeltaTitle, {
                        leftLabel: leftVersionLabel,
                        rightLabel: rightVersionLabel
                      })
                }
                className="chart"
              />
            </div>
          )}

          {item.visualPayload.type === 'joint_distribution' && jointRanges && (
            <div className="card-section">
              {mode === 'single' ? (
                <EChart
                  option={jointHeatmapOption({
                    title: rightVersionLabel,
                    cells: item.visualPayload.matrix.right,
                    xLabels: item.visualPayload.matrix.xAxis.labels,
                    yLabels: item.visualPayload.matrix.yAxis.labels,
                    min: jointRanges.sharedMin,
                    max: jointRanges.sharedMax,
                    colors: ['#eff6ff', '#1d4ed8'],
                    xAxisName: axisSpec.joint.xTitle,
                    yAxisName: axisSpec.joint.yTitle,
                    layout: buildAdaptiveHeatmapLayout(
                      'single',
                      item,
                      axisSpec,
                      item.visualPayload.matrix.xAxis.labels,
                      item.visualPayload.matrix.yAxis.labels
                    )
                  })}
                  className="chart chart-heatmap"
                />
              ) : (
                <div className="heatmap-scroll">
                  <div className="heatmap-grid heatmap-grid-compare">
                    <EChart
                      option={jointHeatmapOption({
                        title: leftVersionLabel,
                        cells: item.visualPayload.matrix.left,
                        xLabels: item.visualPayload.matrix.xAxis.labels,
                        yLabels: item.visualPayload.matrix.yAxis.labels,
                        min: jointRanges.sharedMin,
                        max: jointRanges.sharedMax,
                        colors: ['#eff6ff', '#1d4ed8'],
                        xAxisName: axisSpec.joint.xTitle,
                        yAxisName: axisSpec.joint.yTitle,
                        layout: buildAdaptiveHeatmapLayout(
                          'compare',
                          item,
                          axisSpec,
                          item.visualPayload.matrix.xAxis.labels,
                          item.visualPayload.matrix.yAxis.labels
                        )
                      })}
                      className="chart chart-heatmap"
                    />
                    <EChart
                      option={jointHeatmapOption({
                        title: rightVersionLabel,
                        cells: item.visualPayload.matrix.right,
                        xLabels: item.visualPayload.matrix.xAxis.labels,
                        yLabels: item.visualPayload.matrix.yAxis.labels,
                        min: jointRanges.sharedMin,
                        max: jointRanges.sharedMax,
                        colors: ['#e8f7f6', '#18958b'],
                        xAxisName: axisSpec.joint.xTitle,
                        yAxisName: axisSpec.joint.yTitle,
                        layout: buildAdaptiveHeatmapLayout(
                          'compare',
                          item,
                          axisSpec,
                          item.visualPayload.matrix.xAxis.labels,
                          item.visualPayload.matrix.yAxis.labels
                        )
                      })}
                      className="chart chart-heatmap"
                    />
                    <EChart
                      option={jointHeatmapOption({
                        title: 'Delta',
                        cells: item.visualPayload.matrix.delta,
                        xLabels: item.visualPayload.matrix.xAxis.labels,
                        yLabels: item.visualPayload.matrix.yAxis.labels,
                        min: jointRanges.deltaMin,
                        max: jointRanges.deltaMax,
                        colors: ['#1d4ed8', '#f8fafc', '#18958b'],
                        xAxisName: axisSpec.joint.xTitle,
                        yAxisName: axisSpec.joint.yTitle,
                        layout: buildAdaptiveHeatmapLayout(
                          'compare',
                          item,
                          axisSpec,
                          item.visualPayload.matrix.xAxis.labels,
                          item.visualPayload.matrix.yAxis.labels
                        )
                      })}
                      className="chart chart-heatmap"
                    />
                  </div>
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
                        rightVersionLabel,
                        item.visualPayload.curveRight,
                        axisSpec.curve.xTitle,
                        axisSpec.curve.yTitle,
                        (value) => formatNumber(value)
                      )
                    : curveOption(
                        leftVersionLabel,
                        rightVersionLabel,
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
                        rightVersionLabel,
                        item.visualPayload.curveRight,
                        axisSpec.curve.xTitle,
                        axisSpec.curve.yTitle,
                        (value) => formatNumber(value)
                      )
                    : curveOption(
                        leftVersionLabel,
                        rightVersionLabel,
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

          {item.visualPayload.type === 'gaussian_pair' && (
            <div className="card-section">
              <div className="kpi-inline">
                <p>Log-reduction Gaussian:</p>
              </div>
              <EChart
                option={
                  mode === 'single'
                    ? curveSingleOption(
                        rightVersionLabel,
                        item.visualPayload.logCurveRight,
                        axisSpec.curve.xTitle,
                        axisSpec.curve.yTitle,
                        (value) => formatNumber(value)
                      )
                    : curveOption(
                        leftVersionLabel,
                        rightVersionLabel,
                        item.visualPayload.logCurveLeft,
                        item.visualPayload.logCurveRight,
                        axisSpec.curve.xTitle,
                        axisSpec.curve.yTitle,
                        (value) => formatNumber(value)
                      )
                }
                className="chart"
              />
              <div className="kpi-inline">
                <p>Implied percent-reduction density:</p>
              </div>
              <div className="kpi-inline">
                <p>Clipped tail mass at {item.visualPayload.percentCap}% cap:</p>
                {mode === 'single' ? (
                  <strong>{formatProbability(item.visualPayload.percentCapMassRight)}</strong>
                ) : (
                  <strong>
                    {formatProbability(item.visualPayload.percentCapMassLeft)} vs{' '}
                    {formatProbability(item.visualPayload.percentCapMassRight)} ({' '}
                    <span
                      className={deltaClassName(
                        item.visualPayload.percentCapMassRight - item.visualPayload.percentCapMassLeft
                      )}
                    >
                      {formatProbabilityDelta(
                        item.visualPayload.percentCapMassRight - item.visualPayload.percentCapMassLeft
                      )}
                    </span>
                    )
                  </strong>
                )}
              </div>
              <EChart
                option={
                  mode === 'single'
                    ? curveSingleOption(
                        rightVersionLabel,
                        item.visualPayload.percentCurveRight,
                        axisSpec.buyMultiplier.xTitle,
                        axisSpec.buyMultiplier.yTitle,
                        (value) => formatNumber(value),
                        item.visualPayload.percentCap,
                        `${item.visualPayload.percentCap}% cap`
                      )
                    : curveOption(
                        leftVersionLabel,
                        rightVersionLabel,
                        item.visualPayload.percentCurveLeft,
                        item.visualPayload.percentCurveRight,
                        axisSpec.buyMultiplier.xTitle,
                        axisSpec.buyMultiplier.yTitle,
                        (value) => formatNumber(value),
                        item.visualPayload.percentCap,
                        `${item.visualPayload.percentCap}% cap`
                      )
                }
                className="chart"
              />
            </div>
          )}

          {item.visualPayload.type === 'hpa_expectation_line' && (
            <div className="card-section">
              <div className="kpi-inline">
                <p>Expected annual change line with DT={item.visualPayload.dt}:</p>
              </div>
              <EChart
                option={
                  mode === 'single'
                    ? curveSingleOption(
                        rightVersionLabel,
                        item.visualPayload.curveRight,
                        axisSpec.curve.xTitle,
                        axisSpec.curve.yTitle,
                        (value) => formatNumber(value)
                      )
                    : curveOption(
                        leftVersionLabel,
                        rightVersionLabel,
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
                        rightVersionLabel,
                        item.visualPayload.budgetRight,
                        axisSpec.buyBudget.xTitle,
                        axisSpec.buyBudget.yTitle,
                        (value) => formatNumber(value)
                      )
                    : curveOption(
                        leftVersionLabel,
                        rightVersionLabel,
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
                        rightVersionLabel,
                        item.visualPayload.multiplierRight,
                        axisSpec.buyMultiplier.xTitle,
                        axisSpec.buyMultiplier.yTitle,
                        (value) => formatNumber(value)
                      )
                    : curveOption(
                        leftVersionLabel,
                        rightVersionLabel,
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
