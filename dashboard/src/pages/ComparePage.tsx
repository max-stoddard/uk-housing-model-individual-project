import { useEffect, useMemo, useState } from 'react';
import type { CompareResponse, ParameterCardMeta, ParameterGroup } from '../../shared/types';
import { API_RETRY_DELAY_MS, fetchCatalog, fetchCompare, fetchVersions, isRetryableApiError } from '../lib/api';
import { CompareCard } from '../components/CompareCard';

const GROUP_ORDER: ParameterGroup[] = [
  'Household Demographics & Wealth',
  'Government & Tax',
  'Housing & Rental Market',
  'Purchase & Mortgage',
  'BTL & Investor Behavior'
];

type ChangeFilter = 'all' | 'updated' | 'unchanged';
type ViewMode = 'single' | 'compare';

function getDefaultDisplayVersion(versions: string[], inProgressVersions: string[]): string {
  const inProgressSet = new Set(inProgressVersions);
  for (let index = versions.length - 1; index >= 0; index -= 1) {
    const version = versions[index];
    if (!inProgressSet.has(version)) {
      return version;
    }
  }
  return versions[versions.length - 1] ?? '';
}

function groupCatalog(catalog: ParameterCardMeta[]) {
  const grouped = new Map<string, ParameterCardMeta[]>();
  for (const item of catalog) {
    const current = grouped.get(item.group) ?? [];
    current.push(item);
    grouped.set(item.group, current);
  }
  return grouped;
}

function isUpdated(item: CompareResponse['items'][number], mode: ViewMode): boolean {
  if (mode === 'single') {
    return item.changeOriginsInRange.length > 0;
  }
  return !item.unchanged;
}

function groupCompareItems(compareData: CompareResponse | null, filter: ChangeFilter, mode: ViewMode) {
  const grouped = new Map<ParameterGroup, CompareResponse['items']>();
  if (!compareData) {
    return grouped;
  }

  for (const item of compareData.items) {
    const updated = isUpdated(item, mode);
    const include = filter === 'all' || (filter === 'updated' ? updated : !updated);
    if (!include) {
      continue;
    }

    const current = grouped.get(item.group) ?? [];
    current.push(item);
    grouped.set(item.group, current);
  }

  return grouped;
}

export function ComparePage() {
  const [versions, setVersions] = useState<string[]>([]);
  const [inProgressVersions, setInProgressVersions] = useState<string[]>([]);
  const [catalog, setCatalog] = useState<ParameterCardMeta[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<string>('');
  const [left, setLeft] = useState<string>('');
  const [right, setRight] = useState<string>('');
  const [mode, setMode] = useState<ViewMode>('single');
  const [search, setSearch] = useState<string>('');
  const [compareData, setCompareData] = useState<CompareResponse | null>(null);
  const [error, setError] = useState<string>('');
  const [isBootstrapping, setIsBootstrapping] = useState<boolean>(true);
  const [isBootstrapReady, setIsBootstrapReady] = useState<boolean>(false);
  const [isWaitingForApi, setIsWaitingForApi] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSetupOpen, setIsSetupOpen] = useState<boolean>(true);
  const [changeFilter, setChangeFilter] = useState<ChangeFilter>('all');
  const [sectionOpen, setSectionOpen] = useState<Record<string, boolean>>({});
  const defaultOpenGroup = GROUP_ORDER[0];

  useEffect(() => {
    let cancelled = false;
    let retryTimer: number | undefined;

    const load = async () => {
      setError('');
      setIsBootstrapping(true);
      setIsWaitingForApi(false);

      try {
        const [versionsPayload, catalogList] = await Promise.all([fetchVersions(), fetchCatalog()]);
        if (cancelled) {
          return;
        }

        const versionList = versionsPayload.versions;
        const defaultDisplayVersion = getDefaultDisplayVersion(versionList, versionsPayload.inProgressVersions);
        setVersions(versionList);
        setInProgressVersions(versionsPayload.inProgressVersions);
        setCatalog(catalogList);
        setSelectedIds(catalogList.map((item) => item.id));
        setSelectedVersion(defaultDisplayVersion);
        setLeft(versionList[0] ?? '');
        setRight(defaultDisplayVersion);
        setIsBootstrapReady(true);
        setIsBootstrapping(false);
      } catch (loadError) {
        if (cancelled) {
          return;
        }

        if (isRetryableApiError(loadError)) {
          setIsWaitingForApi(true);
          setIsBootstrapReady(false);
          setIsBootstrapping(false);
          retryTimer = window.setTimeout(() => {
            void load();
          }, API_RETRY_DELAY_MS);
          return;
        }

        setError((loadError as Error).message);
        setIsBootstrapReady(false);
        setIsBootstrapping(false);
      }
    };

    void load();

    return () => {
      cancelled = true;
      if (retryTimer !== undefined) {
        window.clearTimeout(retryTimer);
      }
    };
  }, []);

  useEffect(() => {
    if (mode === 'compare') {
      if (!left && versions.length > 0) {
        setLeft(versions[0]);
      }
      if (!right && versions.length > 0) {
        setRight(getDefaultDisplayVersion(versions, inProgressVersions));
      }
    }
  }, [mode, left, right, versions, inProgressVersions]);

  useEffect(() => {
    if (!isBootstrapReady) {
      setCompareData(null);
      return;
    }

    let cancelled = false;
    let retryTimer: number | undefined;

    const run = async () => {
      if (selectedIds.length === 0) {
        setCompareData(null);
        setIsWaitingForApi(false);
        return;
      }

      if (mode === 'single') {
        if (!selectedVersion) {
          setCompareData(null);
          setIsWaitingForApi(false);
          return;
        }

        setIsLoading(true);
        setIsWaitingForApi(false);
        setError('');
        try {
          const payload = await fetchCompare(selectedVersion, selectedVersion, selectedIds, 'through_right');
          if (cancelled) {
            return;
          }
          setCompareData(payload);
        } catch (loadError) {
          if (cancelled) {
            return;
          }
          if (isRetryableApiError(loadError)) {
            setIsWaitingForApi(true);
            retryTimer = window.setTimeout(() => {
              void run();
            }, API_RETRY_DELAY_MS);
            return;
          }
          setIsWaitingForApi(false);
          setError((loadError as Error).message);
        } finally {
          if (!cancelled) {
            setIsLoading(false);
          }
        }
        return;
      }

      if (!left || !right) {
        setCompareData(null);
        setIsWaitingForApi(false);
        return;
      }

      setIsLoading(true);
      setIsWaitingForApi(false);
      setError('');
      try {
        const payload = await fetchCompare(left, right, selectedIds, 'range');
        if (cancelled) {
          return;
        }
        setCompareData(payload);
      } catch (loadError) {
        if (cancelled) {
          return;
        }
        if (isRetryableApiError(loadError)) {
          setIsWaitingForApi(true);
          retryTimer = window.setTimeout(() => {
            void run();
          }, API_RETRY_DELAY_MS);
          return;
        }
        setIsWaitingForApi(false);
        setError((loadError as Error).message);
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void run();

    return () => {
      cancelled = true;
      if (retryTimer !== undefined) {
        window.clearTimeout(retryTimer);
      }
    };
  }, [isBootstrapReady, mode, left, right, selectedVersion, selectedIds]);

  const filteredCatalog = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) {
      return catalog;
    }
    return catalog.filter(
      (item) =>
        item.title.toLowerCase().includes(term) ||
        item.id.toLowerCase().includes(term) ||
        item.configKeys.some((key) => key.toLowerCase().includes(term))
    );
  }, [catalog, search]);

  const setupGrouped = useMemo(() => groupCatalog(filteredCatalog), [filteredCatalog]);

  const groupedResults = useMemo(() => groupCompareItems(compareData, changeFilter, mode), [compareData, changeFilter, mode]);

  const sectionCounts = useMemo(() => {
    const counts = new Map<ParameterGroup, { updated: number; unchanged: number }>();
    if (!compareData) {
      return counts;
    }
    for (const item of compareData.items) {
      const current = counts.get(item.group) ?? { updated: 0, unchanged: 0 };
      if (isUpdated(item, mode)) {
        current.updated += 1;
      } else {
        current.unchanged += 1;
      }
      counts.set(item.group, current);
    }
    return counts;
  }, [compareData, mode]);

  useEffect(() => {
    if (!compareData) {
      return;
    }

    setSectionOpen((current) => {
      if (Object.keys(current).length === 0) {
        const seeded: Record<string, boolean> = {};
        for (const groupName of GROUP_ORDER) {
          seeded[groupName] = groupName === defaultOpenGroup;
        }
        return seeded;
      }

      let changed = false;
      const nextState = { ...current };
      for (const groupName of GROUP_ORDER) {
        if (!(groupName in nextState)) {
          nextState[groupName] = false;
          changed = true;
        }
      }
      return changed ? nextState : current;
    });
  }, [compareData, defaultOpenGroup]);

  const toggleId = (id: string) => {
    setSelectedIds((current) => {
      if (current.includes(id)) {
        return current.filter((value) => value !== id);
      }
      return [...current, id];
    });
  };

  const toggleAll = () => {
    if (selectedIds.length === catalog.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(catalog.map((item) => item.id));
    }
  };

  const shownCount = compareData
    ? compareData.items.filter((item) =>
        changeFilter === 'all' ? true : changeFilter === 'updated' ? isUpdated(item, mode) : !isUpdated(item, mode)
      ).length
    : 0;

  const titleText = mode === 'single' ? `Model parameters at ${selectedVersion || 'n/a'}` : `${left} vs ${right}`;
  const inProgressSet = useMemo(() => new Set(inProgressVersions), [inProgressVersions]);
  const isInProgressVersion = (version: string) => inProgressSet.has(version);
  const withInProgressLabel = (version: string) =>
    isInProgressVersion(version) ? `${version} (In progress)` : version;

  return (
    <section className={`compare-layout ${isSetupOpen ? '' : 'setup-collapsed'}`}>
      {isSetupOpen ? (
        <aside className="sidebar">
          <div className="sidebar-head">
            <h2>Workspace Setup</h2>
            <div className="sidebar-head-actions">
              <p>{selectedIds.length} tracked</p>
              <button
                type="button"
                className="sidebar-icon-toggle"
                onClick={() => setIsSetupOpen(false)}
                aria-label="Collapse setup panel"
                title="Collapse setup"
              >
                ◂
              </button>
            </div>
          </div>

          <label>Mode</label>
          <div className="mode-switch-row">
            <button
              type="button"
              className={`filter-pill ${mode === 'single' ? 'active' : ''}`}
              onClick={() => setMode('single')}
            >
              Single version
            </button>
            <button
              type="button"
              className={`filter-pill ${mode === 'compare' ? 'active' : ''}`}
              onClick={() => setMode('compare')}
            >
              Compare versions
            </button>
          </div>

          {mode === 'single' ? (
            <>
              <label htmlFor="single-version">Version</label>
              <select id="single-version" value={selectedVersion} onChange={(event) => setSelectedVersion(event.target.value)}>
                {versions.map((version) => (
                  <option key={version} value={version}>
                    {withInProgressLabel(version)}
                  </option>
                ))}
              </select>
            </>
          ) : (
            <>
              <label htmlFor="left-version">Left version</label>
              <select id="left-version" value={left} onChange={(event) => setLeft(event.target.value)}>
                {versions.map((version) => (
                  <option key={version} value={version}>
                    {withInProgressLabel(version)}
                  </option>
                ))}
              </select>

              <label htmlFor="right-version">Right version</label>
              <select id="right-version" value={right} onChange={(event) => setRight(event.target.value)}>
                {versions.map((version) => (
                  <option key={version} value={version}>
                    {withInProgressLabel(version)}
                  </option>
                ))}
              </select>
            </>
          )}

          <label htmlFor="search-params">Find parameters</label>
          <input
            id="search-params"
            placeholder="Search title or key"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />

          <button type="button" className="secondary-button" onClick={toggleAll}>
            {selectedIds.length === catalog.length ? 'Clear all' : 'Select all'}
          </button>

          <div className="param-groups">
            {[...setupGrouped.entries()].map(([groupName, entries]) => (
              <div key={groupName}>
                <h3>{groupName}</h3>
                {entries.map((entry) => (
                  <label key={entry.id} className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(entry.id)}
                      onChange={() => toggleId(entry.id)}
                    />
                    <span>{entry.title}</span>
                  </label>
                ))}
              </div>
            ))}
          </div>
        </aside>
      ) : (
        <button
          type="button"
          className="setup-rail-toggle"
          onClick={() => setIsSetupOpen(true)}
          aria-label="Open setup panel"
          title="Open setup"
        >
          ☰
        </button>
      )}

      <div className="compare-results">
        <section className="summary-panel">
          <h2>Model Parameter Workspace</h2>
          <p>
            This page exists to visualize calibrated model parameters and to track iterative project progress as inputs are
            refined over versions. Single-version mode is the default for reviewing the current state; compare mode is
            available when you need version-to-version deltas.
          </p>
        </section>

        <header className="results-head">
          <h2>{titleText}</h2>
          {(mode === 'single' ? isInProgressVersion(selectedVersion) : isInProgressVersion(left) || isInProgressVersion(right)) && (
            <div className="results-version-tags">
              {mode === 'single' && isInProgressVersion(selectedVersion) && (
                <span className="status-pill-in-progress">Version {selectedVersion} in progress</span>
              )}
              {mode === 'compare' && isInProgressVersion(left) && (
                <span className="status-pill-in-progress">Left {left} in progress</span>
              )}
              {mode === 'compare' && isInProgressVersion(right) && (
                <span className="status-pill-in-progress">Right {right} in progress</span>
              )}
            </div>
          )}
          <p>
            Visualizing tracked model parameters and calibration provenance from
            <code> input-data-versions/version-notes.json</code>
          </p>

          <div className="change-filter-row">
            <span>Filter:</span>
            <button
              type="button"
              className={`filter-pill ${changeFilter === 'all' ? 'active' : ''}`}
              onClick={() => setChangeFilter('all')}
            >
              All
            </button>
            <button
              type="button"
              className={`filter-pill ${changeFilter === 'updated' ? 'active' : ''}`}
              onClick={() => setChangeFilter('updated')}
            >
              Updated
            </button>
            <button
              type="button"
              className={`filter-pill ${changeFilter === 'unchanged' ? 'active' : ''}`}
              onClick={() => setChangeFilter('unchanged')}
            >
              No change
            </button>
            <strong>{shownCount}</strong>
          </div>
        </header>

        {error && <p className="error-banner">{error}</p>}
        {isBootstrapping && <p className="loading-banner">Loading compare workspace...</p>}
        {!isBootstrapping && isLoading && <p className="loading-banner">Loading parameters...</p>}
        {isWaitingForApi && (
          <p className="waiting-banner">Waiting for API to become available. Retrying every 2 seconds...</p>
        )}

        {!isBootstrapping && !isLoading && compareData?.items.length === 0 && (
          <p className="loading-banner">No parameters selected.</p>
        )}

        <div className="cards-stack">
          {GROUP_ORDER.filter((group) => (groupedResults.get(group)?.length ?? 0) > 0).map((groupName) => {
            const items = groupedResults.get(groupName) ?? [];
            const counts = sectionCounts.get(groupName) ?? { updated: 0, unchanged: 0 };
            const open = sectionOpen[groupName] ?? false;

            return (
              <section className="result-group" key={groupName}>
                <button
                  type="button"
                  className="result-group-header"
                  onClick={() =>
                    setSectionOpen((current) => ({
                      ...current,
                      [groupName]: !open
                    }))
                  }
                >
                  <span className="result-group-title">
                    {open ? '▾' : '▸'} {groupName}
                  </span>
                  <span className="result-group-counts">
                    <span className="unchanged">No change: {counts.unchanged}</span>
                    <span className="updated">Updated: {counts.updated}</span>
                  </span>
                </button>

                {open && (
                  <div className="result-group-body">
                    {items.map((item, index) => (
                      <CompareCard
                        key={item.id}
                        item={item}
                        mode={mode}
                        inProgressVersions={inProgressVersions}
                        defaultExpanded={groupName === defaultOpenGroup && index === 0}
                      />
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      </div>
    </section>
  );
}
