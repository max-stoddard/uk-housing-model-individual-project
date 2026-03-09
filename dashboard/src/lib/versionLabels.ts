// Author: Max Stoddard
export type VersionLabelKind = 'in_progress' | 'latest' | 'original';

export interface VersionLabelState {
  version: string;
  isInProgress: boolean;
  isLatest: boolean;
  isOriginal: boolean;
  kinds: VersionLabelKind[];
}

const RESULTS_RUN_VERSION_PATTERN = /^(v\d+(?:\.\d+)*)-output$/;

export function getLatestStableVersion(versions: readonly string[], inProgressVersions: readonly string[]): string {
  const inProgressSet = new Set(inProgressVersions);
  for (let index = versions.length - 1; index >= 0; index -= 1) {
    const version = versions[index] ?? '';
    if (version && !inProgressSet.has(version)) {
      return version;
    }
  }
  return '';
}

export function buildVersionLabelState(
  version: string,
  latestStableVersion: string,
  inProgressVersions: ReadonlySet<string>
): VersionLabelState {
  const isInProgress = inProgressVersions.has(version);
  const isLatest = Boolean(version) && version === latestStableVersion && !isInProgress;
  const isOriginal = version === 'v0';
  const kinds: VersionLabelKind[] = [];

  if (isInProgress) {
    kinds.push('in_progress');
  }
  if (isLatest) {
    kinds.push('latest');
  }
  if (isOriginal) {
    kinds.push('original');
  }

  return {
    version,
    isInProgress,
    isLatest,
    isOriginal,
    kinds
  };
}

export function extractVersionFromResultsRunId(runId: string): string {
  const match = RESULTS_RUN_VERSION_PATTERN.exec(runId.trim());
  return match?.[1] ?? '';
}

export function buildResultsRunVersionLabelState(
  runId: string,
  versions: readonly string[],
  inProgressVersions: readonly string[]
): VersionLabelState | null {
  const version = extractVersionFromResultsRunId(runId);
  if (!version || versions.length === 0 || !versions.includes(version)) {
    return null;
  }

  return buildVersionLabelState(version, getLatestStableVersion(versions, inProgressVersions), new Set(inProgressVersions));
}

function formatKind(kind: VersionLabelKind): string {
  switch (kind) {
    case 'in_progress':
      return 'In progress';
    case 'latest':
      return 'Latest';
    case 'original':
      return 'Original';
  }
}

export function formatVersionOptionLabel(version: string, state: VersionLabelState): string {
  if (state.kinds.length === 0) {
    return version;
  }
  return `${version} (${state.kinds.map(formatKind).join(', ')})`;
}
