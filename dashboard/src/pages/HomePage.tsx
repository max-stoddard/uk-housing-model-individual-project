import { Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import type { EChartsOption } from 'echarts';
import type { CompareResult } from '../../shared/types';
import { fetchCatalog, fetchCompare, fetchGitStats, fetchVersions } from '../lib/api';
import { EChart } from '../components/EChart';
import { getAxisSpec } from '../lib/chartAxes';

const PREVIEW_PARAMETER_IDS = [
  'wealth_given_income_joint',
  'house_price_lognormal',
  'downpayment_oo_lognormal',
  'btl_probability_bins'
];

function formatPreviewNumber(value: number): string {
  if (Math.abs(value) >= 1000) {
    return value.toLocaleString('en-GB', { maximumFractionDigits: 0 });
  }
  if (Math.abs(value) >= 1) {
    return value.toLocaleString('en-GB', { maximumFractionDigits: 4 });
  }
  return value.toLocaleString('en-GB', { maximumFractionDigits: 8 });
}

function formatPreviewScientific(value: number, digits = 2): string {
  const [mantissa, exponent] = value.toExponential(digits).split('e');
  const trimmedMantissa = mantissa.replace(/\.?0+$/, '');
  const normalizedExponent = exponent.replace('+', '').replace(/^(-?)0+(\d)/, '$1$2');
  return `${trimmedMantissa}e${normalizedExponent}`;
}

function formatPreviewCurveValue(value: number): string {
  const absolute = Math.abs(value);
  if (absolute < 1e-12) {
    return '0';
  }
  if (absolute < 0.001) {
    return formatPreviewScientific(value, 2);
  }
  if (absolute < 1) {
    return value.toLocaleString('en-GB', { maximumFractionDigits: 6 });
  }
  return formatPreviewNumber(value);
}

function formatPreviewAxisTick(value: number): string {
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
  return formatPreviewScientific(value, 1);
}

function buildPreviewOption(item: CompareResult): EChartsOption {
  const axisSpec = getAxisSpec(item.id);

  switch (item.visualPayload.type) {
    case 'scalar': {
      const payload = item.visualPayload;
      return {
        tooltip: { trigger: 'axis' },
        grid: { left: 58, right: 20, top: 28, bottom: 84, containLabel: true },
        xAxis: {
          type: 'category',
          data: payload.values.map((value) => value.key),
          axisLabel: { rotate: 25, fontSize: 10 },
          name: axisSpec.scalar.xTitle,
          nameLocation: 'middle',
          nameGap: 54,
          nameTextStyle: { fontSize: 10 }
        },
        yAxis: {
          type: 'value',
          name: axisSpec.scalar.yTitle,
          nameLocation: 'middle',
          nameGap: 46,
          nameTextStyle: { fontSize: 10 }
        },
        series: [
          {
            name: item.rightVersion,
            type: 'bar',
            data: payload.values.map((value) => value.right),
            itemStyle: { color: '#0b7285' }
          }
        ]
      };
    }

    case 'binned_distribution': {
      const payload = item.visualPayload;
      return {
        tooltip: { trigger: 'axis' },
        grid: { left: 62, right: 20, top: 28, bottom: 90, containLabel: true },
        xAxis: {
          type: 'category',
          data: payload.bins.map((bin) => bin.label),
          axisLabel: { rotate: 32, fontSize: 10 },
          name: axisSpec.binned.xTitle,
          nameLocation: 'middle',
          nameGap: 56,
          nameTextStyle: { fontSize: 10 }
        },
        yAxis: {
          type: 'value',
          name: axisSpec.binned.yTitle,
          nameLocation: 'middle',
          nameGap: 48,
          nameTextStyle: { fontSize: 10 }
        },
        series: [
          {
            name: item.rightVersion,
            type: 'bar',
            data: payload.bins.map((bin) => bin.right),
            itemStyle: { color: 'rgba(11, 114, 133, 0.74)' }
          }
        ]
      };
    }

    case 'joint_distribution': {
      const payload = item.visualPayload;
      const values = payload.matrix.right.map((cell) => cell.value);
      const min = Math.min(...values);
      const max = Math.max(...values);
      return {
        tooltip: {
          trigger: 'item',
          confine: true,
          transitionDuration: 0.12,
          formatter: (param: any) => {
            const [xIndex, yIndex, value] = param.data as [number, number, number];
            const xLabel = payload.matrix.xAxis.labels[xIndex];
            const yLabel = payload.matrix.yAxis.labels[yIndex];
            return `${xLabel} / ${yLabel}<br/>${formatPreviewNumber(value)}`;
          }
        },
        grid: { left: 106, right: 56, top: 28, bottom: 84, containLabel: true },
        xAxis: {
          type: 'category',
          data: payload.matrix.xAxis.labels,
          axisLabel: { rotate: 38, fontSize: 10, margin: 10 },
          name: axisSpec.joint.xTitle,
          nameLocation: 'middle',
          nameGap: 46,
          nameTextStyle: { fontSize: 10 }
        },
        yAxis: {
          type: 'category',
          data: payload.matrix.yAxis.labels,
          axisLabel: { fontSize: 10, margin: 8 },
          name: axisSpec.joint.yTitle,
          nameLocation: 'middle',
          nameGap: 88,
          nameTextStyle: { fontSize: 10 }
        },
        visualMap: {
          show: true,
          type: 'continuous',
          min,
          max,
          orient: 'vertical',
          right: 8,
          top: 'middle',
          calculable: false,
          realtime: true,
          showLabel: false,
          precision: 8,
          formatter: '{value}',
          itemWidth: 10,
          itemHeight: 136,
          text: ['High', 'Low'],
          textGap: 6,
          textStyle: { color: '#495057', fontSize: 9 },
          inRange: { color: ['#eff6ff', '#1d4ed8'] }
        },
        series: [
          {
            type: 'heatmap',
            data: payload.matrix.right.map((cell) => [cell.xIndex, cell.yIndex, cell.value]),
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

    case 'lognormal_pair':
    case 'power_law_pair': {
      const payload = item.visualPayload;
      return {
        tooltip: {
          trigger: 'axis',
          formatter: (rawParams: unknown) => {
            const rows = Array.isArray(rawParams) ? rawParams : [rawParams];
            const xValue = Number((rows[0] as any)?.axisValue ?? 0);
            const point = (rows[0] as any)?.data;
            const yValue = Array.isArray(point) ? Number(point[1]) : 0;
            return `${axisSpec.curve.xTitle}: ${formatPreviewNumber(xValue)}<br/>${item.rightVersion}: ${formatPreviewCurveValue(
              yValue
            )}`;
          }
        },
        grid: { left: 62, right: 18, top: 28, bottom: 78, containLabel: true },
        xAxis: {
          type: 'value',
          name: axisSpec.curve.xTitle,
          nameLocation: 'middle',
          nameGap: 46,
          nameTextStyle: { fontSize: 10 }
        },
        yAxis: {
          type: 'value',
          name: axisSpec.curve.yTitle,
          nameLocation: 'middle',
          nameGap: 46,
          nameTextStyle: { fontSize: 10 },
          axisLabel: {
            formatter: (rawValue: number) => formatPreviewAxisTick(Number(rawValue))
          }
        },
        series: [
          {
            type: 'line',
            showSymbol: false,
            smooth: true,
            data: payload.curveRight.map((point) => [point.x, point.y]),
            lineStyle: { color: '#0b7285', width: 2 }
          }
        ]
      };
    }

    case 'buy_quad': {
      const payload = item.visualPayload;
      return {
        tooltip: {
          trigger: 'axis',
          formatter: (rawParams: unknown) => {
            const rows = Array.isArray(rawParams) ? rawParams : [rawParams];
            const xValue = Number((rows[0] as any)?.axisValue ?? 0);
            const point = (rows[0] as any)?.data;
            const yValue = Array.isArray(point) ? Number(point[1]) : 0;
            return `${axisSpec.buyBudget.xTitle}: ${formatPreviewNumber(xValue)}<br/>${item.rightVersion}: ${formatPreviewCurveValue(
              yValue
            )}`;
          }
        },
        grid: { left: 62, right: 18, top: 28, bottom: 78, containLabel: true },
        xAxis: {
          type: 'value',
          name: axisSpec.buyBudget.xTitle,
          nameLocation: 'middle',
          nameGap: 46,
          nameTextStyle: { fontSize: 10 }
        },
        yAxis: {
          type: 'value',
          name: axisSpec.buyBudget.yTitle,
          nameLocation: 'middle',
          nameGap: 46,
          nameTextStyle: { fontSize: 10 },
          axisLabel: {
            formatter: (rawValue: number) => formatPreviewAxisTick(Number(rawValue))
          }
        },
        series: [
          {
            type: 'line',
            showSymbol: false,
            smooth: true,
            data: payload.budgetRight.map((point) => [point.x, point.y]),
            lineStyle: { color: '#0b7285', width: 2 }
          }
        ]
      };
    }

    default:
      return {};
  }
}

export function HomePage() {
  const [versionsCount, setVersionsCount] = useState<number>(0);
  const [latestVersion, setLatestVersion] = useState<string>('...');
  const [cardsCount, setCardsCount] = useState<number>(0);
  const [filesChanged, setFilesChanged] = useState<number>(0);
  const [linesWritten, setLinesWritten] = useState<number>(0);
  const [commitCount, setCommitCount] = useState<number>(0);
  const [previewItems, setPreviewItems] = useState<CompareResult[]>([]);
  const [previewIndex, setPreviewIndex] = useState<number>(0);
  const [isPreviewPaused, setIsPreviewPaused] = useState<boolean>(false);

  const formatCount = (value: number) => value.toLocaleString('en-GB');

  useEffect(() => {
    const load = async () => {
      const [versions, cards, gitStats] = await Promise.all([fetchVersions(), fetchCatalog(), fetchGitStats()]);
      setVersionsCount(versions.length);
      setLatestVersion(versions[versions.length - 1] ?? 'n/a');
      setCardsCount(cards.length);
      setFilesChanged(gitStats.filesChanged);
      setLinesWritten(gitStats.lineChanges);
      setCommitCount(gitStats.commitCount);

      const latest = versions[versions.length - 1] ?? '';
      if (latest) {
        const previewPayload = await fetchCompare(latest, latest, PREVIEW_PARAMETER_IDS, 'through_right');
        const byId = new Map(previewPayload.items.map((item) => [item.id, item]));
        const ordered = PREVIEW_PARAMETER_IDS.map((id) => byId.get(id)).filter((item): item is CompareResult =>
          Boolean(item)
        );
        setPreviewItems(ordered);
      }
    };

    load().catch(() => {
      setVersionsCount(0);
      setLatestVersion('n/a');
      setCardsCount(0);
      setFilesChanged(0);
      setLinesWritten(0);
      setCommitCount(0);
      setPreviewItems([]);
    });
  }, []);

  useEffect(() => {
    if (previewItems.length === 0) {
      setPreviewIndex(0);
      return;
    }
    setPreviewIndex((current) => (current >= previewItems.length ? 0 : current));
  }, [previewItems]);

  useEffect(() => {
    if (previewItems.length <= 1 || isPreviewPaused) {
      return;
    }
    const timer = window.setInterval(() => {
      setPreviewIndex((current) => (current + 1) % previewItems.length);
    }, 7600);
    return () => window.clearInterval(timer);
  }, [previewItems.length, isPreviewPaused]);

  const previewItem = previewItems[previewIndex];

  return (
    <section className="home-layout">
      <div className="summary-card fade-up">
        <p className="eyebrow">Project Summary</p>
        <h2>Purpose and Model Context</h2>
        <p>
          This website is the main workspace for my individual project. It exists to visualize calibrated model parameters,
          track iterative updates, and provide transparent provenance for how each model input evolves over time.
        </p>
        <p>
          The model is an agent-based simulation of the UK housing market, including owner-occupiers, renters, buy-to-let
          investors, banks, government, and policy mechanisms that affect affordability and wealth outcomes.
        </p>
        <div className="summary-links">
          <a href="https://github.com/max-stoddard/uk-housing-model-individual-project" target="_blank" rel="noreferrer">
            <span className="summary-link-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" role="img" focusable="false">
                <path
                  fill="currentColor"
                  d="M3 5.5A2.5 2.5 0 015.5 3h5A2.5 2.5 0 0113 5.5v13a2.5 2.5 0 01-2.5 2.5h-5A2.5 2.5 0 013 18.5v-13zm2.5-.5a.5.5 0 00-.5.5v13a.5.5 0 00.5.5h5a.5.5 0 00.5-.5v-13a.5.5 0 00-.5-.5h-5zM14 6h4.5A2.5 2.5 0 0121 8.5v10a2.5 2.5 0 01-2.5 2.5H14V19h4.5a.5.5 0 00.5-.5v-10a.5.5 0 00-.5-.5H14V6z"
                />
              </svg>
            </span>
            <span>Source Code</span>
          </a>
          <a href="https://github.com/max-stoddard" target="_blank" rel="noreferrer">
            <span className="summary-link-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" role="img" focusable="false">
                <path
                  fill="currentColor"
                  d="M12 2C6.48 2 2 6.58 2 12.23c0 4.52 2.87 8.35 6.84 9.71.5.1.68-.22.68-.49 0-.24-.01-1.03-.01-1.86-2.78.62-3.37-1.22-3.37-1.22-.45-1.19-1.11-1.5-1.11-1.5-.9-.63.07-.62.07-.62 1 .07 1.52 1.05 1.52 1.05.88 1.54 2.31 1.1 2.87.84.09-.66.35-1.1.63-1.35-2.22-.26-4.56-1.14-4.56-5.06 0-1.12.39-2.04 1.03-2.76-.1-.26-.45-1.31.1-2.72 0 0 .84-.28 2.75 1.05A9.34 9.34 0 0112 6.84a9.2 9.2 0 012.5.35c1.9-1.33 2.74-1.05 2.74-1.05.56 1.41.21 2.46.11 2.72.64.72 1.03 1.64 1.03 2.76 0 3.93-2.35 4.8-4.6 5.05.36.32.68.95.68 1.92 0 1.39-.01 2.5-.01 2.84 0 .27.18.59.69.49A10.28 10.28 0 0022 12.23C22 6.58 17.52 2 12 2z"
                />
              </svg>
            </span>
            <span>GitHub</span>
          </a>
          <a href="https://www.linkedin.com/in/maxstoddard/" target="_blank" rel="noreferrer">
            <span className="summary-link-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" role="img" focusable="false">
                <path
                  fill="currentColor"
                  d="M6.94 8.5a1.73 1.73 0 110-3.46 1.73 1.73 0 010 3.46zM5.4 9.8h3.08V19H5.4V9.8zm5.02 0h2.95v1.26h.04c.41-.78 1.4-1.6 2.89-1.6 3.1 0 3.67 2.08 3.67 4.79V19h-3.08v-4.17c0-.99-.02-2.27-1.35-2.27-1.35 0-1.55 1.08-1.55 2.2V19h-3.08V9.8z"
                />
              </svg>
            </span>
            <span>LinkedIn</span>
          </a>
        </div>
      </div>

      <div className="stats-grid fade-up-delay">
        <article>
          <p>Lines Written</p>
          <strong>{formatCount(linesWritten)}</strong>
        </article>
        <article>
          <p>Files Changed</p>
          <strong>{formatCount(filesChanged)}</strong>
        </article>
        <article>
          <p>Commits</p>
          <strong>{formatCount(commitCount)}</strong>
        </article>
      </div>

      <div className="hero-card fade-up">
        <p className="eyebrow">Main Individual Project Website</p>
        <h2>Visualize and track calibrated UK housing model parameters</h2>
        {previewItem && (
          <div
            className="hero-preview"
            onMouseEnter={() => setIsPreviewPaused(true)}
            onMouseLeave={() => setIsPreviewPaused(false)}
          >
            <div className="hero-preview-head">
              <p>Preview from Model Parameters</p>
              <strong>{previewItem.title}</strong>
            </div>
            <div key={previewItem.id} className="hero-preview-chart-shell">
              <EChart option={buildPreviewOption(previewItem)} className="chart hero-preview-chart" />
            </div>
            <div className="hero-preview-dots" role="tablist" aria-label="Parameter preview selector">
              {previewItems.map((item, index) => (
                <button
                  key={item.id}
                  type="button"
                  className={index === previewIndex ? 'active' : ''}
                  onClick={() => setPreviewIndex(index)}
                  aria-label={`Show preview ${index + 1}: ${item.title}`}
                />
              ))}
            </div>
          </div>
        )}
        <Link to="/compare" className="primary-button">
          Open Model Parameters
        </Link>
      </div>

      <div className="stats-grid fade-up-delay">
        <article>
          <p>Snapshot Versions</p>
          <strong>{formatCount(versionsCount)}</strong>
        </article>
        <article>
          <p>Tracked Parameter Cards</p>
          <strong>{formatCount(cardsCount)}</strong>
        </article>
        <article>
          <p>Latest Snapshot</p>
          <strong>{latestVersion}</strong>
        </article>
      </div>
    </section>
  );
}
