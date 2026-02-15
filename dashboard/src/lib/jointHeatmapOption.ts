// Author: Max Stoddard
import type { EChartsOption } from 'echarts';
import type { JointCell } from '../../shared/types';

function formatDefaultCompact(value: number): string {
  if (Math.abs(value) >= 1000) {
    return value.toLocaleString('en-GB', { maximumFractionDigits: 0 });
  }
  return value.toLocaleString('en-GB', { maximumFractionDigits: 4 });
}

export interface JointHeatmapLayoutOverrides {
  containLabel?: boolean;
  outerBoundsMode?: 'none' | 'same' | 'all';
  gridLeft?: number;
  gridRight?: number;
  gridTop?: number;
  gridBottom?: number;
  xAxisRotate?: number;
  xAxisFontSize?: number;
  xAxisMargin?: number;
  yAxisFontSize?: number;
  yAxisMargin?: number;
  xAxisNameGap?: number;
  yAxisNameGap?: number;
  xAxisNameMoveOverlap?: boolean;
  yAxisNameMoveOverlap?: boolean;
  titleFontSize?: number;
  titleTop?: number;
  axisTitleFontSize?: number;
  visualMapTop?: number | 'middle';
  visualMapBottom?: number;
  visualMapRight?: number;
  visualMapItemWidth?: number;
  visualMapItemHeight?: number;
  visualMapTextSize?: number;
  visualMapPrecision?: number;
}

export type HeatmapLayoutContext = 'compare' | 'single' | 'preview';

interface AdaptiveHeatmapLayoutArgs {
  context: HeatmapLayoutContext;
  xLabels: string[];
  yLabels: string[];
  xAxisName: string;
  yAxisName: string;
  layout?: JointHeatmapLayoutOverrides;
}

interface HeatmapContextConfig {
  leftMin: number;
  leftMax: number;
  bottomMin: number;
  bottomMax: number;
  topMin: number;
  topMax: number;
  rightMin: number;
  rightMax: number;
  xTitleBottomPadding: number;
  yTitlePinLeft: number;
  xNameGap: number;
  yNameGap: number;
  xLabelMargin: number;
  yLabelMargin: number;
  titleTop: number;
  visualMapRight: number;
  visualMapItemWidth: number;
  visualMapItemHeight: number;
  visualMapTop: number | 'middle';
}

type ComputedHeatmapMargins = {
  left: number;
  right: number;
  top: number;
  bottom: number;
  xLabelMargin: number;
  yLabelMargin: number;
  xNameGap: number;
  yNameGap: number;
};

const HEATMAP_CONTEXT_CONFIG: Record<HeatmapLayoutContext, HeatmapContextConfig> = {
  compare: {
    leftMin: 72,
    leftMax: 96,
    bottomMin: 75,
    bottomMax: 75,
    topMin: 20,
    topMax: 26,
    rightMin: 30,
    rightMax: 34,
    xTitleBottomPadding: 10,
    yTitlePinLeft: 18,
    xNameGap: 28,
    yNameGap: 12,
    xLabelMargin: 7,
    yLabelMargin: 8,
    titleTop: 5,
    visualMapRight: -3,
    visualMapItemWidth: 10,
    visualMapItemHeight: 120,
    visualMapTop: 'middle'
  },
  single: {
    leftMin: 100,
    leftMax: 130,
    bottomMin: 30,
    bottomMax: 90,
    topMin: 22,
    topMax: 30,
    rightMin: 45,
    rightMax: 50,
    xTitleBottomPadding: 12,
    yTitlePinLeft: 20,
    xNameGap: 32,
    yNameGap: 32,
    xLabelMargin: 8,
    yLabelMargin: 9,
    titleTop: 6,
    visualMapRight: 2,
    visualMapItemWidth: 12,
    visualMapItemHeight: 140,
    visualMapTop: 'middle'
  },
  preview: {
    leftMin: 70,
    leftMax: 100,
    bottomMin: 60,
    bottomMax: 90,
    topMin: 20,
    topMax: 26,
    rightMin: 40,
    rightMax: 50,
    xTitleBottomPadding: 9,
    yTitlePinLeft: 16,
    xNameGap: 26,
    yNameGap: 10,
    xLabelMargin: 6,
    yLabelMargin: 7,
    titleTop: 4,
    visualMapRight: 4,
    visualMapItemWidth: 10,
    visualMapItemHeight: 110,
    visualMapTop: 'middle'
  }
};

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function measureTextWidth(text: string, fontSize: number, fontWeight = 400): number {
  const safeText = text || '';
  if (typeof document === 'undefined') {
    return safeText.length * fontSize * 0.56;
  }
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    return safeText.length * fontSize * 0.56;
  }
  ctx.font = `${fontWeight} ${fontSize}px Space Grotesk, sans-serif`;
  return ctx.measureText(safeText).width;
}

function longestLabelWidth(labels: string[], fontSize: number): number {
  if (labels.length === 0) {
    return 0;
  }
  return Math.max(...labels.map((label) => measureTextWidth(label, fontSize)));
}

function computeAdaptiveMargins(args: AdaptiveHeatmapLayoutArgs): ComputedHeatmapMargins {
  const contextConfig = HEATMAP_CONTEXT_CONFIG[args.context];
  const axisTitleFontSize = args.layout?.axisTitleFontSize ?? 11;
  const xTickFontSize = args.layout?.xAxisFontSize ?? 10;
  const yTickFontSize = args.layout?.yAxisFontSize ?? 10;
  const xRotate = args.layout?.xAxisRotate ?? 30;

  const maxXLabelWidth = longestLabelWidth(args.xLabels, xTickFontSize);
  const maxYLabelWidth = longestLabelWidth(args.yLabels, yTickFontSize);
  const rotateRadians = (Math.abs(xRotate) * Math.PI) / 180;
  const projectedXTickHeight =
    Math.abs(Math.sin(rotateRadians)) * maxXLabelWidth + Math.abs(Math.cos(rotateRadians)) * (xTickFontSize + 2);

  const configuredXNameGap = args.layout?.xAxisNameGap ?? contextConfig.xNameGap;
  const configuredYNameGap = args.layout?.yAxisNameGap ?? contextConfig.yNameGap;
  const xLabelMargin = args.layout?.xAxisMargin ?? contextConfig.xLabelMargin;
  const yLabelMargin = args.layout?.yAxisMargin ?? contextConfig.yLabelMargin;
  const xTitleReserve = args.xAxisName ? axisTitleFontSize + configuredXNameGap : 0;
  const yTitleReserve = args.yAxisName ? axisTitleFontSize + configuredYNameGap : 0;

  const leftRaw = maxYLabelWidth + yLabelMargin + yTitleReserve + 6;
  const bottomRaw = projectedXTickHeight + xLabelMargin + xTitleReserve + 6;
  const titleTop = args.layout?.titleTop ?? contextConfig.titleTop;
  const titleFontSize = args.layout?.titleFontSize ?? 12;
  const topRaw = titleTop + (args.layout ? titleFontSize + 9 : 20);
  const visualMapItemWidth = args.layout?.visualMapItemWidth ?? contextConfig.visualMapItemWidth;
  const rightRaw = visualMapItemWidth + 16;
  const left = clamp(leftRaw, contextConfig.leftMin, contextConfig.leftMax);
  const bottom = clamp(bottomRaw, contextConfig.bottomMin, contextConfig.bottomMax);
  const top = clamp(topRaw, contextConfig.topMin, contextConfig.topMax);
  const right = clamp(rightRaw, contextConfig.rightMin, contextConfig.rightMax);
  const xNameGap = args.layout?.xAxisNameGap !== undefined
    ? args.layout.xAxisNameGap
    : Math.max(
        configuredXNameGap,
        bottom - (contextConfig.xTitleBottomPadding + axisTitleFontSize * 0.6)
      );

  const yNameGap = args.layout?.yAxisNameGap !== undefined
    ? args.layout.yAxisNameGap
    : Math.max(contextConfig.yNameGap, left - contextConfig.yTitlePinLeft);

  return {
    left,
    bottom,
    top,
    right,
    xLabelMargin,
    yLabelMargin,
    xNameGap,
    yNameGap
  };
}

export function resolveAdaptiveHeatmapLayout(args: AdaptiveHeatmapLayoutArgs): JointHeatmapLayoutOverrides {
  const contextConfig = HEATMAP_CONTEXT_CONFIG[args.context];
  const margins = computeAdaptiveMargins(args);

  return {
    ...args.layout,
    containLabel: args.layout?.containLabel ?? false,
    outerBoundsMode: args.layout?.outerBoundsMode ?? 'none',
    xAxisNameMoveOverlap: args.layout?.xAxisNameMoveOverlap ?? false,
    yAxisNameMoveOverlap: args.layout?.yAxisNameMoveOverlap ?? false,
    gridLeft: args.layout?.gridLeft ?? margins.left,
    gridRight: args.layout?.gridRight ?? margins.right,
    gridTop: args.layout?.gridTop ?? margins.top,
    gridBottom: args.layout?.gridBottom ?? margins.bottom,
    xAxisNameGap: args.layout?.xAxisNameGap ?? margins.xNameGap,
    yAxisNameGap: args.layout?.yAxisNameGap ?? margins.yNameGap,
    xAxisMargin: args.layout?.xAxisMargin ?? margins.xLabelMargin,
    yAxisMargin: args.layout?.yAxisMargin ?? margins.yLabelMargin,
    titleTop: args.layout?.titleTop ?? contextConfig.titleTop,
    visualMapRight: args.layout?.visualMapRight ?? contextConfig.visualMapRight,
    visualMapItemWidth: args.layout?.visualMapItemWidth ?? contextConfig.visualMapItemWidth,
    visualMapItemHeight: args.layout?.visualMapItemHeight ?? contextConfig.visualMapItemHeight,
    visualMapTop: args.layout?.visualMapTop ?? contextConfig.visualMapTop
  };
}

interface JointHeatmapOptionArgs {
  title?: string;
  cells: JointCell[];
  xLabels: string[];
  yLabels: string[];
  min: number;
  max: number;
  colors: string[];
  xAxisName: string;
  yAxisName: string;
  valueFormatter?: (value: number) => string;
  layout?: JointHeatmapLayoutOverrides;
}

export function jointHeatmapOption(args: JointHeatmapOptionArgs): EChartsOption {
  const {
    title,
    cells,
    xLabels,
    yLabels,
    min,
    max,
    colors,
    xAxisName,
    yAxisName,
    valueFormatter = formatDefaultCompact,
    layout
  } = args;

  const option: EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: (param: any) => {
        const [xIndex, yIndex, value] = param.data as [number, number, number];
        return `${xLabels[xIndex]} / ${yLabels[yIndex]}<br/>${valueFormatter(Number(value))}`;
      }
    },
    grid: {
      left: layout?.gridLeft ?? 124,
      right: layout?.gridRight ?? 72,
      top: layout?.gridTop ?? 42,
      bottom: layout?.gridBottom ?? 94,
      containLabel: layout?.containLabel ?? true,
      ...(layout?.outerBoundsMode ? { outerBoundsMode: layout.outerBoundsMode } : {})
    },
    xAxis: {
      type: 'category',
      data: xLabels,
      axisLabel: {
        rotate: layout?.xAxisRotate ?? 45,
        fontSize: layout?.xAxisFontSize ?? 9,
        margin: layout?.xAxisMargin ?? 14
      },
      name: xAxisName,
      nameLocation: 'middle',
      nameGap: layout?.xAxisNameGap ?? 56,
      ...(layout?.xAxisNameMoveOverlap !== undefined ? { nameMoveOverlap: layout.xAxisNameMoveOverlap } : {}),
      nameTextStyle: {
        fontSize: layout?.axisTitleFontSize ?? 11,
        fontWeight: 600,
        color: '#495057'
      }
    },
    yAxis: {
      type: 'category',
      data: yLabels,
      axisLabel: {
        fontSize: layout?.yAxisFontSize ?? 9,
        margin: layout?.yAxisMargin ?? 10
      },
      name: yAxisName,
      nameLocation: 'middle',
      nameGap: layout?.yAxisNameGap ?? 104,
      ...(layout?.yAxisNameMoveOverlap !== undefined ? { nameMoveOverlap: layout.yAxisNameMoveOverlap } : {}),
      nameTextStyle: {
        fontSize: layout?.axisTitleFontSize ?? 11,
        fontWeight: 600,
        color: '#495057'
      }
    },
    visualMap: {
      show: true,
      type: 'continuous',
      min,
      max,
      orient: 'vertical',
      right: layout?.visualMapRight ?? 10,
      top: layout?.visualMapTop ?? 'middle',
      ...(layout?.visualMapBottom !== undefined ? { bottom: layout.visualMapBottom } : {}),
      calculable: false,
      realtime: true,
      showLabel: false,
      precision: layout?.visualMapPrecision ?? 6,
      formatter: '{value}',
      itemWidth: layout?.visualMapItemWidth ?? 12,
      itemHeight: layout?.visualMapItemHeight ?? 168,
      text: ['High', 'Low'],
      textGap: 6,
      textStyle: { color: '#495057', fontSize: layout?.visualMapTextSize ?? 10 },
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

  if (title) {
    option.title = {
      text: title,
      left: 'center',
      top: layout?.titleTop ?? 0,
      textStyle: { fontSize: layout?.titleFontSize ?? 12 }
    };
  }

  return option;
}
