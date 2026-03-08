// Author: Max Stoddard
export type VersionLabelKind = 'in_progress' | 'latest' | 'original';

export interface VersionLabelState {
  version: string;
  isInProgress: boolean;
  isLatest: boolean;
  isOriginal: boolean;
  kinds: VersionLabelKind[];
}

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
