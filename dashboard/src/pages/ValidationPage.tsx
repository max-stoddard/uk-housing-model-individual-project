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

const ORIGINAL_MODEL_LOSS = 11.83;

function formatPercent(value: number): string {
  return `${value.toLocaleString('en-GB', { maximumFractionDigits: 2 })}%`;
}

function buildChartOption(payload: ValidationTrendPayload): EChartsOption {
  const pointByVersion = new Map(payload.points.map((point) => [point.version, point]));
  const versions = payload.points.map((point) => point.version);
  const averageValues = payload.points.map((point) => point.averageAbsDiffPct);
  const inProgressValues = payload.points
    .filter((point) => point.status === 'in_progress')
    .map((point) => ({
      name: point.version,
      value: [point.version, point.averageAbsDiffPct]
    }));

  const averageReferenceMarkLine = {
    symbol: 'none',
    silent: true,
    data: [
      {
        yAxis: 0,
        lineStyle: { type: 'dashed' as const, width: 1.4, color: '#868e96' },
        label: { formatter: '0%', color: '#6c757d' }
      },
      {
        yAxis: ORIGINAL_MODEL_LOSS,
        lineStyle: { type: 'dotted' as const, width: 1.8, color: '#5f6b76' },
        label: { show: false }
      }
    ]
  };

  const tooltipFormatter = (rawParams: unknown) => {
    const rows = Array.isArray(rawParams) ? rawParams : [rawParams];
    const axisValue = String((rows[0] as { axisValueLabel?: string; axisValue?: string })?.axisValueLabel ?? (rows[0] as { axisValue?: string })?.axisValue ?? '');
    const point = pointByVersion.get(axisValue);
    if (!point) {
      return axisValue;
    }

    const detail = [
      `Average absolute diff: ${formatPercent(point.averageAbsDiffPct)}`,
      `Status: ${point.status === 'in_progress' ? 'In progress' : 'Complete'}`
    ];
    if (point.note) {
      detail.push(point.note);
    }
    return `${axisValue}<br/>${detail.join('<br/>')}`;
  };

  return {
    tooltip: { trigger: 'axis', formatter: tooltipFormatter },
    grid: { left: 84, right: 34, top: 18, bottom: 86, containLabel: true },
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
        markLine: averageReferenceMarkLine
      },
      {
        name: 'In progress',
        type: 'scatter',
        data: inProgressValues,
        symbol: 'diamond',
        symbolSize: 11,
        itemStyle: { color: '#f08c00', borderColor: '#fff4e6', borderWidth: 1.2 },
        emphasis: { scale: true },
        z: 4
      }
    ]
  };
}

export function ValidationPage() {
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
    return buildChartOption(payload);
  }, [payload]);

  return (
    <section className="validation-layout">
      <article className="results-card">
        <h2>Validation</h2>
        <p>
          This view tracks validation performance across successive calibration versions. Lower loss indicates closer
          agreement with observed data, providing clear evidence that the calibration process is improving model fit over
          time.
        </p>
      </article>

      {error && <p className="error-banner">{error}</p>}
      {isWaitingForApi && (
        <p className="waiting-banner">Waiting for API to become available. Retrying every 2 seconds...</p>
      )}

      <article className="results-card">
        <div className="validation-reference-row" aria-label="Validation benchmark reference">
          <span className="validation-reference-item">
            <span className="validation-reference-line validation-reference-line-original" aria-hidden="true" />
            <span>Original model loss</span>
            <strong>{formatPercent(ORIGINAL_MODEL_LOSS)}</strong>
          </span>
          <span className="validation-reference-item">
            <span className="validation-reference-dot validation-reference-dot-in-progress" aria-hidden="true" />
            <span>In progress version</span>
          </span>
        </div>

        {isLoading ? (
          <p className="loading-banner">Loading validation trend...</p>
        ) : option ? (
          <EChart option={option} className="chart validation-chart" />
        ) : (
          <p className="info-banner">No numeric R8 validation points are available to plot.</p>
        )}
      </article>
    </section>
  );
}
