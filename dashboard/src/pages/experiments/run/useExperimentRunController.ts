import { useEffect, useMemo, useState } from 'react';
import type {
  ExperimentJobSummary,
  ModelRunOptionsPayload,
  ModelRunParameterDefinition,
  ModelRunSubmitRequest,
  ModelRunWarning,
  ResultsStorageSummary
} from '../../../../shared/types';
import {
  API_RETRY_DELAY_MS,
  cancelExperimentJob,
  fetchExperimentJobs,
  fetchModelRunOptions,
  fetchResultsStorageSummary,
  isRetryableApiError,
  submitModelRun,
  submitSensitivityExperiment
} from '../../../lib/api';
import { useExperimentLogs } from '../../run-experiments/useExperimentLogs';

export type FormValue = string | boolean;
export type NumericParameter = ModelRunParameterDefinition & { type: 'integer' | 'number' };

export interface ExperimentRunController {
  options: ModelRunOptionsPayload | null;
  selectedBaseline: string;
  title: string;
  setTitle: (value: string) => void;
  formValues: Record<string, FormValue>;
  warnings: ModelRunWarning[];
  sensitivityTitle: string;
  setSensitivityTitle: (value: string) => void;
  sensitivityParameterKey: string;
  setSensitivityParameterKey: (value: string) => void;
  sensitivityMin: string;
  setSensitivityMin: (value: string) => void;
  sensitivityMax: string;
  setSensitivityMax: (value: string) => void;
  sensitivityRetainFullOutput: boolean;
  setSensitivityRetainFullOutput: (value: boolean) => void;
  sensitivityWarnings: ModelRunWarning[];
  jobs: ExperimentJobSummary[];
  selectedJob: ExperimentJobSummary | null;
  selectedJobRef: string;
  logLines: string[];
  logError: string;
  groupedParameters: Array<[string, ModelRunParameterDefinition[]]>;
  numericSensitivityParameters: NumericParameter[];
  selectedSensitivityParameter: NumericParameter | null;
  isLoadingOptions: boolean;
  isLoadingJobs: boolean;
  isSubmitting: boolean;
  isSubmittingSensitivity: boolean;
  isCancelingSensitivity: boolean;
  pageError: string;
  pendingRunId: string;
  pendingSensitivityExperimentId: string;
  storageSummary: ResultsStorageSummary | null;
  executionDisabled: boolean;
  manualSubmissionLockedBySensitivity: boolean;
  sensitivitySubmissionLockedByManual: boolean;
  lockSensitivityId: string;
  lockManualId: string;
  hasActiveSensitivityJob: boolean;
  onBaselineChange: (baseline: string) => void;
  onFormValueChange: (parameter: ModelRunParameterDefinition, value: FormValue) => void;
  onSubmitRun: (confirmWarnings: boolean) => Promise<void>;
  onSubmitSensitivity: (confirmWarnings: boolean) => Promise<void>;
  onCancelActiveSensitivity: () => Promise<void>;
  onCancelJob: (jobRef: string) => Promise<void>;
}

interface UseExperimentRunControllerOptions {
  selectedJobRef: string;
  onSelectedJobRefChange: (jobRef: string) => void;
  onOpenManualResults: (runId: string) => void;
  onOpenSensitivityResults: (experimentId: string) => void;
}

function parseJobRefId(jobRef: string | null): string {
  if (!jobRef) {
    return '';
  }
  const match = /^(manual|sensitivity):(.+)$/.exec(jobRef);
  return match?.[2] ?? jobRef;
}

function toInitialFormValues(parameters: ModelRunParameterDefinition[]): Record<string, FormValue> {
  const values: Record<string, FormValue> = {};
  for (const parameter of parameters) {
    if (parameter.type === 'boolean') {
      values[parameter.key] = Boolean(parameter.defaultValue);
    } else {
      values[parameter.key] = String(parameter.defaultValue);
    }
  }
  return values;
}

function parseFormValue(parameter: ModelRunParameterDefinition, value: FormValue): number | boolean {
  if (parameter.type === 'boolean') {
    if (typeof value !== 'boolean') {
      throw new Error(`Parameter ${parameter.key} must be boolean.`);
    }
    return value;
  }

  if (typeof value !== 'string') {
    throw new Error(`Parameter ${parameter.key} must be numeric.`);
  }

  const parsed = Number.parseFloat(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(`Parameter ${parameter.key} must be numeric.`);
  }

  if (parameter.type === 'integer' && !Number.isInteger(parsed)) {
    throw new Error(`Parameter ${parameter.key} must be an integer.`);
  }

  return parsed;
}

function isSameValue(left: number | boolean, right: number | boolean): boolean {
  if (typeof left === 'boolean' || typeof right === 'boolean') {
    return left === right;
  }
  return Math.abs(left - right) < 1e-12;
}

function buildDefaultSensitivityRange(parameter: NumericParameter): { min: string; max: string } {
  const baseline = Number(parameter.defaultValue);
  if (!Number.isFinite(baseline)) {
    return { min: '', max: '' };
  }

  if (parameter.type === 'integer') {
    if (baseline === 0) {
      return { min: '-1', max: '1' };
    }
    const delta = Math.max(1, Math.round(Math.abs(baseline) * 0.1));
    return {
      min: String(Math.round(baseline - delta)),
      max: String(Math.round(baseline + delta))
    };
  }

  if (Math.abs(baseline) < 1e-12) {
    return { min: '-0.1', max: '0.1' };
  }

  return {
    min: String(Number((baseline * 0.9).toFixed(6))),
    max: String(Number((baseline * 1.1).toFixed(6)))
  };
}

export function useExperimentRunController({
  selectedJobRef,
  onSelectedJobRefChange,
  onOpenManualResults,
  onOpenSensitivityResults
}: UseExperimentRunControllerOptions): ExperimentRunController {
  const [options, setOptions] = useState<ModelRunOptionsPayload | null>(null);
  const [selectedBaseline, setSelectedBaseline] = useState<string>('');

  const [title, setTitle] = useState<string>('');
  const [formValues, setFormValues] = useState<Record<string, FormValue>>({});
  const [warnings, setWarnings] = useState<ModelRunWarning[]>([]);

  const [sensitivityTitle, setSensitivityTitle] = useState<string>('');
  const [sensitivityParameterKey, setSensitivityParameterKey] = useState<string>('');
  const [sensitivityMin, setSensitivityMin] = useState<string>('');
  const [sensitivityMax, setSensitivityMax] = useState<string>('');
  const [sensitivityRetainFullOutput, setSensitivityRetainFullOutput] = useState<boolean>(false);
  const [sensitivityWarnings, setSensitivityWarnings] = useState<ModelRunWarning[]>([]);

  const [jobs, setJobs] = useState<ExperimentJobSummary[]>([]);
  const [manualSubmissionLockedBySensitivity, setManualSubmissionLockedBySensitivity] = useState<boolean>(false);
  const [sensitivitySubmissionLockedByManual, setSensitivitySubmissionLockedByManual] = useState<boolean>(false);
  const [activeManualJobRef, setActiveManualJobRef] = useState<string | null>(null);
  const [activeSensitivityJobRef, setActiveSensitivityJobRef] = useState<string | null>(null);

  const [isLoadingOptions, setIsLoadingOptions] = useState<boolean>(true);
  const [isLoadingJobs, setIsLoadingJobs] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isSubmittingSensitivity, setIsSubmittingSensitivity] = useState<boolean>(false);
  const [isCancelingSensitivity, setIsCancelingSensitivity] = useState<boolean>(false);
  const [pageError, setPageError] = useState<string>('');

  const [pendingRunId, setPendingRunId] = useState<string>('');
  const [pendingSensitivityExperimentId, setPendingSensitivityExperimentId] = useState<string>('');
  const [pendingManualJobRef, setPendingManualJobRef] = useState<string>('');
  const [pendingSensitivityJobRef, setPendingSensitivityJobRef] = useState<string>('');

  const [storageSummary, setStorageSummary] = useState<ResultsStorageSummary | null>(null);

  const selectedJob = useMemo(
    () => jobs.find((job) => job.jobRef === selectedJobRef) ?? null,
    [jobs, selectedJobRef]
  );

  const groupedParameters = useMemo(() => {
    const grouped = new Map<string, ModelRunParameterDefinition[]>();
    for (const parameter of options?.parameters ?? []) {
      const current = grouped.get(parameter.group) ?? [];
      current.push(parameter);
      grouped.set(parameter.group, current);
    }
    return [...grouped.entries()];
  }, [options]);

  const numericSensitivityParameters = useMemo(
    () =>
      (options?.parameters ?? []).filter(
        (parameter): parameter is NumericParameter => parameter.type === 'integer' || parameter.type === 'number'
      ),
    [options]
  );

  const selectedSensitivityParameter = useMemo(
    () => numericSensitivityParameters.find((parameter) => parameter.key === sensitivityParameterKey) ?? null,
    [numericSensitivityParameters, sensitivityParameterKey]
  );

  const activeSensitivityJob = useMemo(
    () => jobs.find((job) => job.type === 'sensitivity' && (job.status === 'queued' || job.status === 'running')) ?? null,
    [jobs]
  );

  const executionDisabled = Boolean(options && !options.executionEnabled);

  const { lines: logLines, error: logError } = useExperimentLogs(
    selectedJobRef,
    Boolean(options?.executionEnabled && selectedJobRef)
  );

  const refreshOptions = async (requestedBaseline?: string): Promise<ModelRunOptionsPayload | null> => {
    setPageError('');
    setIsLoadingOptions(true);

    try {
      const payload = await fetchModelRunOptions(requestedBaseline);
      setOptions(payload);
      setSelectedBaseline(payload.requestedBaseline);
      setFormValues(toInitialFormValues(payload.parameters));
      setWarnings([]);
      return payload;
    } catch (error) {
      setPageError((error as Error).message);
      return null;
    } finally {
      setIsLoadingOptions(false);
    }
  };

  const refreshJobs = async () => {
    try {
      const payload = await fetchExperimentJobs();
      setJobs(payload.jobs);
      setManualSubmissionLockedBySensitivity(payload.locks.manualSubmissionLocked);
      setSensitivitySubmissionLockedByManual(payload.locks.sensitivitySubmissionLocked);
      setActiveManualJobRef(payload.locks.activeManualJobRef);
      setActiveSensitivityJobRef(payload.locks.activeSensitivityJobRef);

      const nextSelectedJobRef =
        selectedJobRef && payload.jobs.some((job) => job.jobRef === selectedJobRef)
          ? selectedJobRef
          : payload.jobs[0]?.jobRef ?? '';

      if (nextSelectedJobRef !== selectedJobRef) {
        onSelectedJobRefChange(nextSelectedJobRef);
      }
    } catch (error) {
      if (!isRetryableApiError(error)) {
        setPageError((error as Error).message);
      }
    } finally {
      setIsLoadingJobs(false);
    }
  };

  const refreshStorageSummary = async () => {
    try {
      const payload = await fetchResultsStorageSummary();
      setStorageSummary(payload);
    } catch (error) {
      if (!isRetryableApiError(error)) {
        setPageError((error as Error).message);
      }
    }
  };

  useEffect(() => {
    let cancelled = false;
    let retryTimer: number | undefined;

    const load = async () => {
      const loadedOptions = await refreshOptions();
      if (cancelled) {
        return;
      }

      if (!loadedOptions || !loadedOptions.executionEnabled) {
        setIsLoadingJobs(false);
        setJobs([]);
        setStorageSummary(null);
        if (selectedJobRef) {
          onSelectedJobRefChange('');
        }
        return;
      }

      await Promise.all([refreshJobs(), refreshStorageSummary()]);
    };

    void load().catch((error: unknown) => {
      if (cancelled) {
        return;
      }
      if (isRetryableApiError(error)) {
        retryTimer = window.setTimeout(() => {
          void load();
        }, API_RETRY_DELAY_MS);
        return;
      }
      setPageError((error as Error).message);
    });

    return () => {
      cancelled = true;
      if (retryTimer !== undefined) {
        window.clearTimeout(retryTimer);
      }
    };
  }, []);

  useEffect(() => {
    if (!options?.executionEnabled) {
      return;
    }

    const interval = window.setInterval(() => {
      void refreshJobs();
    }, 2000);

    return () => {
      window.clearInterval(interval);
    };
  }, [options?.executionEnabled, selectedJobRef]);

  useEffect(() => {
    if (!options?.executionEnabled) {
      return;
    }

    const interval = window.setInterval(() => {
      void refreshStorageSummary();
    }, 5000);

    return () => {
      window.clearInterval(interval);
    };
  }, [options?.executionEnabled]);

  useEffect(() => {
    const firstNumeric = numericSensitivityParameters[0];
    if (!firstNumeric) {
      setSensitivityParameterKey('');
      return;
    }

    setSensitivityParameterKey((current) => {
      if (current && numericSensitivityParameters.some((item) => item.key === current)) {
        return current;
      }
      return firstNumeric.key;
    });
  }, [numericSensitivityParameters]);

  useEffect(() => {
    if (!selectedSensitivityParameter) {
      setSensitivityMin('');
      setSensitivityMax('');
      return;
    }

    const defaults = buildDefaultSensitivityRange(selectedSensitivityParameter);
    setSensitivityMin(defaults.min);
    setSensitivityMax(defaults.max);
  }, [selectedSensitivityParameter?.key, selectedBaseline]);

  useEffect(() => {
    if (!pendingManualJobRef) {
      return;
    }

    const job = jobs.find((item) => item.jobRef === pendingManualJobRef);
    if (!job) {
      return;
    }

    if (job.status === 'succeeded' && job.runId) {
      setPendingRunId(job.runId);
      setPendingManualJobRef('');
      return;
    }

    if (job.status === 'failed' || job.status === 'canceled') {
      setPendingManualJobRef('');
    }
  }, [jobs, pendingManualJobRef]);

  useEffect(() => {
    if (!pendingSensitivityJobRef) {
      return;
    }

    const job = jobs.find((item) => item.jobRef === pendingSensitivityJobRef);
    if (!job) {
      return;
    }

    if (job.status === 'succeeded') {
      setPendingSensitivityExperimentId(job.id);
      setPendingSensitivityJobRef('');
      return;
    }

    if (job.status === 'failed' || job.status === 'canceled') {
      setPendingSensitivityJobRef('');
    }
  }, [jobs, pendingSensitivityJobRef]);

  useEffect(() => {
    if (!pendingRunId) {
      return;
    }

    const timer = window.setTimeout(() => {
      onOpenManualResults(pendingRunId);
      setPendingRunId('');
    }, 1200);

    return () => {
      window.clearTimeout(timer);
    };
  }, [onOpenManualResults, pendingRunId]);

  useEffect(() => {
    if (!pendingSensitivityExperimentId) {
      return;
    }

    const timer = window.setTimeout(() => {
      onOpenSensitivityResults(pendingSensitivityExperimentId);
      setPendingSensitivityExperimentId('');
    }, 1200);

    return () => {
      window.clearTimeout(timer);
    };
  }, [onOpenSensitivityResults, pendingSensitivityExperimentId]);

  const onBaselineChange = (nextBaseline: string) => {
    if (!nextBaseline || nextBaseline === selectedBaseline) {
      return;
    }
    void refreshOptions(nextBaseline);
  };

  const onFormValueChange = (parameter: ModelRunParameterDefinition, value: FormValue) => {
    setFormValues((current) => ({
      ...current,
      [parameter.key]: value
    }));
  };

  const buildSubmitPayload = (confirmWarnings: boolean): ModelRunSubmitRequest => {
    if (!options) {
      throw new Error('Run options are not loaded yet.');
    }

    const overrides: Record<string, number | boolean> = {};

    for (const parameter of options.parameters) {
      const rawValue = formValues[parameter.key];
      const parsedValue = parseFormValue(parameter, rawValue);
      if (!isSameValue(parsedValue, parameter.defaultValue)) {
        overrides[parameter.key] = parsedValue;
      }
    }

    return {
      baseline: selectedBaseline,
      title,
      overrides,
      confirmWarnings
    };
  };

  const onSubmitRun = async (confirmWarnings: boolean) => {
    setPageError('');
    setIsSubmitting(true);

    try {
      const payload = buildSubmitPayload(confirmWarnings);
      const response = await submitModelRun(payload);
      if (!response.accepted) {
        setWarnings(response.warnings);
        return;
      }

      setWarnings([]);
      setTitle('');
      if (response.job) {
        const jobRef = `manual:${response.job.jobId}`;
        setPendingManualJobRef(jobRef);
        onSelectedJobRefChange(jobRef);
      }
      await Promise.all([refreshJobs(), refreshStorageSummary()]);
    } catch (error) {
      setPageError((error as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const onSubmitSensitivity = async (confirmWarnings: boolean) => {
    if (!selectedSensitivityParameter) {
      setPageError('Select a numeric parameter for sensitivity.');
      return;
    }

    setPageError('');
    setIsSubmittingSensitivity(true);

    try {
      const min = Number.parseFloat(sensitivityMin);
      const max = Number.parseFloat(sensitivityMax);
      const response = await submitSensitivityExperiment({
        baseline: selectedBaseline,
        title: sensitivityTitle,
        parameterKey: selectedSensitivityParameter.key,
        min,
        max,
        retainFullOutput: sensitivityRetainFullOutput,
        confirmWarnings
      });

      if (!response.accepted) {
        setSensitivityWarnings(response.warnings);
        return;
      }

      setSensitivityWarnings([]);
      setSensitivityTitle('');
      if (response.experiment) {
        const jobRef = `sensitivity:${response.experiment.experimentId}`;
        setPendingSensitivityJobRef(jobRef);
        onSelectedJobRefChange(jobRef);
      }
      await refreshJobs();
    } catch (error) {
      setPageError((error as Error).message);
    } finally {
      setIsSubmittingSensitivity(false);
    }
  };

  const onCancelActiveSensitivity = async () => {
    if (!activeSensitivityJob) {
      return;
    }

    setPageError('');
    setIsCancelingSensitivity(true);
    try {
      await cancelExperimentJob(activeSensitivityJob.jobRef);
      await refreshJobs();
    } catch (error) {
      setPageError((error as Error).message);
    } finally {
      setIsCancelingSensitivity(false);
    }
  };

  const onCancelJob = async (jobRef: string) => {
    setPageError('');

    try {
      await cancelExperimentJob(jobRef);
      await refreshJobs();
    } catch (error) {
      setPageError((error as Error).message);
    }
  };

  const onSensitivityParameterKeyChange = (value: string) => {
    setSensitivityParameterKey(value);
    setSensitivityWarnings([]);
  };

  const onSensitivityMinChange = (value: string) => {
    setSensitivityMin(value);
    setSensitivityWarnings([]);
  };

  const onSensitivityMaxChange = (value: string) => {
    setSensitivityMax(value);
    setSensitivityWarnings([]);
  };

  return {
    options,
    selectedBaseline,
    title,
    setTitle,
    formValues,
    warnings,
    sensitivityTitle,
    setSensitivityTitle,
    sensitivityParameterKey,
    setSensitivityParameterKey: onSensitivityParameterKeyChange,
    sensitivityMin,
    setSensitivityMin: onSensitivityMinChange,
    sensitivityMax,
    setSensitivityMax: onSensitivityMaxChange,
    sensitivityRetainFullOutput,
    setSensitivityRetainFullOutput,
    sensitivityWarnings,
    jobs,
    selectedJob,
    selectedJobRef,
    logLines,
    logError,
    groupedParameters,
    numericSensitivityParameters,
    selectedSensitivityParameter,
    isLoadingOptions,
    isLoadingJobs,
    isSubmitting,
    isSubmittingSensitivity,
    isCancelingSensitivity,
    pageError,
    pendingRunId,
    pendingSensitivityExperimentId,
    storageSummary,
    executionDisabled,
    manualSubmissionLockedBySensitivity,
    sensitivitySubmissionLockedByManual,
    lockSensitivityId: parseJobRefId(activeSensitivityJobRef),
    lockManualId: parseJobRefId(activeManualJobRef),
    hasActiveSensitivityJob: Boolean(activeSensitivityJob),
    onBaselineChange,
    onFormValueChange,
    onSubmitRun,
    onSubmitSensitivity,
    onCancelActiveSensitivity,
    onCancelJob
  };
}
