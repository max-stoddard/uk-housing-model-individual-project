import type { ModelRunParameterDefinition, ModelRunWarning } from '../../../shared/types';

type NumericParameter = ModelRunParameterDefinition & { type: 'integer' | 'number' };

interface SensitivitySetupCardProps {
  executionDisabled: boolean;
  isLoadingOptions: boolean;
  selectedBaseline: string;
  onBaselineChange: (baseline: string) => void;
  snapshots: Array<{ version: string; status: string }>;
  numericParameters: NumericParameter[];
  parameterKey: string;
  onParameterKeyChange: (value: string) => void;
  minValue: string;
  maxValue: string;
  onMinValueChange: (value: string) => void;
  onMaxValueChange: (value: string) => void;
  title: string;
  onTitleChange: (value: string) => void;
  retainFullOutput: boolean;
  onRetainFullOutputChange: (value: boolean) => void;
  selectedParameter: NumericParameter | null;
  warnings: ModelRunWarning[];
  isSubmitting: boolean;
  isCanceling: boolean;
  sensitivitySubmissionLockedByManual: boolean;
  lockMessage: string | null;
  hasActiveSensitivityJob: boolean;
  onSubmit: (confirmWarnings: boolean) => void;
  onCancelActive: () => void;
}

export function SensitivitySetupCard({
  executionDisabled,
  isLoadingOptions,
  selectedBaseline,
  onBaselineChange,
  snapshots,
  numericParameters,
  parameterKey,
  onParameterKeyChange,
  minValue,
  maxValue,
  onMinValueChange,
  onMaxValueChange,
  title,
  onTitleChange,
  retainFullOutput,
  onRetainFullOutputChange,
  selectedParameter,
  warnings,
  isSubmitting,
  isCanceling,
  sensitivitySubmissionLockedByManual,
  lockMessage,
  hasActiveSensitivityJob,
  onSubmit,
  onCancelActive
}: SensitivitySetupCardProps) {
  return (
    <article className="results-card">
      <h3>Sensitivity Setup</h3>
      <p>Run one-parameter-at-a-time 5-point sweeps with baseline comparison.</p>
      {sensitivitySubmissionLockedByManual && lockMessage && <p className="info-banner">{lockMessage}</p>}

      {isLoadingOptions ? (
        <p className="loading-banner">Loading sensitivity options...</p>
      ) : (
        <>
          <div className="run-form-head">
            <label>
              Calibration Parameter Version
              <select
                value={selectedBaseline}
                disabled={executionDisabled}
                onChange={(event) => onBaselineChange(event.target.value)}
              >
                {snapshots.map((snapshot) => (
                  <option key={snapshot.version} value={snapshot.version}>
                    {snapshot.version} ({snapshot.status})
                  </option>
                ))}
              </select>
            </label>

            <label>
              Numeric parameter
              <select
                value={parameterKey}
                disabled={executionDisabled}
                onChange={(event) => onParameterKeyChange(event.target.value)}
              >
                {numericParameters.map((parameter) => (
                  <option key={parameter.key} value={parameter.key}>
                    {parameter.title} ({parameter.key})
                  </option>
                ))}
              </select>
            </label>

            <label>
              Min value
              <input
                type="number"
                step={selectedParameter?.type === 'integer' ? 1 : 'any'}
                value={minValue}
                disabled={executionDisabled}
                onChange={(event) => onMinValueChange(event.target.value)}
              />
            </label>

            <label>
              Max value
              <input
                type="number"
                step={selectedParameter?.type === 'integer' ? 1 : 'any'}
                value={maxValue}
                disabled={executionDisabled}
                onChange={(event) => onMaxValueChange(event.target.value)}
              />
            </label>

            <label>
              Optional experiment title
              <input
                type="text"
                value={title}
                disabled={executionDisabled}
                onChange={(event) => onTitleChange(event.target.value)}
                maxLength={120}
                placeholder="Policy sensitivity label"
              />
            </label>

            <label className="sensitivity-checkbox-field">
              <span>Retain full point outputs</span>
              <input
                type="checkbox"
                checked={retainFullOutput}
                disabled={executionDisabled}
                onChange={(event) => onRetainFullOutputChange(event.target.checked)}
              />
              <small>Off by default. Keep summary only unless full outputs are required.</small>
            </label>
          </div>

          {selectedParameter && (
            <p className="info-banner">
              Baseline {selectedParameter.key}={String(selectedParameter.defaultValue)}
            </p>
          )}

          {warnings.length > 0 && (
            <div className="run-warning-card">
              <h4>Warnings detected</h4>
              <p>Confirm to start anyway.</p>
              <ul>
                {warnings.map((warning) => (
                  <li key={`${warning.code}-${warning.message}`}>{warning.message}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="run-form-actions">
            <button
              type="button"
              className="primary-button"
              disabled={isSubmitting || executionDisabled || sensitivitySubmissionLockedByManual || hasActiveSensitivityJob}
              onClick={() => onSubmit(false)}
            >
              {isSubmitting ? 'Submitting...' : 'Start Sensitivity'}
            </button>
            {warnings.length > 0 && (
              <button
                type="button"
                className="secondary-button"
                disabled={isSubmitting || executionDisabled || sensitivitySubmissionLockedByManual || hasActiveSensitivityJob}
                onClick={() => onSubmit(true)}
              >
                Confirm and Start
              </button>
            )}
            {hasActiveSensitivityJob && (
              <button
                type="button"
                className="secondary-button"
                disabled={isCanceling || executionDisabled}
                onClick={onCancelActive}
              >
                {isCanceling ? 'Canceling...' : 'Cancel Active Experiment'}
              </button>
            )}
          </div>
        </>
      )}
    </article>
  );
}
