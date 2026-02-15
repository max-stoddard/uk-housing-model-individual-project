import { useMemo, useState } from 'react';
import type { CompareResult, ScalarDatum } from '../../shared/types';
import { EChart } from './EChart';
import { getAxisSpec } from '../lib/chartAxes';
import { jointHeatmapOption } from '../lib/jointHeatmapOption';
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
  defaultExpanded?: boolean;
}

const formatNumber = formatChartNumber;

function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return 'n/a';
  }
  return `${value.toFixed(2)}%`;
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
                  option={jointHeatmapOption({
                    title: item.rightVersion,
                    cells: item.visualPayload.matrix.right,
                    xLabels: item.visualPayload.matrix.xAxis.labels,
                    yLabels: item.visualPayload.matrix.yAxis.labels,
                    min: jointRanges.sharedMin,
                    max: jointRanges.sharedMax,
                    colors: ['#eff6ff', '#1d4ed8'],
                    xAxisName: axisSpec.joint.xTitle,
                    yAxisName: axisSpec.joint.yTitle,
                    layout: jointLayoutOverrides(item.id)
                  })}
                  className="chart chart-heatmap"
                />
              ) : (
                <div className="heatmap-grid">
                  <EChart
                    option={jointHeatmapOption({
                      title: item.leftVersion,
                      cells: item.visualPayload.matrix.left,
                      xLabels: item.visualPayload.matrix.xAxis.labels,
                      yLabels: item.visualPayload.matrix.yAxis.labels,
                      min: jointRanges.sharedMin,
                      max: jointRanges.sharedMax,
                      colors: ['#eff6ff', '#1d4ed8'],
                      xAxisName: axisSpec.joint.xTitle,
                      yAxisName: axisSpec.joint.yTitle,
                      layout: jointLayoutOverrides(item.id)
                    })}
                    className="chart chart-heatmap"
                  />
                  <EChart
                    option={jointHeatmapOption({
                      title: item.rightVersion,
                      cells: item.visualPayload.matrix.right,
                      xLabels: item.visualPayload.matrix.xAxis.labels,
                      yLabels: item.visualPayload.matrix.yAxis.labels,
                      min: jointRanges.sharedMin,
                      max: jointRanges.sharedMax,
                      colors: ['#e8f7f6', '#18958b'],
                      xAxisName: axisSpec.joint.xTitle,
                      yAxisName: axisSpec.joint.yTitle,
                      layout: jointLayoutOverrides(item.id)
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
                      layout: jointLayoutOverrides(item.id)
                    })}
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
