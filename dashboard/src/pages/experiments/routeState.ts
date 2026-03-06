import {
  DEFAULT_EXPERIMENT_ROUTE_STATE,
  EXPERIMENT_MODES,
  EXPERIMENT_TYPES,
  type ExperimentMode,
  type ExperimentRouteState,
  type ExperimentType
} from './types';

interface ExperimentRouteStateInput {
  type?: string;
  mode?: string;
  runId?: string;
  experimentId?: string;
  jobRef?: string;
}

function isExperimentType(value: string): value is ExperimentType {
  return (EXPERIMENT_TYPES as readonly string[]).includes(value);
}

function isExperimentMode(value: string): value is ExperimentMode {
  return (EXPERIMENT_MODES as readonly string[]).includes(value);
}

function clean(value: string | null | undefined): string {
  return value?.trim() ?? '';
}

export function normaliseExperimentRouteState(
  partial: ExperimentRouteStateInput
): ExperimentRouteState {
  const type = isExperimentType(clean(partial.type))
    ? (clean(partial.type) as ExperimentType)
    : DEFAULT_EXPERIMENT_ROUTE_STATE.type;
  const mode = isExperimentMode(clean(partial.mode))
    ? (clean(partial.mode) as ExperimentMode)
    : DEFAULT_EXPERIMENT_ROUTE_STATE.mode;

  const base: ExperimentRouteState = {
    type,
    mode,
    runId: clean(partial.runId),
    experimentId: clean(partial.experimentId),
    jobRef: clean(partial.jobRef)
  };

  if (base.mode === 'run') {
    return {
      ...base,
      runId: '',
      experimentId: ''
    };
  }

  if (base.type === 'manual') {
    return {
      ...base,
      experimentId: '',
      jobRef: ''
    };
  }

  return {
    ...base,
    runId: '',
    jobRef: ''
  };
}

export function parseExperimentRouteState(searchParams: URLSearchParams): ExperimentRouteState {
  return normaliseExperimentRouteState({
    type: clean(searchParams.get('type')),
    mode: clean(searchParams.get('mode')),
    runId: clean(searchParams.get('runId')),
    experimentId: clean(searchParams.get('experimentId')),
    jobRef: clean(searchParams.get('jobRef'))
  });
}

export function buildExperimentSearchParams(state: ExperimentRouteState): URLSearchParams {
  const normalised = normaliseExperimentRouteState(state);
  const params = new URLSearchParams();
  params.set('type', normalised.type);
  params.set('mode', normalised.mode);

  if (normalised.mode === 'run' && normalised.jobRef) {
    params.set('jobRef', normalised.jobRef);
  }

  if (normalised.mode === 'view' && normalised.type === 'manual' && normalised.runId) {
    params.set('runId', normalised.runId);
  }

  if (normalised.mode === 'view' && normalised.type === 'sensitivity' && normalised.experimentId) {
    params.set('experimentId', normalised.experimentId);
  }

  return params;
}

export function buildExperimentsPath(state: ExperimentRouteState): string {
  const query = buildExperimentSearchParams(state).toString();
  return query ? `/experiments?${query}` : '/experiments';
}
