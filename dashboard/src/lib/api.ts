import type { CompareResponse, ParameterCardMeta } from '../../shared/types';

interface VersionsResponse {
  versions: string[];
}

interface CatalogResponse {
  items: ParameterCardMeta[];
}

export async function fetchVersions(): Promise<string[]> {
  const response = await fetch('/api/versions');
  if (!response.ok) {
    throw new Error('Failed to fetch versions');
  }
  const payload = (await response.json()) as VersionsResponse;
  return payload.versions;
}

export async function fetchCatalog(): Promise<ParameterCardMeta[]> {
  const response = await fetch('/api/parameter-catalog');
  if (!response.ok) {
    throw new Error('Failed to fetch parameter catalog');
  }
  const payload = (await response.json()) as CatalogResponse;
  return payload.items;
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

  const response = await fetch(`/api/compare?${params.toString()}`);
  if (!response.ok) {
    const payload = (await response.json()) as { error?: string };
    throw new Error(payload.error ?? 'Failed to fetch comparison');
  }

  return (await response.json()) as CompareResponse;
}
