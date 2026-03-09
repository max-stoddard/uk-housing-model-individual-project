// Author: Max Stoddard
import type { ResultsRunStatus } from '../../shared/types';
import type { VersionLabelKind, VersionLabelState } from '../lib/versionLabels';

function manualResultsVersionKinds(state: VersionLabelState | null): Array<Extract<VersionLabelKind, 'latest' | 'original'>> {
  return (state?.kinds.filter((kind): kind is Extract<VersionLabelKind, 'latest' | 'original'> => kind !== 'in_progress') ??
    []);
}

function manualResultsVersionPillClass(kind: Extract<VersionLabelKind, 'latest' | 'original'>): string {
  switch (kind) {
    case 'latest':
      return 'status-pill status-pill-latest';
    case 'original':
      return 'status-pill status-pill-original';
  }
}

function manualResultsVersionPillText(kind: Extract<VersionLabelKind, 'latest' | 'original'>): string {
  switch (kind) {
    case 'latest':
      return 'Latest';
    case 'original':
      return 'Original';
  }
}

function statusClass(status: ResultsRunStatus): string {
  switch (status) {
    case 'complete':
      return 'status-pill complete';
    case 'partial':
      return 'status-pill partial';
    default:
      return 'status-pill invalid';
  }
}

interface ManualSelectionStatusPillsProps {
  status: ResultsRunStatus;
  versionLabelState: VersionLabelState | null;
}

export function ManualSelectionStatusPills({ status, versionLabelState }: ManualSelectionStatusPillsProps) {
  const versionKinds = manualResultsVersionKinds(versionLabelState);

  return (
    <span className="manual-selection-status-pills">
      <span className={statusClass(status)}>{status}</span>
      {versionKinds.map((kind) => (
        <span key={kind} className={manualResultsVersionPillClass(kind)}>
          {manualResultsVersionPillText(kind)}
        </span>
      ))}
    </span>
  );
}
