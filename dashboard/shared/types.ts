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
}

export type ValidationStatus = 'complete' | 'in_progress';

export interface MethodVariationNote {
  configParameters: string[];
  improvementSummary: string;
  whyChanged: string;
  methodChosen?: string;
  decisionLogic?: string;
}

export interface VersionChangeOrigin {
  versionId: string;
  description: string;
  validationDataset: string;
  updatedDataSources: string[];
  calibrationFiles: string[];
  configParameters: string[];
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
