// Author: Max Stoddard
import { spawnSync } from 'node:child_process';

export interface RuntimeDependencyResult {
  available: boolean;
  versionOutput: string;
  error?: string;
}

export interface RuntimeDependencyStatus {
  java: RuntimeDependencyResult;
  maven: RuntimeDependencyResult;
  mavenBin: string;
}

function runVersionCheck(command: string, args: string[]): RuntimeDependencyResult {
  const result = spawnSync(command, args, { encoding: 'utf-8' });
  if (result.error) {
    return {
      available: false,
      versionOutput: '',
      error: result.error.message
    };
  }

  const combinedOutput = `${result.stdout ?? ''}\n${result.stderr ?? ''}`.trim();
  if (result.status !== 0) {
    return {
      available: false,
      versionOutput: combinedOutput,
      error: `Command exited with status ${result.status ?? 'unknown'}.`
    };
  }

  return {
    available: true,
    versionOutput: combinedOutput
  };
}

export function getConfiguredMavenBin(): string {
  return process.env.DASHBOARD_MAVEN_BIN?.trim() || 'mvn';
}

export function checkRuntimeDependencies(mavenBin = getConfiguredMavenBin()): RuntimeDependencyStatus {
  return {
    java: runVersionCheck('java', ['-version']),
    maven: runVersionCheck(mavenBin, ['-v']),
    mavenBin
  };
}
