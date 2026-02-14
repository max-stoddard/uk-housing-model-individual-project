import fs from 'node:fs';
import path from 'node:path';

export function parseVersionParts(version: string): number[] {
  return version
    .replace(/^v/i, '')
    .split('.')
    .map((part) => Number.parseInt(part, 10));
}

export function compareVersions(a: string, b: string): number {
  const ap = parseVersionParts(a);
  const bp = parseVersionParts(b);
  const maxLen = Math.max(ap.length, bp.length);

  for (let i = 0; i < maxLen; i += 1) {
    const av = ap[i] ?? 0;
    const bv = bp[i] ?? 0;
    if (av !== bv) {
      return av - bv;
    }
  }

  if (ap.length !== bp.length) {
    return ap.length - bp.length;
  }

  return a.localeCompare(b);
}

export function listVersions(inputDataDir: string): string[] {
  return fs
    .readdirSync(inputDataDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .filter((name) => /^v\d+(?:\.\d+)*$/.test(name))
    .filter((name) => name !== 'v1')
    .sort(compareVersions)
    .filter((name) => fs.existsSync(path.join(inputDataDir, name, 'config.properties')));
}
