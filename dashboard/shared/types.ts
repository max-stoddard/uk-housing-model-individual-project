export type VersionId = string;

export type ParameterGroup =
  | 'Household Demographics & Wealth'
  | 'Government & Tax'
  | 'Housing & Rental Market'
  | 'Purchase & Mortgage'
  | 'Bank & Credit Policy'
  | 'BTL & Investor Behavior';

export type ParameterFormat =
  | 'scalar'
  | 'scalar_pair'
  | 'binned_distribution'
  | 'joint_distribution'
  | 'lognormal_pair'
  | 'power_law_pair'
  | 'gaussian_pair'
  | 'hpa_expectation_line'
  | 'buy_quad';

export interface ParameterCardMeta {
  id: string;
  title: string;
  group: ParameterGroup;
  format: ParameterFormat;
  configKeys: string[];
  dataFileConfigKeys?: string[];
  explanation: string;
}

export interface DataSourceInfo {
  configPathLeft: string;
  configPathRight: string;
  configKeys: string[];
  dataFilesLeft: string[];
  dataFilesRight: string[];
  datasetsLeft: DatasetAttribution[];
  datasetsRight: DatasetAttribution[];
}

export type ValidationStatus = 'complete' | 'in_progress';

export interface MethodVariationNote {
  configParameters: string[];
  improvementSummary: string;
  whyChanged: string;
  methodChosen?: string;
  decisionLogic?: string;
}

export interface ParameterChange {
  configParameter: string;
  datasetSource: string | null;
}

export interface DatasetAttribution {
  tag: string;
  fullName: string;
  year: string;
  edition?: string;
  evidence?: string;
}

export interface VersionChangeOrigin {
  versionId: string;
  description: string;
  updatedDataSources: string[];
  calibrationFiles: string[];
  configParameters: string[];
  parameterChanges: ParameterChange[];
  validationStatus: ValidationStatus;
  methodVariations: MethodVariationNote[];
}

export interface DeltaStat {
  absolute: number;
  percent: number | null;
}

export interface ScalarDatum {
  key: string;
  left: number;
  right: number;
  delta: DeltaStat;
}

export interface BinnedDatum {
  label: string;
  lower: number;
  upper: number;
  left: number;
  right: number;
  delta: number;
}

export type AxisScaleType = 'linear' | 'log';

export interface AxisMeta {
  edges: number[];
  labels: string[];
  scaleType: AxisScaleType;
}

export interface JointCell {
  xIndex: number;
  yIndex: number;
  value: number;
}

export interface JointPayload {
  xAxis: AxisMeta;
  yAxis: AxisMeta;
  left: JointCell[];
  right: JointCell[];
  delta: JointCell[];
}

export interface CurvePoint {
  x: number;
  y: number;
}

export type VisualPayload =
  | { type: 'scalar'; values: ScalarDatum[] }
  | { type: 'binned_distribution'; bins: BinnedDatum[] }
  | { type: 'joint_distribution'; matrix: JointPayload }
  | {
      type: 'lognormal_pair';
      parameters: ScalarDatum[];
      curveLeft: CurvePoint[];
      curveRight: CurvePoint[];
      domain: { min: number; max: number };
    }
  | {
      type: 'power_law_pair';
      parameters: ScalarDatum[];
      curveLeft: CurvePoint[];
      curveRight: CurvePoint[];
      domain: { min: number; max: number };
    }
  | {
      type: 'gaussian_pair';
      parameters: ScalarDatum[];
      logCurveLeft: CurvePoint[];
      logCurveRight: CurvePoint[];
      percentCurveLeft: CurvePoint[];
      percentCurveRight: CurvePoint[];
      logDomain: { min: number; max: number };
      percentDomain: { min: number; max: number };
      percentCap: number;
      percentCapMassLeft: number;
      percentCapMassRight: number;
    }
  | {
      type: 'hpa_expectation_line';
      parameters: ScalarDatum[];
      curveLeft: CurvePoint[];
      curveRight: CurvePoint[];
      domain: { min: number; max: number };
      dt: number;
    }
  | {
      type: 'buy_quad';
      parameters: ScalarDatum[];
      budgetLeft: CurvePoint[];
      budgetRight: CurvePoint[];
      multiplierLeft: CurvePoint[];
      multiplierRight: CurvePoint[];
      expectedMultiplier: {
        left: number;
        right: number;
        delta: DeltaStat;
      };
      domain: { min: number; max: number };
    };

export interface CompareResult {
  id: string;
  title: string;
  group: ParameterGroup;
  format: ParameterFormat;
  unchanged: boolean;
  sourceInfo: DataSourceInfo;
  explanation: string;
  leftVersion: VersionId;
  rightVersion: VersionId;
  changeOriginsInRange: VersionChangeOrigin[];
  visualPayload: VisualPayload;
}

export interface CompareResponse {
  left: VersionId;
  right: VersionId;
  items: CompareResult[];
}

export type ResultsRunStatus = 'complete' | 'partial' | 'invalid';

export type ResultsFileType =
  | 'output'
  | 'core_indicator'
  | 'transaction'
  | 'micro_snapshot'
  | 'config'
  | 'other';

export type ResultsCoverageStatus = 'supported' | 'empty' | 'unsupported' | 'error';

export type ResultsSeriesSource = 'core_indicator' | 'output';

export interface ResultsIndicatorMeta {
  id: string;
  title: string;
  units: string;
  description: string;
  source: ResultsSeriesSource;
}

export interface KpiMetricSummary {
  indicatorId: string;
  title: string;
  units: string;
  windowType: 'tail_120';
  latest: number | null;
  mean: number | null;
  yoyDelta: number | null;
  yoyPercent: number | null;
}

export interface ResultsCoverageSummary {
  requiredCount: number;
  supportedCount: number;
  emptyCount: number;
  errorCount: number;
}

export interface ResultsRunSummary {
  runId: string;
  path: string;
  modifiedAt: string;
  createdAt: string;
  sizeBytes: number;
  fileCount: number;
  status: ResultsRunStatus;
  configAvailable: boolean;
  parseCoverage: ResultsCoverageSummary;
}

export interface ResultsIndicatorAvailability extends ResultsIndicatorMeta {
  available: boolean;
  coverageStatus: ResultsCoverageStatus;
  note?: string;
}

export interface ResultsRunDetail {
  runId: string;
  path: string;
  modifiedAt: string;
  createdAt: string;
  sizeBytes: number;
  fileCount: number;
  status: ResultsRunStatus;
  configAvailable: boolean;
  parseCoverage: ResultsCoverageSummary;
  indicators: ResultsIndicatorAvailability[];
  kpiSummary: KpiMetricSummary[];
}

export interface ResultsFileManifestEntry {
  fileName: string;
  filePath: string;
  sizeBytes: number;
  modifiedAt: string;
  fileType: ResultsFileType;
  coverageStatus: ResultsCoverageStatus;
  note?: string;
}

export interface ResultsSeriesPoint {
  modelTime: number;
  value: number | null;
}

export interface ResultsSeriesPayload {
  runId: string;
  indicator: ResultsIndicatorMeta;
  smoothWindow: 0 | 3 | 12;
  points: ResultsSeriesPoint[];
}

export interface ResultsCompareSeries {
  runId: string;
  points: ResultsSeriesPoint[];
}

export interface ResultsCompareIndicator {
  indicator: ResultsIndicatorMeta;
  seriesByRun: ResultsCompareSeries[];
}

export interface ResultsComparePayload {
  runIds: string[];
  indicatorIds: string[];
  smoothWindow: 0 | 3 | 12;
  window: 'post200' | 'tail120' | 'full';
  indicators: ResultsCompareIndicator[];
}
