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
}

const WEEK_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;
const EMPTY_TREE_HASH = '4b825dc642cb6eb9a060e54bf8d69288fbee4904';

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

export async function getGitStats(options: GitStatsOptions): Promise<GitStatsPayload> {
  return getLocalGitStats(options.repoRoot, options.baseCommit);
}
