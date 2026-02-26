// Author: Max Stoddard
import { useEffect, useMemo, useState } from 'react';
import type { EChartsOption } from 'echarts';
import type { ValidationTrendPayload } from '../../shared/types';
import { EChart } from '../components/EChart';
import {
  API_RETRY_DELAY_MS,
  fetchValidationTrend,
  isRetryableApiError
} from '../lib/api';

type ValidationMode = 'three_lines' | 'average';

function formatPercent(value: number): string {
  return `${value.toLocaleString('en-GB', { maximumFractionDigits: 2 })}%`;
}

function buildChartOption(payload: ValidationTrendPayload, mode: ValidationMode): EChartsOption {
  const versions = payload.points.map((point) => point.version);
  const incomeValues = payload.points.map((point) => point.incomeDiffPct);
  const housingValues = payload.points.map((point) => point.housingWealthDiffPct);
  const financialValues = payload.points.map((point) => point.financialWealthDiffPct);
  const averageValues = payload.points.map((point) => point.averageAbsDiffPct);

  const baselineMarkLine = {
    symbol: 'none',
    silent: true,
    lineStyle: { type: 'dashed' as const, width: 1.4, color: '#868e96' },
    label: { formatter: '0%', color: '#6c757d' },
    data: [{ yAxis: 0 }]
  };

  const tooltipFormatter = (rawParams: unknown) => {
    const rows = Array.isArray(rawParams) ? rawParams : [rawParams];
    const axisValue = String((rows[0] as { axisValueLabel?: string; axisValue?: string })?.axisValueLabel ?? (rows[0] as { axisValue?: string })?.axisValue ?? '');
    const detail = rows
      .map((row) => {
        const typed = row as { seriesName?: string; data?: number };
        const value = typeof typed.data === 'number' ? typed.data : 0;
        return `${typed.seriesName ?? ''}: ${formatPercent(value)}`;
      })
      .join('<br/>');
    return `${axisValue}<br/>${detail}`;
  };

  if (mode === 'average') {
    return {
      tooltip: { trigger: 'axis', formatter: tooltipFormatter },
      legend: { top: 0, data: ['Average absolute diff'] },
      grid: { left: 84, right: 34, top: 44, bottom: 86, containLabel: true },
      xAxis: {
        type: 'category',
        data: versions,
        name: 'Version',
        nameLocation: 'middle',
        nameGap: 54,
        nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' }
      },
      yAxis: {
        type: 'value',
        name: 'Diff percentile (%)',
        nameLocation: 'middle',
        nameGap: 64,
        nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' },
        axisLabel: {
          formatter: (rawValue: number) => `${Number(rawValue).toLocaleString('en-GB', { maximumFractionDigits: 2 })}%`
        },
        min: (extent: { min: number }) => Math.min(0, extent.min),
        max: (extent: { max: number }) => Math.max(0, extent.max)
      },
      series: [
        {
          name: 'Average absolute diff',
          type: 'line',
          smooth: true,
          showSymbol: true,
          symbolSize: 6,
          data: averageValues,
          lineStyle: { color: '#0b7285', width: 2.2 },
          itemStyle: { color: '#0b7285' },
          markLine: baselineMarkLine
        }
      ]
    };
  }

  return {
    tooltip: { trigger: 'axis', formatter: tooltipFormatter },
    legend: { top: 0, data: ['Income diff', 'Housing wealth diff', 'Financial wealth diff'] },
    grid: { left: 84, right: 34, top: 44, bottom: 86, containLabel: true },
    xAxis: {
      type: 'category',
      data: versions,
      name: 'Version',
      nameLocation: 'middle',
      nameGap: 54,
      nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' }
    },
    yAxis: {
      type: 'value',
      name: 'Diff percentile (%)',
      nameLocation: 'middle',
      nameGap: 64,
      nameTextStyle: { fontSize: 12, fontWeight: 600, color: '#495057' },
      axisLabel: {
        formatter: (rawValue: number) => `${Number(rawValue).toLocaleString('en-GB', { maximumFractionDigits: 2 })}%`
      },
      min: (extent: { min: number }) => Math.min(0, extent.min),
      max: (extent: { max: number }) => Math.max(0, extent.max)
    },
    series: [
      {
        name: 'Income diff',
        type: 'line',
        smooth: true,
        showSymbol: true,
        symbolSize: 6,
        data: incomeValues,
        lineStyle: { color: '#0b7285', width: 2.2 },
        itemStyle: { color: '#0b7285' },
        markLine: baselineMarkLine
      },
      {
        name: 'Housing wealth diff',
        type: 'line',
        smooth: true,
        showSymbol: true,
        symbolSize: 6,
        data: housingValues,
        lineStyle: { color: '#2f9e44', width: 2.2 },
        itemStyle: { color: '#2f9e44' }
      },
      {
        name: 'Financial wealth diff',
        type: 'line',
        smooth: true,
        showSymbol: true,
        symbolSize: 6,
        data: financialValues,
        lineStyle: { color: '#1971c2', width: 2.2 },
        itemStyle: { color: '#1971c2' }
      }
    ]
  };
}

export function ValidationPage() {
  const [mode, setMode] = useState<ValidationMode>('three_lines');
  const [payload, setPayload] = useState<ValidationTrendPayload | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isWaitingForApi, setIsWaitingForApi] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    let cancelled = false;
    let retryTimer: number | undefined;

    const load = async () => {
      setIsLoading(true);
      setIsWaitingForApi(false);
      setError('');

      try {
        const response = await fetchValidationTrend();
        if (cancelled) {
          return;
        }
        setPayload(response);
      } catch (loadError) {
        if (cancelled) {
          return;
        }
        if (isRetryableApiError(loadError)) {
          setIsWaitingForApi(true);
          retryTimer = window.setTimeout(() => {
            void load();
          }, API_RETRY_DELAY_MS);
          return;
        }
        setError((loadError as Error).message);
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
      if (retryTimer !== undefined) {
        window.clearTimeout(retryTimer);
      }
    };
  }, []);

  const option = useMemo(() => {
    if (!payload || payload.points.length === 0) {
      return null;
    }
    return buildChartOption(payload, mode);
  }, [payload, mode]);

  return (
    <section className="validation-layout">
      <article className="results-card">
        <h2>Validation</h2>
        <p>
          Validation trends from <code>input-data-versions/version-notes.json</code> using dataset <code>r8</code>. Lower
          values closer to <code>0%</code> indicate better agreement.
        </p>
      </article>

      {error && <p className="error-banner">{error}</p>}
      {isWaitingForApi && (
        <p className="waiting-banner">Waiting for API to become available. Retrying every 2 seconds...</p>
      )}

      <article className="results-card">
        <div className="validation-mode-row">
          <button
            type="button"
            className={`filter-pill ${mode === 'three_lines' ? 'active' : ''}`}
            onClick={() => setMode('three_lines')}
          >
            Three lines
          </button>
          <button
            type="button"
            className={`filter-pill ${mode === 'average' ? 'active' : ''}`}
            onClick={() => setMode('average')}
          >
            Average
          </button>
        </div>

        {isLoading ? (
          <p className="loading-banner">Loading validation trend...</p>
        ) : option ? (
          <EChart option={option} className="chart validation-chart" />
        ) : (
          <p className="info-banner">No complete R8 validation points are available to plot.</p>
        )}
      </article>
    </section>
  );
}
