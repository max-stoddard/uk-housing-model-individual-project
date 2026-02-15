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
  titleFontSize?: number;
  axisTitleFontSize?: number;
  visualMapRight?: number;
  visualMapItemWidth?: number;
  visualMapItemHeight?: number;
  visualMapTextSize?: number;
  visualMapPrecision?: number;
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
      containLabel: true
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
      top: 'middle',
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
      textStyle: { fontSize: layout?.titleFontSize ?? 12 }
    };
  }

  return option;
}
