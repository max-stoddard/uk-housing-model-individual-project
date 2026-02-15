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

interface GitHubCompareFile {
  additions?: number;
  deletions?: number;
}

interface GitHubCompareResponse {
  total_commits?: number;
  files?: GitHubCompareFile[];
  message?: string;
}

interface GitHubCommitListItem {
  sha?: string;
}

interface GitHubCommitParent {
  sha?: string;
}

interface GitHubCommitDetail {
  files?: GitHubCompareFile[];
  parents?: GitHubCommitParent[];
}

interface CachedGitHubStats {
  expiresAt: number;
  value: GitStatsPayload;
}

const GITHUB_CACHE_TTL_MS = 5 * 60 * 1000;
const WEEK_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;
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

function computeLineChangesFromFiles(files: GitHubCompareFile[]): number {
  return files.reduce((total, file) => total + Number(file.additions ?? 0) + Number(file.deletions ?? 0), 0);
}

async function getGitHubWeeklyStats(
  owner: string,
  name: string,
  githubBranch: string,
  sinceIso: string,
  headers: Record<string, string>
): Promise<WeeklyGitStats> {
  const commitsSinceUrl =
    `https://api.github.com/repos/${owner}/${name}/commits` +
    `?sha=${encodeURIComponent(githubBranch)}` +
    `&since=${encodeURIComponent(sinceIso)}` +
    '&per_page=100';
  const commitsSincePayload = await fetchGitHubJson(commitsSinceUrl, headers, 'GitHub commits(since) request');
  const commitsSince = (Array.isArray(commitsSincePayload) ? commitsSincePayload : []) as GitHubCommitListItem[];
  const commitShas = commitsSince
    .map((entry) => entry.sha)
    .filter((sha): sha is string => typeof sha === 'string' && sha.length > 0);

  if (commitShas.length === 0) {
    return {
      filesChanged: 0,
      lineChanges: 0,
      commitCount: 0
    };
  }

  let weeklyBaseSha = '';
  try {
    const cutoffUrl =
      `https://api.github.com/repos/${owner}/${name}/commits` +
      `?sha=${encodeURIComponent(githubBranch)}` +
      `&until=${encodeURIComponent(sinceIso)}` +
      '&per_page=1';
    const cutoffPayload = await fetchGitHubJson(cutoffUrl, headers, 'GitHub commits(until) request');
    const cutoffCommits = (Array.isArray(cutoffPayload) ? cutoffPayload : []) as GitHubCommitListItem[];
    weeklyBaseSha = cutoffCommits[0]?.sha ?? '';
  } catch {
    weeklyBaseSha = '';
  }

  if (!weeklyBaseSha) {
    const oldestSha = commitShas[commitShas.length - 1];
    const oldestDetailUrl = `https://api.github.com/repos/${owner}/${name}/commits/${encodeURIComponent(oldestSha)}`;
    const oldestDetailPayload = await fetchGitHubJson(oldestDetailUrl, headers, 'GitHub oldest commit detail request');
    const oldestDetail = isObject(oldestDetailPayload) ? (oldestDetailPayload as GitHubCommitDetail) : {};
    const oldestParents = Array.isArray(oldestDetail.parents) ? oldestDetail.parents : [];
    const firstParentSha = oldestParents[0]?.sha ?? '';

    if (firstParentSha) {
      weeklyBaseSha = firstParentSha;
    } else {
      const oldestFiles = Array.isArray(oldestDetail.files) ? oldestDetail.files : [];
      return {
        filesChanged: oldestFiles.length,
        lineChanges: computeLineChangesFromFiles(oldestFiles),
        commitCount: commitShas.length
      };
    }
  }

  const weeklyCompareUrl =
    `https://api.github.com/repos/${owner}/${name}/compare/` +
    `${encodeURIComponent(weeklyBaseSha)}...${encodeURIComponent(githubBranch)}`;
  const weeklyComparePayload = await fetchGitHubJson(weeklyCompareUrl, headers, 'GitHub weekly compare request');
  const weeklyCompare = isObject(weeklyComparePayload) ? (weeklyComparePayload as GitHubCompareResponse) : {};
  const weeklyFiles = Array.isArray(weeklyCompare.files) ? weeklyCompare.files : [];

  return {
    filesChanged: weeklyFiles.length,
    lineChanges: computeLineChangesFromFiles(weeklyFiles),
    commitCount: commitShas.length
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

  const payload = await fetchGitHubJson(compareUrl, headers, 'GitHub compare request');

  const parsedCompare = isObject(payload) ? (payload as GitHubCompareResponse) : {};
  const files = Array.isArray(parsedCompare.files) ? parsedCompare.files : [];
  const insertions = files.reduce((total, file) => total + Number(file.additions ?? 0), 0);
  const deletions = files.reduce((total, file) => total + Number(file.deletions ?? 0), 0);
  const commitCount = Number(parsedCompare.total_commits ?? 0);
  const weeklySinceIso = getSinceIsoForWeeklyWindow();
  let weekly: WeeklyGitStats;

  try {
    weekly = await getGitHubWeeklyStats(owner, name, githubBranch, weeklySinceIso, headers);
  } catch {
    weekly = {
      filesChanged: 0,
      lineChanges: 0,
      commitCount: 0
    };
  }

  const stats: GitStatsPayload = {
    baseCommit,
    filesChanged: files.length,
    insertions,
    deletions,
    lineChanges: insertions + deletions,
    commitCount: Number.isFinite(commitCount) ? commitCount : 0,
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
