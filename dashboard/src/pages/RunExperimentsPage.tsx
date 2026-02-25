import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import type {
  ModelRunJob,
  ModelRunOptionsPayload,
  ModelRunParameterDefinition,
  ModelRunSubmitRequest,
  ModelRunWarning,
  ResultsStorageSummary
} from '../../shared/types';
import { StorageUsageBar } from '../components/StorageUsageBar';
import {
  API_RETRY_DELAY_MS,
  cancelModelRunJob,
  clearModelRunJob,
  fetchModelRunJobs,
  fetchModelRunLogs,
  fetchModelRunOptions,
  fetchResultsStorageSummary,
  isRetryableApiError,
  submitModelRun
} from '../lib/api';

type FormValue = string | boolean;

type ExperimentType = 'manual' | 'sensitivity';

function formatJobStatus(status: ModelRunJob['status']): string {
  return status.replace('_', ' ');
}

function statusClass(status: ModelRunJob['status']): string {
  switch (status) {
    case 'succeeded':
      return 'status-pill complete';
    case 'running':
      return 'status-pill partial';
    case 'queued':
      return 'coverage-pill unsupported';
    case 'canceled':
      return 'coverage-pill unsupported';
    default:
      return 'status-pill invalid';
  }
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

export function RunExperimentsPage() {
  const navigate = useNavigate();
  const [activeType, setActiveType] = useState<ExperimentType>('manual');
  const [options, setOptions] = useState<ModelRunOptionsPayload | null>(null);
  const [selectedBaseline, setSelectedBaseline] = useState<string>('');
  const [title, setTitle] = useState<string>('');
  const [formValues, setFormValues] = useState<Record<string, FormValue>>({});
  const [jobs, setJobs] = useState<ModelRunJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string>('');
  const [logLines, setLogLines] = useState<string[]>([]);
  const logCursorRef = useRef<number>(0);
  const [warnings, setWarnings] = useState<ModelRunWarning[]>([]);
  const [isLoadingOptions, setIsLoadingOptions] = useState<boolean>(true);
  const [isLoadingJobs, setIsLoadingJobs] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [pageError, setPageError] = useState<string>('');
  const [pendingRunId, setPendingRunId] = useState<string>('');
  const [pendingJobId, setPendingJobId] = useState<string>('');
  const [storageSummary, setStorageSummary] = useState<ResultsStorageSummary | null>(null);

  const selectedJob = useMemo(() => jobs.find((job) => job.jobId === selectedJobId) ?? null, [jobs, selectedJobId]);
  const storageUsagePercent = useMemo(() => {
    if (!storageSummary || storageSummary.capBytes <= 0) {
      return 0;
    }
    return (storageSummary.usedBytes / storageSummary.capBytes) * 100;
  }, [storageSummary]);
  const isStorageOverCap = storageUsagePercent >= 100;

  const groupedParameters = useMemo(() => {
    const grouped = new Map<string, ModelRunParameterDefinition[]>();
    for (const parameter of options?.parameters ?? []) {
      const current = grouped.get(parameter.group) ?? [];
      current.push(parameter);
      grouped.set(parameter.group, current);
    }
    return [...grouped.entries()];
  }, [options]);

  const refreshOptions = async (requestedBaseline?: string) => {
    setPageError('');
    setIsLoadingOptions(true);

    try {
      const payload = await fetchModelRunOptions(requestedBaseline);
      setOptions(payload);
      setSelectedBaseline(payload.requestedBaseline);
      setFormValues(toInitialFormValues(payload.parameters));
      setWarnings([]);
    } catch (error) {
      setPageError((error as Error).message);
    } finally {
      setIsLoadingOptions(false);
    }
  };

  const refreshJobs = async () => {
    try {
      const payload = await fetchModelRunJobs();
      setJobs(payload);
      setSelectedJobId((current) => {
        if (current && payload.some((job) => job.jobId === current)) {
          return current;
        }
        return payload[0]?.jobId ?? '';
      });
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
      await refreshOptions();
      if (cancelled) {
        return;
      }
      await refreshJobs();
      if (cancelled) {
        return;
      }
      await refreshStorageSummary();
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
    const interval = window.setInterval(() => {
      void refreshJobs();
    }, 2000);

    return () => {
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void refreshStorageSummary();
    }, 5000);

    return () => {
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    setLogLines([]);
    logCursorRef.current = 0;
  }, [selectedJobId]);

  useEffect(() => {
    if (!selectedJobId) {
      return;
    }

    let cancelled = false;

    const pollLogs = async () => {
      try {
        const payload = await fetchModelRunLogs(selectedJobId, logCursorRef.current, 200);
        if (cancelled) {
          return;
        }

        logCursorRef.current = payload.nextCursor;
        setLogLines((current) => {
          if (payload.truncated) {
            return payload.lines;
          }
          return [...current, ...payload.lines].slice(-10_000);
        });
      } catch (error) {
        if (!isRetryableApiError(error)) {
          setPageError((error as Error).message);
        }
      }
    };

    void pollLogs();
    const interval = window.setInterval(() => {
      void pollLogs();
    }, 1500);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [selectedJobId]);

  useEffect(() => {
    if (!pendingJobId) {
      return;
    }

    const job = jobs.find((item) => item.jobId === pendingJobId);
    if (!job) {
      return;
    }

    if (job.status === 'succeeded') {
      setPendingRunId(job.runId);
      setPendingJobId('');
      return;
    }

    if (job.status === 'failed' || job.status === 'canceled') {
      setPendingJobId('');
    }
  }, [jobs, pendingJobId]);

  useEffect(() => {
    if (!pendingRunId) {
      return;
    }

    const timer = window.setTimeout(() => {
      navigate(`/model-results?runId=${encodeURIComponent(pendingRunId)}`);
    }, 1200);

    return () => {
      window.clearTimeout(timer);
    };
  }, [navigate, pendingRunId]);

  if (!isLoadingOptions && options && !options.executionEnabled) {
    return <Navigate to="/model-results" replace />;
  }

  const onBaselineChange = (nextBaseline: string) => {
    if (!nextBaseline || nextBaseline === selectedBaseline) {
      return;
    }
    void refreshOptions(nextBaseline);
  };

  const updateFormValue = (parameter: ModelRunParameterDefinition, value: FormValue) => {
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

  const submitRun = async (confirmWarnings: boolean) => {
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
        setPendingJobId(response.job.jobId);
        setSelectedJobId(response.job.jobId);
      }
      await refreshJobs();
      await refreshStorageSummary();
    } catch (error) {
      setPageError((error as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const cancelJob = async (jobId: string) => {
    setPageError('');

    try {
      await cancelModelRunJob(jobId);
      await refreshJobs();
      await refreshStorageSummary();
    } catch (error) {
      setPageError((error as Error).message);
    }
  };

  const clearJob = async (jobId: string) => {
    setPageError('');

    try {
      await clearModelRunJob(jobId);
      await refreshJobs();
      await refreshStorageSummary();
    } catch (error) {
      setPageError((error as Error).message);
    }
  };

  return (
    <section className="run-exp-layout">
      {pageError && <p className="error-banner">{pageError}</p>}
      {pendingRunId && (
        <p className="waiting-banner">
          Run completed. Redirecting to results...{' '}
          <Link to={`/model-results?runId=${encodeURIComponent(pendingRunId)}`}>View in Model Results</Link>
        </p>
      )}
      {storageSummary && <StorageUsageBar usedBytes={storageSummary.usedBytes} capBytes={storageSummary.capBytes} />}
      {storageSummary && isStorageOverCap && (
        <p className="error-banner">Results storage is over cap. Delete one or more runs before starting another run.</p>
      )}

      <article className="results-card">
        <h2>Run Experiments</h2>
        <p>Run calibrated scenarios and inspect queue status/logs.</p>

        <div className="experiment-tabs">
          <button
            type="button"
            className={`filter-pill ${activeType === 'manual' ? 'active' : ''}`}
            onClick={() => setActiveType('manual')}
          >
            Manual Parameters
          </button>
          <button
            type="button"
            className={`filter-pill ${activeType === 'sensitivity' ? 'active' : ''}`}
            onClick={() => setActiveType('sensitivity')}
          >
            Sensitivity
          </button>
        </div>
      </article>

      {activeType === 'sensitivity' ? (
        <article className="results-card">
          <h3>Sensitivity</h3>
          <p>This experiment type is planned and not yet implemented.</p>
        </article>
      ) : (
        <div className="run-exp-grid">
          <article className="results-card">
            <h3>Manual Parameters</h3>
            <p>Choose a calibration parameter version, set USER SET parameters, then queue a model run.</p>

            {isLoadingOptions || !options ? (
              <p className="loading-banner">Loading run options...</p>
            ) : (
              <>
                <div className="run-form-head">
                  <label>
                    Calibration Parameter Version
                    <select
                      value={selectedBaseline}
                      onChange={(event) => onBaselineChange(event.target.value)}
                    >
                      {options.snapshots.map((snapshot) => (
                        <option key={snapshot.version} value={snapshot.version}>
                          {snapshot.version} ({snapshot.status})
                        </option>
                      ))}
                    </select>
                    <Link
                      className="summary-link-inline"
                      to={`/compare?mode=single&version=${encodeURIComponent(selectedBaseline)}`}
                    >
                      View in Calibration Versions
                    </Link>
                  </label>

                  <label>
                    Optional run title
                    <input
                      type="text"
                      value={title}
                      onChange={(event) => setTitle(event.target.value)}
                      maxLength={120}
                      placeholder="Policy scenario label"
                    />
                    <small>Output folder uses: &lt;title&gt; &lt;calibration-version&gt;.</small>
                  </label>
                </div>

                {warnings.length > 0 && (
                  <div className="run-warning-card">
                    <h4>Warnings detected</h4>
                    <p>Confirm to submit anyway.</p>
                    <ul>
                      {warnings.map((warning) => (
                        <li key={warning.code}>{warning.message}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="run-param-groups">
                  {groupedParameters.map(([group, parameters]) => (
                    <section key={group} className="run-param-group">
                      <h4>{group}</h4>
                      <div className="run-param-grid">
                        {parameters.map((parameter) => (
                          <label key={parameter.key} className="run-param-item">
                            <span>{parameter.title}</span>
                            <small>{parameter.key}</small>
                            {parameter.type === 'boolean' ? (
                              <input
                                type="checkbox"
                                checked={Boolean(formValues[parameter.key])}
                                onChange={(event) => updateFormValue(parameter, event.target.checked)}
                              />
                            ) : (
                              <input
                                type="number"
                                step={parameter.type === 'integer' ? 1 : 'any'}
                                value={String(formValues[parameter.key] ?? '')}
                                onChange={(event) => updateFormValue(parameter, event.target.value)}
                              />
                            )}
                            <small>{parameter.description}</small>
                          </label>
                        ))}
                      </div>
                    </section>
                  ))}
                </div>

                <div className="run-form-actions">
                  <button type="button" className="primary-button" disabled={isSubmitting} onClick={() => void submitRun(false)}>
                    {isSubmitting ? 'Submitting...' : 'Queue Run'}
                  </button>
                  {warnings.length > 0 && (
                    <button type="button" className="secondary-button" disabled={isSubmitting} onClick={() => void submitRun(true)}>
                      Confirm and Queue
                    </button>
                  )}
                </div>
              </>
            )}
          </article>

          <article className="results-card">
            <h3>Job Queue</h3>
            {isLoadingJobs ? (
              <p className="loading-banner">Loading jobs...</p>
            ) : jobs.length === 0 ? (
              <p className="info-banner">No jobs submitted yet.</p>
            ) : (
              <ul className="job-list">
                {jobs.map((job) => (
                  <li key={job.jobId} className={`job-item ${selectedJobId === job.jobId ? 'focused' : ''}`}>
                    <button type="button" className="run-focus-btn" onClick={() => setSelectedJobId(job.jobId)}>
                      {selectedJobId === job.jobId ? 'Viewing' : 'View'}
                    </button>
                    <strong>{job.title || job.runId}</strong>
                    <p>Baseline: {job.baseline}</p>
                    <p>
                      <span className={statusClass(job.status)}>{formatJobStatus(job.status)}</span>
                    </p>
                    <p>{job.createdAt}</p>
                    {(job.status === 'queued' || job.status === 'running') && (
                      <button type="button" className="secondary-button" onClick={() => void cancelJob(job.jobId)}>
                        Cancel
                      </button>
                    )}
                    {(job.status === 'succeeded' || job.status === 'failed' || job.status === 'canceled') && (
                      <button type="button" className="secondary-button" onClick={() => void clearJob(job.jobId)}>
                        Clear
                      </button>
                    )}
                    {job.status === 'succeeded' && (
                      <Link className="summary-link-inline" to={`/model-results?runId=${encodeURIComponent(job.runId)}`}>
                        View in Model Results
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </article>

          <article className="results-card">
            <h3>Job Logs {selectedJob ? `(${selectedJob.runId})` : ''}</h3>
            {selectedJob ? (
              <pre className="job-log-view">{logLines.length === 0 ? 'No logs yet.' : logLines.join('\n')}</pre>
            ) : (
              <p className="info-banner">Select a job to view logs.</p>
            )}
          </article>
        </div>
      )}
    </section>
  );
}
