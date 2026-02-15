import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { getGitStats } from '../server/lib/gitStats.js';
import { compareParameters, getParameterCatalog, getVersions } from '../server/lib/service.js';
import { getConfigPath, parseConfigFile, readNumericCsvRows, resolveConfigDataFilePath } from '../server/lib/io.js';
import { loadVersionNotes } from '../server/lib/versionNotes.js';
import { assertAxisSpecComplete, getAxisSpec } from '../src/lib/chartAxes.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '../..');

function sum(values: number[]): number {
  return values.reduce((total, value) => total + value, 0);
}

function assertClose(actual: number, expected: number, tolerance: number, message: string): void {
  assert.ok(Math.abs(actual - expected) <= tolerance, `${message}: expected ${expected}, got ${actual}`);
}

const expectedIds = [
  'income_given_age_joint',
  'wealth_given_income_joint',
  'btl_probability_bins',
  'age_distribution',
  'national_insurance_rates',
  'income_tax_rates',
  'government_allowance_support',
  'house_price_lognormal',
  'rental_price_lognormal',
  'desired_rent_power',
  'btl_strategy_split',
  'mortgage_duration_years',
  'downpayment_ftb_lognormal',
  'downpayment_oo_lognormal',
  'market_average_price_decay',
  'buy_quad'
];

const catalog = getParameterCatalog();
assert.deepEqual(
  catalog.map((item) => item.id),
  expectedIds,
  'Catalog should contain exactly the changed parameter cards tracked in version notes'
);

assertAxisSpecComplete(expectedIds);
for (const id of expectedIds) {
  const spec = getAxisSpec(id);
  const labels = [
    spec.scalar.xTitle,
    spec.scalar.yTitle,
    spec.binned.xTitle,
    spec.binned.yTitle,
    spec.binned.yDeltaTitle,
    spec.joint.xTitle,
    spec.joint.yTitle,
    spec.joint.legendTitle,
    spec.curve.xTitle,
    spec.curve.yTitle,
    spec.buyBudget.xTitle,
    spec.buyBudget.yTitle,
    spec.buyMultiplier.xTitle,
    spec.buyMultiplier.yTitle
  ];
  for (const label of labels) {
    assert.ok(/\(.+\)/.test(label), `Axis label should include unit marker: ${id} -> ${label}`);
    assert.ok(!label.toLowerCase().includes('native units'), `Axis label should not use native units placeholder: ${id}`);
  }
}

const versions = getVersions(repoRoot);
assert.ok(versions.length > 0, 'Expected at least one version folder');
assert.ok(!versions.includes('v1'), 'v1 should be excluded after cleanup');
assert.equal(versions[0], 'v0', 'Oldest version should be v0');

const notes = loadVersionNotes(repoRoot);
assert.ok(notes.length > 0, 'Expected at least one version note entry');
for (const entry of notes) {
  assert.ok(Array.isArray(entry.calibration_files), 'calibration_files should be present for every version entry');
  assert.ok(Array.isArray(entry.config_parameters), 'config_parameters should be present for every version entry');
  assert.ok(Array.isArray(entry.method_variations), 'method_variations should be present for every version entry');
}
const v38Note = notes.find((entry) => entry.version_id === 'v3.8');
assert.ok(v38Note, 'Expected v3.8 note entry');
assert.equal(v38Note?.validation.status, 'in_progress', 'v3.8 validation should remain in_progress');
assert.equal(v38Note?.validation.income_diff_pct, null, 'v3.8 income diff should be null while in progress');
assert.equal(v38Note?.validation.housing_wealth_diff_pct, null, 'v3.8 housing diff should be null while in progress');
assert.equal(v38Note?.validation.financial_wealth_diff_pct, null, 'v3.8 financial diff should be null while in progress');

const rangeAtSameVersion = compareParameters(repoRoot, 'v3.8', 'v3.8', ['national_insurance_rates'], 'range');
const throughRightAtSameVersion = compareParameters(repoRoot, 'v3.8', 'v3.8', ['national_insurance_rates'], 'through_right');
assert.equal(
  rangeAtSameVersion.items[0]?.changeOriginsInRange.length ?? 0,
  0,
  'range provenance scope should be empty when left and right are the same version'
);
assert.ok(
  (throughRightAtSameVersion.items[0]?.changeOriginsInRange.length ?? 0) > 0,
  'through_right provenance scope should include historical updates through the selected version'
);
assert.ok(
  throughRightAtSameVersion.items[0]?.changeOriginsInRange.some((origin) => origin.versionId === 'v2.0'),
  'through_right provenance should include NI update origin v2.0'
);

const singleBuyQuad = compareParameters(repoRoot, 'v3.8', 'v3.8', ['buy_quad'], 'through_right').items[0];
const buyQuadV38Origin = singleBuyQuad?.changeOriginsInRange.find((origin) => origin.versionId === 'v3.8');
assert.ok(buyQuadV38Origin, 'Expected buy_quad provenance to include v3.8 origin in through_right scope');
assert.ok(
  (buyQuadV38Origin?.methodVariations.length ?? 0) > 0,
  'Expected buy_quad v3.8 provenance to include method variation notes'
);
assert.ok(
  buyQuadV38Origin?.methodVariations.some((variation) =>
    variation.configParameters.some((parameter) => parameter.startsWith('BUY_'))
  ),
  'Expected at least one method variation scoped to BUY_* parameters'
);

const compare = compareParameters(repoRoot, 'v0', versions[versions.length - 1], [
  'mortgage_duration_years',
  'house_price_lognormal',
  'desired_rent_power',
  'buy_quad',
  'income_given_age_joint',
  'national_insurance_rates',
  'income_tax_rates',
  'wealth_given_income_joint',
  'age_distribution'
]);

assert.equal(compare.left, 'v0');
assert.equal(compare.items.length, 9);

const formatSet = new Set(compare.items.map((item) => item.format));
assert.ok(formatSet.has('scalar'));
assert.ok(formatSet.has('lognormal_pair'));
assert.ok(formatSet.has('power_law_pair'));
assert.ok(formatSet.has('buy_quad'));
assert.ok(formatSet.has('joint_distribution'));
assert.ok(formatSet.has('binned_distribution'));

for (const item of compare.items) {
  assert.equal(item.leftVersion, 'v0');
  assert.ok(item.sourceInfo.configPathLeft.endsWith('config.properties'));
  assert.ok(item.sourceInfo.configPathRight.endsWith('config.properties'));
  assert.ok(Array.isArray(item.changeOriginsInRange), 'changeOriginsInRange should be present on every compare item');
}

const ageDist = compare.items.find((item) => item.id === 'age_distribution');
assert.ok(ageDist && ageDist.visualPayload.type === 'binned_distribution');
if (ageDist && ageDist.visualPayload.type === 'binned_distribution') {
  const labels = ageDist.visualPayload.bins.map((bin) => bin.label);
  assert.ok(labels.includes('75-85'), 'Expected split age band 75-85');
  assert.ok(labels.includes('85-95'), 'Expected split age band 85-95');
  assert.ok(!labels.includes('75-95'), 'Shared age grid should not include unsplit 75-95 band');

  const leftConfig = parseConfigFile(getConfigPath(repoRoot, 'v0'));
  const rightConfig = parseConfigFile(getConfigPath(repoRoot, 'v3.8'));
  const leftRows = readNumericCsvRows(
    resolveConfigDataFilePath(repoRoot, 'v0', leftConfig.get('DATA_AGE_DISTRIBUTION') ?? '')
  );
  const rightRows = readNumericCsvRows(
    resolveConfigDataFilePath(repoRoot, 'v3.8', rightConfig.get('DATA_AGE_DISTRIBUTION') ?? '')
  );

  const rawLeftMass = sum(leftRows.map((row) => row[2]));
  const rawRightMass = sum(rightRows.map((row) => row[2]));
  const rebinnedLeftMass = sum(ageDist.visualPayload.bins.map((bin) => bin.left));
  const rebinnedRightMass = sum(ageDist.visualPayload.bins.map((bin) => bin.right));

  assertClose(rebinnedLeftMass, rawLeftMass, 1e-8, '1D rebin should preserve left mass');
  assertClose(rebinnedRightMass, rawRightMass, 1e-8, '1D rebin should preserve right mass');
}

const incomeAge = compare.items.find((item) => item.id === 'income_given_age_joint');
assert.ok(incomeAge && incomeAge.visualPayload.type === 'joint_distribution');
if (incomeAge && incomeAge.visualPayload.type === 'joint_distribution') {
  const xLabels = incomeAge.visualPayload.matrix.xAxis.labels;
  assert.ok(xLabels.includes('75-85'), 'Expected shared age x-bin 75-85');
  assert.ok(xLabels.includes('85-95'), 'Expected shared age x-bin 85-95');
  assert.ok(!xLabels.includes('75-95'), 'Expected no merged 75-95 x-bin in shared grid');

  const leftConfig = parseConfigFile(getConfigPath(repoRoot, 'v0'));
  const rightConfig = parseConfigFile(getConfigPath(repoRoot, 'v3.8'));
  const leftRows = readNumericCsvRows(
    resolveConfigDataFilePath(repoRoot, 'v0', leftConfig.get('DATA_INCOME_GIVEN_AGE') ?? '')
  );
  const rightRows = readNumericCsvRows(
    resolveConfigDataFilePath(repoRoot, 'v3.8', rightConfig.get('DATA_INCOME_GIVEN_AGE') ?? '')
  );

  const rawLeftMass = sum(leftRows.map((row) => row[4]));
  const rawRightMass = sum(rightRows.map((row) => row[4]));
  const rebinnedLeftMass = sum(incomeAge.visualPayload.matrix.left.map((cell) => cell.value));
  const rebinnedRightMass = sum(incomeAge.visualPayload.matrix.right.map((cell) => cell.value));

  assertClose(rebinnedLeftMass, rawLeftMass, 1e-7, '2D rebin should preserve left mass');
  assertClose(rebinnedRightMass, rawRightMass, 1e-7, '2D rebin should preserve right mass');
}

const wealthIncome = compare.items.find((item) => item.id === 'wealth_given_income_joint');
assert.ok(wealthIncome && wealthIncome.visualPayload.type === 'joint_distribution');
if (wealthIncome && wealthIncome.visualPayload.type === 'joint_distribution') {
  assert.ok(
    wealthIncome.visualPayload.matrix.xAxis.labels.some((label) => label.includes('£')),
    'Expected clean level-space labels on wealth/income x axis'
  );
  assert.ok(
    wealthIncome.visualPayload.matrix.yAxis.labels.some((label) => label.includes('£')),
    'Expected clean level-space labels on wealth/income y axis'
  );
}

const niRates = compare.items.find((item) => item.id === 'national_insurance_rates');
assert.ok(niRates && niRates.visualPayload.type === 'binned_distribution', 'Expected NI rates card in compare payload');
if (niRates && niRates.visualPayload.type === 'binned_distribution') {
  assert.equal(niRates.unchanged, false, 'NI thresholds/rates should be changed between v0 and v3.8');
  assert.ok(
    niRates.visualPayload.bins.some((bin) => Math.abs(bin.delta) > 1e-12),
    'At least one NI step-rate bracket should have non-zero delta'
  );
  assert.ok(
    niRates.changeOriginsInRange.some((origin) => origin.versionId === 'v2.0'),
    'NI card provenance should include v2.0'
  );
}

const buyQuad = compare.items.find((item) => item.id === 'buy_quad');
assert.ok(buyQuad, 'Expected buy_quad card');
assert.ok(
  buyQuad?.changeOriginsInRange.some((origin) => origin.versionId === 'v3.8' && origin.validationStatus === 'in_progress'),
  'buy_quad provenance should include v3.8 as in_progress'
);

type MockFetchResult = { payload: unknown; status?: number } | null;
type MockFetchHandler = (url: URL) => MockFetchResult;

function asJsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      'content-type': 'application/json'
    }
  });
}

async function runWithMockFetch(handler: MockFetchHandler, run: () => Promise<void>): Promise<void> {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const requestUrl =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    const parsedUrl = new URL(requestUrl);
    const mocked = handler(parsedUrl);
    if (mocked) {
      return asJsonResponse(mocked.payload, mocked.status ?? 200);
    }
    return asJsonResponse({ message: `Unhandled mock URL: ${parsedUrl.toString()}` }, 404);
  }) as typeof fetch;

  try {
    await run();
  } finally {
    globalThis.fetch = originalFetch;
  }
}

function makeFiles(start: number, end: number): Array<{ filename: string; additions: number; deletions: number }> {
  return Array.from({ length: end - start }, (_, offset) => {
    const index = start + offset;
    return {
      filename: `file-${index}.txt`,
      additions: 1,
      deletions: 0
    };
  });
}

async function assertGitStatsFallbackAggregation(): Promise<void> {
  await runWithMockFetch((url) => {
    if (url.pathname === '/repos/example/repo/compare/base-sha...master') {
      return {
        payload: { total_commits: 3, files: [] }
      };
    }

    if (url.pathname === '/repos/example/repo/commits') {
      const page = url.searchParams.get('page');
      const since = url.searchParams.get('since');
      if (page !== '1') {
        return { payload: [] };
      }
      if (since) {
        return { payload: [{ sha: 'c3' }, { sha: 'c2' }] };
      }
      return {
        payload: [{ sha: 'c3' }, { sha: 'c2' }, { sha: 'c1' }, { sha: 'base-sha' }]
      };
    }

    if (url.pathname === '/repos/example/repo/commits/c3') {
      return {
        payload: {
          stats: { additions: 10, deletions: 1 },
          files: [
            { filename: 'a.ts', additions: 6, deletions: 1 },
            { filename: 'b.ts', additions: 4, deletions: 0 }
          ]
        }
      };
    }

    if (url.pathname === '/repos/example/repo/commits/c2') {
      return {
        payload: {
          stats: { additions: 5, deletions: 2 },
          files: [
            { filename: 'b.ts', additions: 2, deletions: 1 },
            { filename: 'c.ts', additions: 3, deletions: 1 }
          ]
        }
      };
    }

    if (url.pathname === '/repos/example/repo/commits/c1') {
      return {
        payload: {
          stats: { additions: 1, deletions: 3 },
          files: [{ filename: 'd.ts', additions: 1, deletions: 3 }]
        }
      };
    }

    return null;
  }, async () => {
    const stats = await getGitStats({
      repoRoot: path.resolve(repoRoot, '__missing_repo_for_git_stats__'),
      baseCommit: 'base-sha',
      githubRepo: 'example/repo',
      githubBranch: 'master',
      githubToken: 'token'
    });

    assert.equal(stats.filesChanged, 4, 'Fallback filesChanged should count unique files across commit details');
    assert.equal(stats.insertions, 16, 'Fallback insertions should aggregate commit additions');
    assert.equal(stats.deletions, 6, 'Fallback deletions should aggregate commit deletions');
    assert.equal(stats.lineChanges, 22, 'Fallback lineChanges should equal insertions + deletions');
    assert.equal(stats.commitCount, 3, 'Fallback commitCount should equal traversed commit range');

    assert.equal(stats.weekly.filesChanged, 3, 'Weekly filesChanged should count unique files in weekly commit range');
    assert.equal(stats.weekly.lineChanges, 18, 'Weekly lineChanges should aggregate weekly additions + deletions');
    assert.equal(stats.weekly.commitCount, 2, 'Weekly commitCount should reflect weekly commit range');
  });
}

async function assertGitStatsFallbackAvoids300CapArtifact(): Promise<void> {
  await runWithMockFetch((url) => {
    if (url.pathname === '/repos/example/cap-repo/compare/base-cap...master') {
      return {
        payload: { total_commits: 2, files: [] }
      };
    }

    if (url.pathname === '/repos/example/cap-repo/commits') {
      const page = url.searchParams.get('page');
      const since = url.searchParams.get('since');
      if (page !== '1') {
        return { payload: [] };
      }
      if (since) {
        return { payload: [{ sha: 'd2' }] };
      }
      return {
        payload: [{ sha: 'd2' }, { sha: 'd1' }, { sha: 'base-cap' }]
      };
    }

    if (url.pathname === '/repos/example/cap-repo/commits/d2') {
      return {
        payload: {
          stats: { additions: 220, deletions: 20 },
          files: makeFiles(0, 220)
        }
      };
    }

    if (url.pathname === '/repos/example/cap-repo/commits/d1') {
      return {
        payload: {
          stats: { additions: 220, deletions: 40 },
          files: makeFiles(180, 400)
        }
      };
    }

    return null;
  }, async () => {
    const stats = await getGitStats({
      repoRoot: path.resolve(repoRoot, '__missing_repo_for_git_stats_cap__'),
      baseCommit: 'base-cap',
      githubRepo: 'example/cap-repo',
      githubBranch: 'master',
      githubToken: 'token'
    });

    assert.equal(stats.filesChanged, 400, 'Fallback filesChanged should not be capped at 300');
    assert.ok(stats.filesChanged > 300, 'Fallback filesChanged should exceed GitHub compare file cap when data supports it');
    assert.equal(stats.commitCount, 2, 'Fallback commitCount should include both commits in range');
    assert.equal(stats.weekly.filesChanged, 220, 'Weekly filesChanged should reflect weekly commit details');
  });
}

await assertGitStatsFallbackAggregation();
await assertGitStatsFallbackAvoids300CapArtifact();

console.log('Smoke tests passed.');
