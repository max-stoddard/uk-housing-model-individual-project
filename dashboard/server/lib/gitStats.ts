import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

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

export interface GitHubConfig {
  token: string;
  repo: string;
  branch: string;
}

interface GitStatsOptions {
  repoRoot: string;
  baseCommit: string;
  github?: GitHubConfig;
}

const WEEK_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;
const EMPTY_TREE_HASH = '4b825dc642cb6eb9a060e54bf8d69288fbee4904';
const CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour
const CACHE_FILE_NAME = 'dashboard-git-stats-cache.json';
const GITHUB_RETRY_DELAY_MS = 1500;
const GITHUB_MAX_RETRIES = 3;

interface CacheEntry {
  timestamp: number;
  baseCommit: string;
  payload: GitStatsPayload;
}

let memoryCache: CacheEntry | null = null;

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

// ---------------------------------------------------------------------------
// Disk cache
// ---------------------------------------------------------------------------

function getCacheFilePath(): string {
  return path.join(os.tmpdir(), CACHE_FILE_NAME);
}

function readDiskCache(baseCommit: string): GitStatsPayload | null {
  try {
    const raw = fs.readFileSync(getCacheFilePath(), 'utf-8');
    const entry: CacheEntry = JSON.parse(raw);
    if (entry.baseCommit === baseCommit && Date.now() - entry.timestamp < CACHE_TTL_MS) {
      return entry.payload;
    }
  } catch {
    // cache miss or corrupt file -ignore
  }
  return null;
}

function writeDiskCache(baseCommit: string, payload: GitStatsPayload): void {
  const entry: CacheEntry = { timestamp: Date.now(), baseCommit, payload };
  try {
    fs.writeFileSync(getCacheFilePath(), JSON.stringify(entry), 'utf-8');
  } catch {
    // non-critical -ignore write failures
  }
}

function readCache(baseCommit: string): GitStatsPayload | null {
  if (memoryCache && memoryCache.baseCommit === baseCommit && Date.now() - memoryCache.timestamp < CACHE_TTL_MS) {
    return memoryCache.payload;
  }
  const diskResult = readDiskCache(baseCommit);
  if (diskResult) {
    memoryCache = { timestamp: Date.now(), baseCommit, payload: diskResult };
  }
  return diskResult;
}

function writeCache(baseCommit: string, payload: GitStatsPayload): void {
  memoryCache = { timestamp: Date.now(), baseCommit, payload };
  writeDiskCache(baseCommit, payload);
}

// ---------------------------------------------------------------------------
// GitHub API helpers
// ---------------------------------------------------------------------------

async function githubFetch(url: string, token: string): Promise<Response> {
  return fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    }
  });
}

async function fetchWithRetry(url: string, token: string): Promise<Response> {
  for (let attempt = 0; attempt < GITHUB_MAX_RETRIES; attempt++) {
    const response = await githubFetch(url, token);
    if (response.status === 202) {
      // GitHub is still computing stats -wait and retry
      await new Promise((resolve) => setTimeout(resolve, GITHUB_RETRY_DELAY_MS));
      continue;
    }
    return response;
  }
  // Return the last response even if still 202
  return githubFetch(url, token);
}

interface ContributorWeek {
  w: number; // unix timestamp (seconds)
  a: number; // additions
  d: number; // deletions
  c: number; // commits
}

interface ContributorEntry {
  weeks: ContributorWeek[];
}

async function getContributorStats(
  config: GitHubConfig,
  baseCommitDateIso: string,
  sinceIso: string
): Promise<{ total: { insertions: number; deletions: number; lineChanges: number; commitCount: number }; weekly: { lineChanges: number; commitCount: number } }> {
  const url = `https://api.github.com/repos/${config.repo}/stats/contributors`;
  const response = await fetchWithRetry(url, config.token);
  if (!response.ok) {
    throw new Error(`GitHub contributors API returned ${response.status}`);
  }

  const contributors: ContributorEntry[] = await response.json();
  const baseDate = new Date(baseCommitDateIso).getTime() / 1000;
  const sinceDate = new Date(sinceIso).getTime() / 1000;

  let totalInsertions = 0;
  let totalDeletions = 0;
  let totalCommits = 0;
  let weeklyLineChanges = 0;
  let weeklyCommits = 0;

  for (const contributor of contributors) {
    for (const week of contributor.weeks) {
      if (week.w >= baseDate) {
        totalInsertions += week.a;
        totalDeletions += week.d;
        totalCommits += week.c;
      }
      if (week.w >= sinceDate) {
        weeklyLineChanges += week.a + week.d;
        weeklyCommits += week.c;
      }
    }
  }

  return {
    total: {
      insertions: totalInsertions,
      deletions: totalDeletions,
      lineChanges: totalInsertions + totalDeletions,
      commitCount: totalCommits
    },
    weekly: {
      lineChanges: weeklyLineChanges,
      commitCount: weeklyCommits
    }
  };
}

async function getFilesChangedViaCompare(
  config: GitHubConfig,
  base: string,
  head: string
): Promise<number> {
  const uniqueFiles = new Set<string>();
  let page = 1;

  while (true) {
    const url = `https://api.github.com/repos/${config.repo}/compare/${base}...${head}?per_page=100&page=${page}`;
    const response = await githubFetch(url, config.token);
    if (!response.ok) {
      throw new Error(`GitHub compare API returned ${response.status}`);
    }
    const data = await response.json();
    const files: { filename: string }[] = data.files ?? [];
    for (const file of files) {
      uniqueFiles.add(file.filename);
    }
    if (files.length < 100) {
      break;
    }
    page++;
  }

  return uniqueFiles.size;
}

async function getWeeklyFilesChanged(
  config: GitHubConfig,
  sinceIso: string
): Promise<number> {
  // Find the commit closest to the weekly cutoff
  const commitsUrl = `https://api.github.com/repos/${config.repo}/commits?sha=${config.branch}&until=${sinceIso}&per_page=1`;
  const commitsResponse = await githubFetch(commitsUrl, config.token);
  if (!commitsResponse.ok) {
    return 0;
  }
  const commits: { sha: string }[] = await commitsResponse.json();
  if (commits.length === 0) {
    // All commits are within the weekly window -compare against empty tree
    return getFilesChangedViaCompare(config, EMPTY_TREE_HASH, config.branch);
  }
  return getFilesChangedViaCompare(config, commits[0].sha, config.branch);
}

async function getBaseCommitDate(config: GitHubConfig, baseCommit: string): Promise<string> {
  const url = `https://api.github.com/repos/${config.repo}/commits/${baseCommit}`;
  const response = await githubFetch(url, config.token);
  if (!response.ok) {
    throw new Error(`GitHub commit API returned ${response.status}`);
  }
  const data = await response.json();
  return data.commit?.committer?.date ?? data.commit?.author?.date ?? new Date(0).toISOString();
}

async function getGitHubStats(config: GitHubConfig, baseCommit: string): Promise<GitStatsPayload> {
  const sinceIso = getSinceIsoForWeeklyWindow();
  const baseCommitDate = await getBaseCommitDate(config, baseCommit);

  const [contributorData, totalFiles, weeklyFiles] = await Promise.all([
    getContributorStats(config, baseCommitDate, sinceIso),
    getFilesChangedViaCompare(config, baseCommit, config.branch),
    getWeeklyFilesChanged(config, sinceIso)
  ]);

  return {
    baseCommit,
    filesChanged: totalFiles,
    insertions: contributorData.total.insertions,
    deletions: contributorData.total.deletions,
    lineChanges: contributorData.total.lineChanges,
    commitCount: contributorData.total.commitCount,
    weekly: {
      filesChanged: weeklyFiles,
      lineChanges: contributorData.weekly.lineChanges,
      commitCount: contributorData.weekly.commitCount
    }
  };
}

// ---------------------------------------------------------------------------
// Main entry point: cache -> local git -> GitHub API -> zeros
// ---------------------------------------------------------------------------

export async function getGitStats(options: GitStatsOptions): Promise<GitStatsPayload> {
  // 1. Check cache
  const cached = readCache(options.baseCommit);
  if (cached) {
    return cached;
  }

  // 2. Try local git
  try {
    const local = getLocalGitStats(options.repoRoot, options.baseCommit);
    writeCache(options.baseCommit, local);
    return local;
  } catch {
    // local git unavailable (e.g. deployed on Render with no repo)
  }

  // 3. Try GitHub API
  if (options.github) {
    try {
      const remote = await getGitHubStats(options.github, options.baseCommit);
      writeCache(options.baseCommit, remote);
      return remote;
    } catch (error) {
      console.warn(`[git-stats] GitHub API fallback failed: ${(error as Error).message}`);
    }
  }

  // 4. Return zeros
  return buildZeroGitStats(options.baseCommit);
}
