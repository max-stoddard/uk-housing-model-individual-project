import { execFileSync } from 'node:child_process';

interface WeeklyGitStats {
  filesChanged: number;
  lineChanges: number;
  commitCount: number;
}

export interface GitStatsPayload {
  baseCommit: string;
  filesChanged: number;
  insertions: number;
  deletions: number;
  lineChanges: number;
  commitCount: number;
  weekly: WeeklyGitStats;
}

interface GitStatsOptions {
  repoRoot: string;
  baseCommit: string;
  githubRepo?: string;
  githubBranch?: string;
  githubToken?: string;
}

interface GitHubCommitFile {
  filename?: string;
  additions?: number;
  deletions?: number;
}

interface GitHubCommitListItem {
  sha?: string;
}

interface GitHubCommitDetail {
  files?: GitHubCommitFile[];
  stats?: {
    additions?: number;
    deletions?: number;
  };
}

interface GitHubAggregatedStats {
  filesChanged: number;
  insertions: number;
  deletions: number;
  lineChanges: number;
  commitCount: number;
}

interface CachedGitHubStats {
  expiresAt: number;
  value: GitStatsPayload;
}

const GITHUB_CACHE_TTL_MS = 5 * 60 * 1000;
const WEEK_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;
const GITHUB_COMMITS_PER_PAGE = 100;
const GITHUB_MAX_PAGES = 200;
const GITHUB_DETAIL_CONCURRENCY = 10;
const EMPTY_TREE_HASH = '4b825dc642cb6eb9a060e54bf8d69288fbee4904';
const githubStatsCache = new Map<string, CachedGitHubStats>();

function asErrorMessage(value: unknown): string {
  if (value instanceof Error) {
    return value.message;
  }
  return String(value);
}

export function buildZeroGitStats(baseCommit: string): GitStatsPayload {
  return {
    baseCommit,
    filesChanged: 0,
    insertions: 0,
    deletions: 0,
    lineChanges: 0,
    commitCount: 0,
    weekly: {
      filesChanged: 0,
      lineChanges: 0,
      commitCount: 0
    }
  };
}

function parseShortStatLine(output: string) {
  const files = Number(output.match(/(\d+)\s+files?\s+changed/)?.[1] ?? 0);
  const insertions = Number(output.match(/(\d+)\s+insertions?\(\+\)/)?.[1] ?? 0);
  const deletions = Number(output.match(/(\d+)\s+deletions?\(-\)/)?.[1] ?? 0);
  return {
    filesChanged: files,
    insertions,
    deletions,
    lineChanges: insertions + deletions
  };
}

function getSinceIsoForWeeklyWindow(): string {
  return new Date(Date.now() - WEEK_WINDOW_MS).toISOString();
}

function readGitNumber(repoRoot: string, args: string[]): number {
  const value = Number(
    execFileSync('git', args, {
      cwd: repoRoot,
      encoding: 'utf-8'
    }).trim()
  );
  return Number.isFinite(value) ? value : 0;
}

function readGitString(repoRoot: string, args: string[]): string {
  return execFileSync('git', args, {
    cwd: repoRoot,
    encoding: 'utf-8'
  }).trim();
}

function getLocalWeeklyStats(repoRoot: string, sinceIso: string): WeeklyGitStats {
  const cutoffCommit = readGitString(repoRoot, ['rev-list', '-1', `--before=${sinceIso}`, 'HEAD']);
  const weeklyDiffBase = cutoffCommit || EMPTY_TREE_HASH;
  const weeklyShortStat = readGitString(repoRoot, ['diff', '--shortstat', weeklyDiffBase, 'HEAD']);
  const weeklyStat = parseShortStatLine(weeklyShortStat);
  const weeklyCommitCount = readGitNumber(repoRoot, ['rev-list', '--count', `--since=${sinceIso}`, 'HEAD']);

  return {
    filesChanged: weeklyStat.filesChanged,
    lineChanges: weeklyStat.lineChanges,
    commitCount: weeklyCommitCount
  };
}

function getLocalGitStats(repoRoot: string, baseCommit: string): GitStatsPayload {
  const shortStat = execFileSync('git', ['diff', '--shortstat', baseCommit], {
    cwd: repoRoot,
    encoding: 'utf-8'
  }).trim();
  const commitCount = readGitNumber(repoRoot, ['rev-list', '--count', `${baseCommit}..HEAD`]);
  const sinceIso = getSinceIsoForWeeklyWindow();
  const weekly = getLocalWeeklyStats(repoRoot, sinceIso);

  return {
    baseCommit,
    ...parseShortStatLine(shortStat),
    commitCount: Number.isFinite(commitCount) ? commitCount : 0,
    weekly
  };
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function getMessageFromPayload(payload: unknown): string | null {
  if (!isObject(payload)) {
    return null;
  }
  const message = payload.message;
  if (typeof message !== 'string') {
    return null;
  }
  return message;
}

function parseGitHubRepo(repo: string): { owner: string; name: string } {
  const match = /^([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+)$/.exec(repo.trim());
  if (!match) {
    throw new Error(`Invalid GitHub repo slug: ${repo}`);
  }
  return {
    owner: match[1],
    name: match[2]
  };
}

async function fetchGitHubJson(
  url: string,
  headers: Record<string, string>,
  context: string
): Promise<unknown> {
  const response = await fetch(url, { headers });
  let payload: unknown = null;

  try {
    payload = (await response.json()) as unknown;
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const reason = getMessageFromPayload(payload) ?? `HTTP ${response.status}`;
    throw new Error(`${context} failed: ${reason}`);
  }

  return payload;
}

function sumFileInsertions(files: GitHubCommitFile[]): number {
  return files.reduce((total, file) => total + Number(file.additions ?? 0), 0);
}

function sumFileDeletions(files: GitHubCommitFile[]): number {
  return files.reduce((total, file) => total + Number(file.deletions ?? 0), 0);
}

function readInsertions(detail: GitHubCommitDetail): number {
  const fromStats = Number(detail.stats?.additions);
  if (Number.isFinite(fromStats)) {
    return fromStats;
  }
  const files = Array.isArray(detail.files) ? detail.files : [];
  return sumFileInsertions(files);
}

function readDeletions(detail: GitHubCommitDetail): number {
  const fromStats = Number(detail.stats?.deletions);
  if (Number.isFinite(fromStats)) {
    return fromStats;
  }
  const files = Array.isArray(detail.files) ? detail.files : [];
  return sumFileDeletions(files);
}

function aggregateGitHubCommitDetails(details: GitHubCommitDetail[]): GitHubAggregatedStats {
  const touchedFiles = new Set<string>();
  let insertions = 0;
  let deletions = 0;

  for (const detail of details) {
    insertions += readInsertions(detail);
    deletions += readDeletions(detail);

    const files = Array.isArray(detail.files) ? detail.files : [];
    for (const file of files) {
      if (typeof file.filename === 'string' && file.filename.length > 0) {
        touchedFiles.add(file.filename);
      }
    }
  }

  return {
    filesChanged: touchedFiles.size,
    insertions,
    deletions,
    lineChanges: insertions + deletions,
    commitCount: details.length
  };
}

async function listGitHubCommitShas(
  owner: string,
  name: string,
  githubBranch: string,
  headers: Record<string, string>,
  options: {
    stopBeforeSha?: string;
    sinceIso?: string;
  }
): Promise<string[]> {
  const commitShas: string[] = [];
  let page = 1;
  let stopReached = false;

  while (page <= GITHUB_MAX_PAGES) {
    const params = new URLSearchParams({
      sha: githubBranch,
      per_page: String(GITHUB_COMMITS_PER_PAGE),
      page: String(page)
    });

    if (options.sinceIso) {
      params.set('since', options.sinceIso);
    }

    const commitsUrl = `https://api.github.com/repos/${owner}/${name}/commits?${params.toString()}`;
    const payload = await fetchGitHubJson(commitsUrl, headers, `GitHub commits request (page ${page})`);
    const commits = (Array.isArray(payload) ? payload : []) as GitHubCommitListItem[];

    if (commits.length === 0) {
      break;
    }

    for (const commit of commits) {
      const sha = commit.sha;
      if (typeof sha !== 'string' || sha.length === 0) {
        continue;
      }
      if (options.stopBeforeSha && sha === options.stopBeforeSha) {
        stopReached = true;
        break;
      }
      commitShas.push(sha);
    }

    if (stopReached || commits.length < GITHUB_COMMITS_PER_PAGE) {
      break;
    }
    page += 1;
  }

  if (page > GITHUB_MAX_PAGES) {
    throw new Error(`GitHub commits pagination exceeded ${GITHUB_MAX_PAGES} pages`);
  }

  return commitShas;
}

async function getGitHubCommitDetail(
  owner: string,
  name: string,
  sha: string,
  headers: Record<string, string>,
  detailCache: Map<string, GitHubCommitDetail>
): Promise<GitHubCommitDetail> {
  const cached = detailCache.get(sha);
  if (cached) {
    return cached;
  }

  const detailUrl = `https://api.github.com/repos/${owner}/${name}/commits/${encodeURIComponent(sha)}`;
  const payload = await fetchGitHubJson(detailUrl, headers, `GitHub commit detail request (${sha})`);
  const detail = isObject(payload) ? (payload as GitHubCommitDetail) : {};
  detailCache.set(sha, detail);
  return detail;
}

async function getGitHubCommitDetails(
  owner: string,
  name: string,
  commitShas: string[],
  headers: Record<string, string>,
  detailCache: Map<string, GitHubCommitDetail>
): Promise<GitHubCommitDetail[]> {
  const details: GitHubCommitDetail[] = [];

  for (let index = 0; index < commitShas.length; index += GITHUB_DETAIL_CONCURRENCY) {
    const batch = commitShas.slice(index, index + GITHUB_DETAIL_CONCURRENCY);
    const batchDetails = await Promise.all(
      batch.map((sha) => getGitHubCommitDetail(owner, name, sha, headers, detailCache))
    );
    details.push(...batchDetails);
  }

  return details;
}

async function getGitHubWeeklyStats(
  owner: string,
  name: string,
  githubBranch: string,
  sinceIso: string,
  headers: Record<string, string>,
  detailCache: Map<string, GitHubCommitDetail>
): Promise<WeeklyGitStats> {
  const weeklyCommitShas = await listGitHubCommitShas(owner, name, githubBranch, headers, { sinceIso });
  if (weeklyCommitShas.length === 0) {
    return {
      filesChanged: 0,
      lineChanges: 0,
      commitCount: 0
    };
  }

  const weeklyDetails = await getGitHubCommitDetails(owner, name, weeklyCommitShas, headers, detailCache);
  const weeklyAggregate = aggregateGitHubCommitDetails(weeklyDetails);
  return {
    filesChanged: weeklyAggregate.filesChanged,
    lineChanges: weeklyAggregate.lineChanges,
    commitCount: weeklyAggregate.commitCount
  };
}

async function getGitHubCompareStats(
  baseCommit: string,
  githubRepo: string,
  githubBranch: string,
  githubToken: string
): Promise<GitStatsPayload> {
  const cacheKey = `${githubRepo}:${githubBranch}:${baseCommit}`;
  const cached = githubStatsCache.get(cacheKey);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.value;
  }

  const { owner, name } = parseGitHubRepo(githubRepo);
  const compareUrl = `https://api.github.com/repos/${owner}/${name}/compare/${encodeURIComponent(baseCommit)}...${encodeURIComponent(githubBranch)}`;
  const headers: Record<string, string> = {
    Accept: 'application/vnd.github+json',
    'User-Agent': 'uk-housing-market-abm-dashboard'
  };

  if (githubToken) {
    headers.Authorization = `Bearer ${githubToken}`;
  }

  await fetchGitHubJson(compareUrl, headers, 'GitHub compare request');

  const detailCache = new Map<string, GitHubCommitDetail>();
  const commitShas = await listGitHubCommitShas(owner, name, githubBranch, headers, {
    stopBeforeSha: baseCommit
  });
  const commitDetails = await getGitHubCommitDetails(owner, name, commitShas, headers, detailCache);
  const aggregate = aggregateGitHubCommitDetails(commitDetails);
  const weeklySinceIso = getSinceIsoForWeeklyWindow();
  let weekly: WeeklyGitStats;

  try {
    weekly = await getGitHubWeeklyStats(owner, name, githubBranch, weeklySinceIso, headers, detailCache);
  } catch {
    weekly = {
      filesChanged: 0,
      lineChanges: 0,
      commitCount: 0
    };
  }

  const stats: GitStatsPayload = {
    baseCommit,
    filesChanged: aggregate.filesChanged,
    insertions: aggregate.insertions,
    deletions: aggregate.deletions,
    lineChanges: aggregate.lineChanges,
    commitCount: aggregate.commitCount,
    weekly
  };

  githubStatsCache.set(cacheKey, {
    value: stats,
    expiresAt: Date.now() + GITHUB_CACHE_TTL_MS
  });

  return stats;
}

export async function getGitStats(options: GitStatsOptions): Promise<GitStatsPayload> {
  const githubRepo = options.githubRepo?.trim() || 'max-stoddard/UK-Housing-Market-ABM';
  const githubBranch = options.githubBranch?.trim() || 'master';
  const githubToken = options.githubToken?.trim() ?? '';

  try {
    return getLocalGitStats(options.repoRoot, options.baseCommit);
  } catch (localError) {
    try {
      return await getGitHubCompareStats(options.baseCommit, githubRepo, githubBranch, githubToken);
    } catch (githubError) {
      throw new Error(
        `Local git stats failed (${asErrorMessage(localError)}); GitHub fallback failed (${asErrorMessage(githubError)})`
      );
    }
  }
}
