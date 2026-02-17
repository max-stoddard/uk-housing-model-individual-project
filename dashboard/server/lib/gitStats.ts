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
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe']
    }).trim()
  );
  return Number.isFinite(value) ? value : 0;
}

function readGitString(repoRoot: string, args: string[]): string {
  return execFileSync('git', args, {
    cwd: repoRoot,
    encoding: 'utf-8',
    stdio: ['pipe', 'pipe', 'pipe']
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
    encoding: 'utf-8',
    stdio: ['pipe', 'pipe', 'pipe']
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

async function githubFetchDiff(url: string, token: string): Promise<Response> {
  return fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github.diff',
      'X-GitHub-Api-Version': '2022-11-28'
    }
  });
}

function parseDiffStats(diffText: string): { filesChanged: number; insertions: number; deletions: number } {
  let filesChanged = 0;
  let insertions = 0;
  let deletions = 0;

  const lines = diffText.split('\n');
  for (const line of lines) {
    if (line.startsWith('diff --git a/')) {
      filesChanged++;
    } else if (line.startsWith('+') && !line.startsWith('+++')) {
      insertions++;
    } else if (line.startsWith('-') && !line.startsWith('---')) {
      deletions++;
    }
  }

  return { filesChanged, insertions, deletions };
}

async function getDiffStats(
  config: GitHubConfig,
  base: string,
  head: string
): Promise<{ filesChanged: number; insertions: number; deletions: number }> {
  const url = `https://api.github.com/repos/${config.repo}/compare/${base}...${head}`;
  const response = await githubFetchDiff(url, config.token);
  if (!response.ok) {
    throw new Error(`GitHub compare diff returned ${response.status}`);
  }
  const diffText = await response.text();
  return parseDiffStats(diffText);
}

async function getCompareCommitCount(
  config: GitHubConfig,
  base: string,
  head: string
): Promise<number> {
  const url = `https://api.github.com/repos/${config.repo}/compare/${base}...${head}`;
  const response = await githubFetch(url, config.token);
  if (!response.ok) {
    throw new Error(`GitHub compare API returned ${response.status}`);
  }
  const data = await response.json();
  return data.total_commits ?? data.ahead_by ?? 0;
}

async function getWeeklyCutoffCommit(
  config: GitHubConfig,
  sinceIso: string
): Promise<string> {
  const url = `https://api.github.com/repos/${config.repo}/commits?sha=${config.branch}&until=${sinceIso}&per_page=1`;
  const response = await githubFetch(url, config.token);
  if (!response.ok) {
    return EMPTY_TREE_HASH;
  }
  const commits: { sha: string }[] = await response.json();
  return commits.length > 0 ? commits[0].sha : EMPTY_TREE_HASH;
}

async function getGitHubStats(config: GitHubConfig, baseCommit: string): Promise<GitStatsPayload> {
  const sinceIso = getSinceIsoForWeeklyWindow();

  // Phase 1: total stats + weekly cutoff in parallel
  const [totalDiff, totalCommits, weeklyCutoff] = await Promise.all([
    getDiffStats(config, baseCommit, config.branch),
    getCompareCommitCount(config, baseCommit, config.branch),
    getWeeklyCutoffCommit(config, sinceIso)
  ]);

  // Phase 2: weekly stats (depends on cutoff SHA)
  const [weeklyDiff, weeklyCommits] = await Promise.all([
    getDiffStats(config, weeklyCutoff, config.branch),
    getCompareCommitCount(config, weeklyCutoff, config.branch)
  ]);

  return {
    baseCommit,
    filesChanged: totalDiff.filesChanged,
    insertions: totalDiff.insertions,
    deletions: totalDiff.deletions,
    lineChanges: totalDiff.insertions + totalDiff.deletions,
    commitCount: totalCommits,
    weekly: {
      filesChanged: weeklyDiff.filesChanged,
      lineChanges: weeklyDiff.insertions + weeklyDiff.deletions,
      commitCount: weeklyCommits
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
    console.log('[git-stats] using cached result');
    return cached;
  }

  // 2. Try local git
  try {
    const local = getLocalGitStats(options.repoRoot, options.baseCommit);
    writeCache(options.baseCommit, local);
    console.log('[git-stats] local git succeeded');
    return local;
  } catch (error) {
    console.log(`[git-stats] local git failed: ${(error as Error).message}`);
  }

  // 3. Try GitHub API
  if (!options.github) {
    console.log('[git-stats] GitHub API fallback not configured, skipping');
  }
  if (options.github) {
    try {
      const remote = await getGitHubStats(options.github, options.baseCommit);
      writeCache(options.baseCommit, remote);
      console.log('[git-stats] GitHub API succeeded');
      return remote;
    } catch (error) {
      console.warn(`[git-stats] GitHub API fallback failed: ${(error as Error).message}`);
    }
  }

  // 4. Return zeros
  console.log('[git-stats] returning zeros');
  return buildZeroGitStats(options.baseCommit);
}
