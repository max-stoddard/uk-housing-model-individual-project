import type { CompareResponse, ParameterCardMeta } from '../../shared/types';

interface VersionsResponse {
  versions: string[];
  inProgressVersions?: string[];
}

export interface VersionsPayload {
  versions: string[];
  inProgressVersions: string[];
}

interface CatalogResponse {
  items: ParameterCardMeta[];
}

interface GitStatsResponse {
  baseCommit: string;
  filesChanged: number;
  insertions: number;
  deletions: number;
  lineChanges: number;
  commitCount: number;
  weekly: {
    filesChanged: number;
    lineChanges: number;
    commitCount: number;
  };
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').trim().replace(/\/+$/, '');

function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return apiBaseUrl ? `${apiBaseUrl}${normalizedPath}` : normalizedPath;
}

export async function fetchVersions(): Promise<VersionsPayload> {
  const response = await fetch(buildApiUrl('/api/versions'));
  if (!response.ok) {
    throw new Error('Failed to fetch versions');
  }
  const payload = (await response.json()) as VersionsResponse;
  return {
    versions: payload.versions,
    inProgressVersions: payload.inProgressVersions ?? []
  };
}

export async function fetchCatalog(): Promise<ParameterCardMeta[]> {
  const response = await fetch(buildApiUrl('/api/parameter-catalog'));
  if (!response.ok) {
    throw new Error('Failed to fetch parameter catalog');
  }
  const payload = (await response.json()) as CatalogResponse;
  return payload.items;
}

export async function fetchGitStats(): Promise<GitStatsResponse> {
  const response = await fetch(buildApiUrl('/api/git-stats'));
  if (!response.ok) {
    throw new Error('Failed to fetch git stats');
  }
  return (await response.json()) as GitStatsResponse;
}

export async function fetchCompare(
  left: string,
  right: string,
  ids: string[],
  provenanceScope: 'range' | 'through_right' = 'range'
): Promise<CompareResponse> {
  const params = new URLSearchParams({
    left,
    right,
    ids: ids.join(','),
    provenanceScope
  });

  const response = await fetch(`${buildApiUrl('/api/compare')}?${params.toString()}`);
  if (!response.ok) {
    const payload = (await response.json()) as { error?: string };
    throw new Error(payload.error ?? 'Failed to fetch comparison');
  }

  return (await response.json()) as CompareResponse;
}
