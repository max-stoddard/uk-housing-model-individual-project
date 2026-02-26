import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { PassThrough } from 'node:stream';
import { fileURLToPath } from 'node:url';
import {
  compareParameters,
  getInProgressVersions,
  getParameterCatalog,
  getValidationTrend,
  getVersions
} from '../server/lib/service.js';
import {
  deleteResultsRun,
  getResultsCompare,
  getResultsRunDetail,
  getResultsRunFiles,
  getResultsRuns,
  getResultsSeries
} from '../server/lib/results.js';
import {
  __resetModelRunManagerForTests,
  __setModelRunSpawnForTests,
  cancelModelRunJob,
  clearModelRunJob,
  getModelRunJobLogs,
  getModelRunOptions,
  getResultsStorageSummary,
  listModelRunJobs,
  submitModelRun
} from '../server/lib/modelRuns.js';
import { getConfigPath, parseConfigFile, readNumericCsvRows, resolveConfigDataFilePath } from '../server/lib/io.js';
import { createWriteAuthController, getWriteAuthConfigurationError, resolveDashboardWriteAccess } from '../server/lib/writeAuth.js';
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

function gaussianPercentDensity(percent: number, mu: number, sigma: number): number {
  const denominator = percent * sigma * Math.sqrt(2 * Math.PI);
  const exponent = -((Math.log(percent) - mu) ** 2) / (2 * sigma ** 2);
  return Math.exp(exponent) / denominator;
}

function waitForAsyncTick(ms = 0): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function writeSizedFile(filePath: string, sizeBytes: number): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, Buffer.alloc(sizeBytes, 0));
}

class FakeModelProcess extends EventEmitter {
  stdout = new PassThrough();
  stderr = new PassThrough();
  private rejectSigterm = false;

  kill(signal: NodeJS.Signals = 'SIGTERM'): boolean {
    if (signal === 'SIGTERM' && this.rejectSigterm) {
      return false;
    }
    setTimeout(() => {
      this.emit('close', signal === 'SIGTERM' ? null : 1, signal);
    }, 0);
    return true;
  }

  disableSigtermDelivery(): void {
    this.rejectSigterm = true;
  }

  emitStdout(line: string): void {
    this.stdout.write(`${line}\n`);
  }

  emitStderr(line: string): void {
    this.stderr.write(`${line}\n`);
  }

  succeed(): void {
    this.emit('close', 0, null);
  }

  fail(): void {
    this.emit('close', 1, null);
  }
}

const expectedIds = [
  'income_given_age_joint',
  'wealth_given_income_joint',
  'age_distribution',
  'uk_housing_stock_totals',
  'household_consumption_fractions',
  'btl_probability_bins',
  'national_insurance_rates',
  'income_tax_rates',
  'government_allowance_support',
  'house_price_lognormal',
  'rental_price_lognormal',
  'desired_rent_power',
  'hpa_expectation_params',
  'hold_period_years',
  'initial_sale_markup_distribution',
  'price_reduction_probabilities',
  'sale_reduction_gaussian',
  'tenancy_length_range',
  'initial_rent_markup_distribution',
  'rent_reduction_gaussian',
  'bidup_multiplier',
  'rent_gross_yield',
  'market_average_price_decay',
  'mortgage_duration_years',
  'downpayment_ftb_lognormal',
  'downpayment_oo_lognormal',
  'downpayment_btl_profile',
  'buy_quad',
  'bank_rate_credit_response',
  'bank_ltv_limits',
  'bank_lti_limits',
  'bank_affordability_icr_limits',
  'btl_strategy_split'
];

const newlyAddedIds = [
  'uk_housing_stock_totals',
  'household_consumption_fractions',
  'hpa_expectation_params',
  'hold_period_years',
  'initial_sale_markup_distribution',
  'price_reduction_probabilities',
  'sale_reduction_gaussian',
  'tenancy_length_range',
  'initial_rent_markup_distribution',
  'rent_reduction_gaussian',
  'bidup_multiplier',
  'rent_gross_yield',
  'downpayment_btl_profile',
  'bank_rate_credit_response',
  'bank_ltv_limits',
  'bank_lti_limits',
  'bank_affordability_icr_limits'
] as const;

const RESULTS_ROW_COUNT = 2001;

const RESULTS_CORE_FILE_NAMES = [
  'coreIndicator-ooLTV.csv',
  'coreIndicator-ooLTI.csv',
  'coreIndicator-btlLTV.csv',
  'coreIndicator-creditGrowth.csv',
  'coreIndicator-debtToIncome.csv',
  'coreIndicator-ooDebtToIncome.csv',
  'coreIndicator-mortgageApprovals.csv',
  'coreIndicator-housingTransactions.csv',
  'coreIndicator-advancesToFTB.csv',
  'coreIndicator-advancesToBTL.csv',
  'coreIndicator-advancesToHM.csv',
  'coreIndicator-housePriceGrowth.csv',
  'coreIndicator-priceToIncome.csv',
  'coreIndicator-rentalYield.csv',
  'coreIndicator-interestRateSpread.csv'
] as const;

const RESULTS_OUTPUT_COLUMNS = [
  'Model time',
  'nHomeless',
  'nRenting',
  'nOwnerOccupier',
  'nActiveBTL',
  'Sale HPI',
  'Sale AvSalePrice',
  'Sale AvMonthsOnMarket',
  'Rental HPI',
  'Rental AvSalePrice',
  'Rental AvMonthsOnMarket',
  'creditStock',
  'interestRate'
] as const;

interface ResultsFixtureRunIds {
  complete: string;
  emptyOutput: string;
  sparseCore: string;
  noConfig: string;
}

interface ResultsFixtureContext {
  root: string;
  runIds: ResultsFixtureRunIds;
}

interface ResultsFixtureRunOptions {
  runId: string;
  outputMode: 'full' | 'empty';
  includeConfig: boolean;
  includeTransactionFile: boolean;
  emptyCoreFiles?: Set<string>;
  modifiedAtMs: number;
}

function buildOutputCsv(rowCount: number): string {
  const lines = [RESULTS_OUTPUT_COLUMNS.join(';')];
  for (let modelTime = 0; modelTime < rowCount; modelTime += 1) {
    lines.push(
      [
        String(modelTime),
        String(90 + (modelTime % 13)),
        String(800 + modelTime),
        String(700 + (modelTime % 17)),
        String(120 + (modelTime % 7)),
        String(100 + (modelTime % 37)),
        String(220000 + modelTime * 25),
        (2 + (modelTime % 12) / 10).toFixed(2),
        String(95 + (modelTime % 31)),
        (1250 + modelTime * 0.45).toFixed(2),
        (1 + (modelTime % 8) / 10).toFixed(2),
        String(1_000_000 + modelTime * 1200),
        (0.01 + (modelTime % 24) / 10_000).toFixed(4)
      ].join(';')
    );
  }
  return `${lines.join('\n')}\n`;
}

function buildCoreCsv(seed: number, rowCount: number): string {
  const values: string[] = [];
  for (let index = 0; index < rowCount; index += 1) {
    values.push(String(seed + (index % 9) + index * 0.01));
  }
  return `${values.join(';')}\n`;
}

function writeResultsFixtureRun(resultsRoot: string, options: ResultsFixtureRunOptions): void {
  const runPath = path.join(resultsRoot, options.runId);
  fs.mkdirSync(runPath, { recursive: true });

  if (options.outputMode === 'full') {
    fs.writeFileSync(path.join(runPath, 'Output-run1.csv'), buildOutputCsv(RESULTS_ROW_COUNT), 'utf-8');
  } else {
    fs.writeFileSync(path.join(runPath, 'Output-run1.csv'), '', 'utf-8');
  }

  for (let index = 0; index < RESULTS_CORE_FILE_NAMES.length; index += 1) {
    const fileName = RESULTS_CORE_FILE_NAMES[index];
    const content =
      options.emptyCoreFiles?.has(fileName) === true ? '' : buildCoreCsv((index + 1) * 100, RESULTS_ROW_COUNT);
    fs.writeFileSync(path.join(runPath, fileName), content, 'utf-8');
  }

  if (options.includeConfig) {
    fs.writeFileSync(path.join(runPath, 'config.properties'), 'SEED=42\n', 'utf-8');
  }

  if (options.includeTransactionFile) {
    fs.writeFileSync(path.join(runPath, 'RentalTransactions-run1.csv'), 'modelTime;price\n0;1000\n', 'utf-8');
  }

  const modifiedAt = new Date(options.modifiedAtMs);
  fs.utimesSync(runPath, modifiedAt, modifiedAt);
}

function createResultsFixtureRepo(): ResultsFixtureContext {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'dashboard-results-smoke-'));
  const resultsRoot = path.join(root, 'Results');
  fs.mkdirSync(resultsRoot, { recursive: true });

  const runIds: ResultsFixtureRunIds = {
    complete: 'fixture-complete-output',
    emptyOutput: 'fixture-empty-output',
    sparseCore: 'fixture-sparse-core-output',
    noConfig: 'fixture-no-config-output'
  };

  const baseTime = Date.now();
  writeResultsFixtureRun(resultsRoot, {
    runId: runIds.complete,
    outputMode: 'full',
    includeConfig: true,
    includeTransactionFile: true,
    modifiedAtMs: baseTime + 4000
  });
  writeResultsFixtureRun(resultsRoot, {
    runId: runIds.noConfig,
    outputMode: 'full',
    includeConfig: false,
    includeTransactionFile: false,
    modifiedAtMs: baseTime + 3000
  });
  writeResultsFixtureRun(resultsRoot, {
    runId: runIds.emptyOutput,
    outputMode: 'empty',
    includeConfig: true,
    includeTransactionFile: false,
    modifiedAtMs: baseTime + 2000
  });
  writeResultsFixtureRun(resultsRoot, {
    runId: runIds.sparseCore,
    outputMode: 'full',
    includeConfig: true,
    includeTransactionFile: false,
    emptyCoreFiles: new Set(['coreIndicator-mortgageApprovals.csv']),
    modifiedAtMs: baseTime + 1000
  });

  return { root, runIds };
}

function buildModelRunConfigText(baseSeed: number): string {
  return `SEED = ${baseSeed}
N_STEPS = 2000
N_SIMS = 1
TARGET_POPULATION = 10000
TIME_TO_START_RECORDING_TRANSACTIONS = 1000
ROLLING_WINDOW_SIZE_FOR_CORE_INDICATORS = 6
CUMULATIVE_WEIGHT_BEYOND_YEAR = 0.25
recordTransactions = true
recordNBidUpFrequency = false
recordCoreIndicators = true
recordQualityBandPrice = false
recordHouseholdID = true
recordEmploymentIncome = true
recordRentalIncome = true
recordBankBalance = true
recordHousingWealth = true
recordNHousesOwned = true
recordAge = true
recordSavingRate = false
CENTRAL_BANK_INITIAL_BASE_RATE = 0.005
CENTRAL_BANK_LTV_HARD_MAX_FTB = 0.95
CENTRAL_BANK_LTV_HARD_MAX_HM = 0.9
CENTRAL_BANK_LTV_HARD_MAX_BTL = 0.8
CENTRAL_BANK_LTI_SOFT_MAX_FTB = 5.4
CENTRAL_BANK_LTI_SOFT_MAX_HM = 5.6
CENTRAL_BANK_LTI_MAX_FRAC_OVER_SOFT_MAX_FTB = 0.15
CENTRAL_BANK_LTI_MAX_FRAC_OVER_SOFT_MAX_HM = 0.15
CENTRAL_BANK_LTI_MONTHS_TO_CHECK = 12
CENTRAL_BANK_AFFORDABILITY_HARD_MAX = 0.4
CENTRAL_BANK_ICR_HARD_MIN = 1.2
DATA_AGE_DISTRIBUTION = "src/main/resources/Age.csv"
DATA_INCOME_GIVEN_AGE = "src/main/resources/Income.csv"
`;
}

function createModelRunFixtureRepo(): string {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'dashboard-model-runs-smoke-'));
  const inputDataRoot = path.join(root, 'input-data-versions');
  const resultsRoot = path.join(root, 'Results');
  fs.mkdirSync(inputDataRoot, { recursive: true });
  fs.mkdirSync(resultsRoot, { recursive: true });

  const baselines = ['v1.0', 'v1.1'];
  baselines.forEach((baseline, index) => {
    const baselinePath = path.join(inputDataRoot, baseline);
    fs.mkdirSync(baselinePath, { recursive: true });
    fs.writeFileSync(path.join(baselinePath, 'config.properties'), buildModelRunConfigText(index + 1), 'utf-8');
    fs.writeFileSync(path.join(baselinePath, 'Age.csv'), '0,10,0.1\n', 'utf-8');
    fs.writeFileSync(path.join(baselinePath, 'Income.csv'), '0,10,0.1\n', 'utf-8');
  });

  const versionNotes = {
    author: 'smoke-test',
    schema_version: 1,
    description: 'fixture',
    entries: [
      {
        version_id: 'v1.1',
        snapshot_folder: 'v1.1',
        validation_dataset: 'R8',
        description: 'fixture in-progress snapshot',
        updated_data_sources: [],
        calibration_files: [],
        config_parameters: [],
        parameter_changes: [],
        method_variations: [],
        validation: {
          status: 'in_progress',
          income_diff_pct: null,
          housing_wealth_diff_pct: null,
          financial_wealth_diff_pct: null
        }
      }
    ]
  };

  fs.writeFileSync(path.join(inputDataRoot, 'version-notes.json'), JSON.stringify(versionNotes, null, 2), 'utf-8');
  return root;
}

const catalog = getParameterCatalog();
assert.deepEqual(
  catalog.map((item) => item.id),
  expectedIds,
  'Catalog should contain exactly all tracked calibrated parameter cards'
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
const inProgressVersions = getInProgressVersions(repoRoot);
assert.ok(
  inProgressVersions.every((version) => versions.includes(version)),
  'In-progress versions should resolve to discovered snapshot folders'
);
assert.ok(!inProgressVersions.includes('v4.0'), 'Expected v4.0 to be reported as a stable snapshot');
const latestVersion = versions[versions.length - 1];

const notes = loadVersionNotes(repoRoot);
assert.ok(notes.length > 0, 'Expected at least one version note entry');
for (const entry of notes) {
  assert.ok(Array.isArray(entry.calibration_files), 'calibration_files should be present for every version entry');
  assert.ok(Array.isArray(entry.config_parameters), 'config_parameters should be present for every version entry');
  assert.ok(Array.isArray(entry.parameter_changes), 'parameter_changes should be present for every version entry');
  for (const parameterChange of entry.parameter_changes) {
    assert.equal(typeof parameterChange.config_parameter, 'string', 'parameter_changes.config_parameter should be a string');
    assert.ok(
      parameterChange.dataset_source === null || typeof parameterChange.dataset_source === 'string',
      'parameter_changes.dataset_source should be string or null'
    );
  }
  assert.ok(Array.isArray(entry.method_variations), 'method_variations should be present for every version entry');
}
const v10Note = notes.find((entry) => entry.version_id === 'v1.0');
assert.ok(v10Note, 'Expected v1.0 note entry');
assert.ok(
  v10Note?.parameter_changes.some(
    (change) =>
      change.config_parameter === 'DATA_INCOME_GIVEN_AGE' &&
      change.dataset_source === 'src/main/resources/AgeGrossIncomeJointDist.csv'
  ),
  'Expected v1.0 parameter_changes to include DATA_INCOME_GIVEN_AGE dataset source'
);
const v38Note = notes.find((entry) => entry.version_id === 'v4.0');
assert.ok(v38Note, 'Expected v4.0 note entry');
assert.equal(v38Note?.validation.status, 'complete', 'v4.0 validation should be complete');
assert.equal(v38Note?.validation.income_diff_pct, 7.87, 'v4.0 income diff should match released value');
assert.equal(v38Note?.validation.housing_wealth_diff_pct, 14.37, 'v4.0 housing diff should match released value');
assert.equal(v38Note?.validation.financial_wealth_diff_pct, 13.25, 'v4.0 financial diff should match released value');

const validationTrend = getValidationTrend(repoRoot);
assert.equal(validationTrend.dataset, 'r8', 'Validation trend should be scoped to r8');
assert.ok(validationTrend.points.length > 0, 'Validation trend should include points');
assert.equal(validationTrend.points[0]?.version, 'v0', 'Validation trend should start at v0');
assert.equal(
  validationTrend.points[validationTrend.points.length - 1]?.version,
  'v4.0',
  'Validation trend should end at v4.0'
);

const versionOrder = new Map(versions.map((version, index) => [version, index]));
for (let index = 1; index < validationTrend.points.length; index += 1) {
  const previousVersion = validationTrend.points[index - 1]?.version ?? '';
  const currentVersion = validationTrend.points[index]?.version ?? '';
  const previousRank = versionOrder.get(previousVersion);
  const currentRank = versionOrder.get(currentVersion);
  assert.ok(previousRank !== undefined && currentRank !== undefined, 'Validation trend points should map to known versions');
  assert.ok(previousRank < currentRank, 'Validation trend points should be sorted by version');
}

const expectedTrendCount = new Set(
  notes
    .filter(
      (entry) =>
        entry.validation_dataset.toLowerCase() === 'r8' &&
        entry.validation.status === 'complete' &&
        typeof entry.validation.income_diff_pct === 'number' &&
        Number.isFinite(entry.validation.income_diff_pct) &&
        typeof entry.validation.housing_wealth_diff_pct === 'number' &&
        Number.isFinite(entry.validation.housing_wealth_diff_pct) &&
        typeof entry.validation.financial_wealth_diff_pct === 'number' &&
        Number.isFinite(entry.validation.financial_wealth_diff_pct) &&
        versionOrder.has(entry.snapshot_folder)
    )
    .map((entry) => entry.snapshot_folder)
).size;
assert.equal(
  validationTrend.points.length,
  expectedTrendCount,
  'Validation trend point count should match complete r8 snapshots'
);

const v40Point = validationTrend.points.find((point) => point.version === 'v4.0');
assert.ok(v40Point, 'Validation trend should include v4.0 point');
assert.equal(v40Point?.incomeDiffPct, 7.87, 'v4.0 trend point should match income diff');
assert.equal(v40Point?.housingWealthDiffPct, 14.37, 'v4.0 trend point should match housing wealth diff');
assert.equal(v40Point?.financialWealthDiffPct, 13.25, 'v4.0 trend point should match financial wealth diff');
assertClose(
  Number(v40Point?.averageAbsDiffPct),
  (Math.abs(7.87) + Math.abs(14.37) + Math.abs(13.25)) / 3,
  1e-12,
  'v4.0 trend point should compute average absolute diff correctly'
);

const rangeAtSameVersion = compareParameters(repoRoot, 'v4.0', 'v4.0', ['national_insurance_rates'], 'range');
const throughRightAtSameVersion = compareParameters(repoRoot, 'v4.0', 'v4.0', ['national_insurance_rates'], 'through_right');
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

const singleBuyQuad = compareParameters(repoRoot, 'v4.0', 'v4.0', ['buy_quad'], 'through_right').items[0];
const buyQuadV38Origin = singleBuyQuad?.changeOriginsInRange.find((origin) => origin.versionId === 'v4.0');
assert.ok(buyQuadV38Origin, 'Expected buy_quad provenance to include v4.0 origin in through_right scope');
assert.ok(singleBuyQuad && singleBuyQuad.visualPayload.type === 'buy_quad', 'Expected buy_quad payload to use buy_quad type');
if (singleBuyQuad && singleBuyQuad.visualPayload.type === 'buy_quad') {
  const muRow = singleBuyQuad.visualPayload.parameters.find((row) => row.key === 'BUY_MU');
  assert.ok(muRow, 'Expected BUY_MU row in buy_quad parameters');
  assert.ok(
    Number.isFinite(singleBuyQuad.visualPayload.medianMultiplier.left) &&
      singleBuyQuad.visualPayload.medianMultiplier.left > 0,
    'Expected buy_quad medianMultiplier.left to be a positive finite number'
  );
  assert.ok(
    Number.isFinite(singleBuyQuad.visualPayload.medianMultiplier.right) &&
      singleBuyQuad.visualPayload.medianMultiplier.right > 0,
    'Expected buy_quad medianMultiplier.right to be a positive finite number'
  );
  assertClose(
    singleBuyQuad.visualPayload.medianMultiplier.right,
    Math.exp(Number(muRow?.right ?? Number.NaN)),
    1e-12,
    'Expected buy_quad medianMultiplier.right to match exp(BUY_MU)'
  );
}
assert.ok(
  (buyQuadV38Origin?.methodVariations.length ?? 0) > 0,
  'Expected buy_quad v4.0 provenance to include method variation notes'
);
assert.ok(
  buyQuadV38Origin?.methodVariations.some((variation) =>
    variation.configParameters.some((parameter) => parameter.startsWith('BUY_'))
  ),
  'Expected at least one method variation scoped to BUY_* parameters'
);
assert.ok(
  buyQuadV38Origin?.parameterChanges.every(
    (change) => !change.configParameter.startsWith('BUY_') || change.datasetSource === null
  ),
  'Expected v4.0 BUY_* parameter changes to have null dataset_source'
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

const unchangedCards = compareParameters(repoRoot, 'v0', latestVersion, [...newlyAddedIds], 'range');
assert.equal(unchangedCards.items.length, newlyAddedIds.length, 'Expected all newly added cards in compare payload');
for (const item of unchangedCards.items) {
  assert.equal(item.unchanged, true, `Expected newly added card ${item.id} to remain unchanged across versions`);
}

const saleMarkup = unchangedCards.items.find((item) => item.id === 'initial_sale_markup_distribution');
assert.ok(
  saleMarkup && saleMarkup.visualPayload.type === 'binned_distribution',
  'Expected initial_sale_markup_distribution card with binned payload'
);
if (saleMarkup && saleMarkup.visualPayload.type === 'binned_distribution') {
  assert.ok(
    saleMarkup.visualPayload.bins.every((bin) => Math.abs(bin.delta) <= 1e-12),
    'Sale mark-up bins should have zero delta across versions'
  );
}

const rentMarkup = unchangedCards.items.find((item) => item.id === 'initial_rent_markup_distribution');
assert.ok(
  rentMarkup && rentMarkup.visualPayload.type === 'binned_distribution',
  'Expected initial_rent_markup_distribution card with binned payload'
);
if (rentMarkup && rentMarkup.visualPayload.type === 'binned_distribution') {
  assert.ok(
    rentMarkup.visualPayload.bins.every((bin) => Math.abs(bin.delta) <= 1e-12),
    'Rent mark-up bins should have zero delta across versions'
  );
}

const unchangedSingleWithProvenance = compareParameters(
  repoRoot,
  latestVersion,
  latestVersion,
  [...newlyAddedIds],
  'through_right'
);
for (const item of unchangedSingleWithProvenance.items) {
  assert.equal(
    item.changeOriginsInRange.length,
    0,
    `Expected no provenance origins for newly added card ${item.id} in through_right scope`
  );
}

const reshapedCards = compareParameters(repoRoot, 'v0', latestVersion, [
  'price_reduction_probabilities',
  'sale_reduction_gaussian',
  'rent_reduction_gaussian',
  'hpa_expectation_params'
]);

const priceReductionProbabilities = reshapedCards.items.find((item) => item.id === 'price_reduction_probabilities');
assert.ok(priceReductionProbabilities, 'Expected price_reduction_probabilities card');
assert.equal(priceReductionProbabilities?.format, 'scalar_pair');
assert.deepEqual(priceReductionProbabilities?.sourceInfo.configKeys, ['P_SALE_PRICE_REDUCE', 'P_RENT_PRICE_REDUCE']);

const saleReductionGaussian = reshapedCards.items.find((item) => item.id === 'sale_reduction_gaussian');
assert.ok(saleReductionGaussian, 'Expected sale_reduction_gaussian card');
assert.equal(saleReductionGaussian?.format, 'gaussian_pair');
assert.ok(
  saleReductionGaussian?.visualPayload.type === 'gaussian_pair',
  'Expected gaussian_pair payload for sale_reduction_gaussian'
);
if (saleReductionGaussian?.visualPayload.type === 'gaussian_pair') {
  assert.equal(saleReductionGaussian.visualPayload.percentDomain.max, 50, 'Sale gaussian percent domain max should be 50');
  assert.ok(
    Number.isFinite(saleReductionGaussian.visualPayload.percentCapMassLeft) &&
      saleReductionGaussian.visualPayload.percentCapMassLeft >= 0 &&
      saleReductionGaussian.visualPayload.percentCapMassLeft <= 1,
    'Sale gaussian left cap mass should be a finite probability in [0, 1]'
  );
  assert.ok(
    Number.isFinite(saleReductionGaussian.visualPayload.percentCapMassRight) &&
      saleReductionGaussian.visualPayload.percentCapMassRight >= 0 &&
      saleReductionGaussian.visualPayload.percentCapMassRight <= 1,
    'Sale gaussian right cap mass should be a finite probability in [0, 1]'
  );
  assert.ok(
    saleReductionGaussian.visualPayload.logDomain.min < saleReductionGaussian.visualPayload.logDomain.max,
    'Sale gaussian log domain should be increasing'
  );
  assert.ok(
    saleReductionGaussian.visualPayload.percentDomain.min < saleReductionGaussian.visualPayload.percentDomain.max,
    'Sale gaussian percent domain should be increasing'
  );
  assert.ok(
    saleReductionGaussian.visualPayload.logCurveRight.every(
      (point) => Number.isFinite(point.x) && Number.isFinite(point.y) && point.y >= 0
    ),
    'Sale gaussian log curve should contain finite non-negative densities'
  );
  assert.ok(
    saleReductionGaussian.visualPayload.percentCurveRight.every(
      (point) => Number.isFinite(point.x) && Number.isFinite(point.y) && point.y >= 0 && point.x > 0 && point.x <= 50
    ),
    'Sale gaussian percent curve should contain finite non-negative densities within (0, 50]'
  );

  const muRight = saleReductionGaussian.visualPayload.parameters.find((row) => row.key === 'REDUCTION_MU')?.right;
  const sigmaRight = saleReductionGaussian.visualPayload.parameters.find((row) => row.key === 'REDUCTION_SIGMA')?.right;
  assert.ok(muRight !== undefined, 'Expected sale reduction mu in parameters');
  assert.ok(sigmaRight !== undefined && sigmaRight > 0, 'Expected positive sale reduction sigma in parameters');
  const sample = saleReductionGaussian.visualPayload.percentCurveRight[
    Math.floor(saleReductionGaussian.visualPayload.percentCurveRight.length / 2)
  ];
  assert.ok(sample, 'Expected sample point for sale percent curve');
  const expectedDensity = gaussianPercentDensity(sample.x, muRight as number, sigmaRight as number);
  assertClose(sample.y, expectedDensity, 1e-12, 'Sale percent curve should match transformed Gaussian density');
}

const rentReductionGaussian = reshapedCards.items.find((item) => item.id === 'rent_reduction_gaussian');
assert.ok(rentReductionGaussian, 'Expected rent_reduction_gaussian card');
assert.equal(rentReductionGaussian?.format, 'gaussian_pair');
assert.ok(
  rentReductionGaussian?.visualPayload.type === 'gaussian_pair',
  'Expected gaussian_pair payload for rent_reduction_gaussian'
);
if (rentReductionGaussian?.visualPayload.type === 'gaussian_pair') {
  assert.equal(rentReductionGaussian.visualPayload.percentDomain.max, 50, 'Rent gaussian percent domain max should be 50');
  assert.ok(
    Number.isFinite(rentReductionGaussian.visualPayload.percentCapMassLeft) &&
      rentReductionGaussian.visualPayload.percentCapMassLeft >= 0 &&
      rentReductionGaussian.visualPayload.percentCapMassLeft <= 1,
    'Rent gaussian left cap mass should be a finite probability in [0, 1]'
  );
  assert.ok(
    Number.isFinite(rentReductionGaussian.visualPayload.percentCapMassRight) &&
      rentReductionGaussian.visualPayload.percentCapMassRight >= 0 &&
      rentReductionGaussian.visualPayload.percentCapMassRight <= 1,
    'Rent gaussian right cap mass should be a finite probability in [0, 1]'
  );
  assert.ok(
    rentReductionGaussian.visualPayload.logCurveRight.every(
      (point) => Number.isFinite(point.x) && Number.isFinite(point.y) && point.y >= 0
    ),
    'Rent gaussian log curve should contain finite non-negative densities'
  );
  assert.ok(
    rentReductionGaussian.visualPayload.percentCurveRight.every(
      (point) => Number.isFinite(point.x) && Number.isFinite(point.y) && point.y >= 0 && point.x > 0 && point.x <= 50
    ),
    'Rent gaussian percent curve should contain finite non-negative densities within (0, 50]'
  );

  const muRight = rentReductionGaussian.visualPayload.parameters.find((row) => row.key === 'RENT_REDUCTION_MU')?.right;
  const sigmaRight = rentReductionGaussian.visualPayload.parameters.find((row) => row.key === 'RENT_REDUCTION_SIGMA')?.right;
  assert.ok(muRight !== undefined, 'Expected rent reduction mu in parameters');
  assert.ok(sigmaRight !== undefined && sigmaRight > 0, 'Expected positive rent reduction sigma in parameters');
  const sample = rentReductionGaussian.visualPayload.percentCurveRight[
    Math.floor(rentReductionGaussian.visualPayload.percentCurveRight.length / 2)
  ];
  assert.ok(sample, 'Expected sample point for rent percent curve');
  const expectedDensity = gaussianPercentDensity(sample.x, muRight as number, sigmaRight as number);
  assertClose(sample.y, expectedDensity, 1e-12, 'Rent percent curve should match transformed Gaussian density');
}

const hpaExpectation = reshapedCards.items.find((item) => item.id === 'hpa_expectation_params');
assert.ok(hpaExpectation, 'Expected hpa_expectation_params card');
assert.equal(hpaExpectation?.format, 'hpa_expectation_line');
assert.ok(
  hpaExpectation?.visualPayload.type === 'hpa_expectation_line',
  'Expected hpa_expectation_line payload for hpa_expectation_params'
);
if (hpaExpectation?.visualPayload.type === 'hpa_expectation_line') {
  assert.equal(hpaExpectation.visualPayload.domain.min, -0.2, 'HPA domain min should be -0.2');
  assert.equal(hpaExpectation.visualPayload.domain.max, 0.2, 'HPA domain max should be 0.2');
  assert.equal(hpaExpectation.visualPayload.dt, 1, 'HPA expectation DT should equal 1');

  const factorRight = hpaExpectation.visualPayload.parameters.find((row) => row.key === 'HPA_EXPECTATION_FACTOR')?.right;
  const constRight = hpaExpectation.visualPayload.parameters.find((row) => row.key === 'HPA_EXPECTATION_CONST')?.right;
  assert.ok(factorRight !== undefined, 'Expected HPA factor in parameters');
  assert.ok(constRight !== undefined, 'Expected HPA const in parameters');

  const sample = hpaExpectation.visualPayload.curveRight[Math.floor(hpaExpectation.visualPayload.curveRight.length / 2)];
  assert.ok(sample, 'Expected mid-point sample for HPA curve');
  const expected = (factorRight as number) * sample.x + (constRight as number);
  assertClose(sample.y, expected, 1e-12, 'HPA curve should satisfy y = factor*x + const');
}

for (const item of compare.items) {
  assert.equal(item.leftVersion, 'v0');
  assert.ok(item.sourceInfo.configPathLeft.endsWith('config.properties'));
  assert.ok(item.sourceInfo.configPathRight.endsWith('config.properties'));
  assert.ok(Array.isArray(item.sourceInfo.datasetsLeft), 'datasetsLeft should be present on every compare item');
  assert.ok(Array.isArray(item.sourceInfo.datasetsRight), 'datasetsRight should be present on every compare item');
  assert.ok(Array.isArray(item.changeOriginsInRange), 'changeOriginsInRange should be present on every compare item');
  for (const origin of item.changeOriginsInRange) {
    assert.ok(Array.isArray(origin.parameterChanges), 'parameterChanges should be present on every provenance origin');
    assert.ok(!('validationDataset' in origin), 'validationDataset should not be exposed on compare origins');
  }
}

const ageDist = compare.items.find((item) => item.id === 'age_distribution');
assert.ok(ageDist && ageDist.visualPayload.type === 'binned_distribution');
if (ageDist && ageDist.visualPayload.type === 'binned_distribution') {
  const labels = ageDist.visualPayload.bins.map((bin) => bin.label);
  assert.ok(labels.includes('75-85'), 'Expected split age band 75-85');
  assert.ok(labels.includes('85-95'), 'Expected split age band 85-95');
  assert.ok(!labels.includes('75-95'), 'Shared age grid should not include unsplit 75-95 band');

  const leftConfig = parseConfigFile(getConfigPath(repoRoot, 'v0'));
  const rightConfig = parseConfigFile(getConfigPath(repoRoot, 'v4.0'));
  const leftRows = readNumericCsvRows(
    resolveConfigDataFilePath(repoRoot, 'v0', leftConfig.get('DATA_AGE_DISTRIBUTION') ?? '')
  );
  const rightRows = readNumericCsvRows(
    resolveConfigDataFilePath(repoRoot, 'v4.0', rightConfig.get('DATA_AGE_DISTRIBUTION') ?? '')
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
  const rightConfig = parseConfigFile(getConfigPath(repoRoot, 'v4.0'));
  const leftRows = readNumericCsvRows(
    resolveConfigDataFilePath(repoRoot, 'v0', leftConfig.get('DATA_INCOME_GIVEN_AGE') ?? '')
  );
  const rightRows = readNumericCsvRows(
    resolveConfigDataFilePath(repoRoot, 'v4.0', rightConfig.get('DATA_INCOME_GIVEN_AGE') ?? '')
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
  assert.equal(niRates.unchanged, false, 'NI thresholds/rates should be changed between v0 and v4.0');
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
  buyQuad?.changeOriginsInRange.some((origin) => origin.versionId === 'v4.0' && origin.validationStatus === 'complete'),
  'buy_quad provenance should include v4.0 as complete'
);
assert.ok(buyQuad && buyQuad.visualPayload.type === 'buy_quad', 'Expected buy_quad card to return buy_quad payload');
if (buyQuad && buyQuad.visualPayload.type === 'buy_quad') {
  assert.ok(
    Number.isFinite(buyQuad.visualPayload.medianMultiplier.left) && buyQuad.visualPayload.medianMultiplier.left > 0,
    'Expected compare buy_quad medianMultiplier.left to be positive and finite'
  );
  assert.ok(
    Number.isFinite(buyQuad.visualPayload.medianMultiplier.right) && buyQuad.visualPayload.medianMultiplier.right > 0,
    'Expected compare buy_quad medianMultiplier.right to be positive and finite'
  );
}

const unchangedSingleSource = compareParameters(repoRoot, latestVersion, latestVersion, ['uk_housing_stock_totals'], 'through_right')
  .items[0];
assert.ok(unchangedSingleSource, 'Expected uk_housing_stock_totals in single compare payload');
assert.ok(unchangedSingleSource.unchanged, 'Expected uk_housing_stock_totals to be unchanged at same-version compare');
assert.ok(
  unchangedSingleSource.sourceInfo.datasetsRight.length > 0,
  'Expected unchanged single-version card to include source dataset attribution'
);

const wasSingle = compareParameters(repoRoot, 'v4.0', 'v4.0', ['age_distribution'], 'through_right').items[0];
assert.ok(wasSingle, 'Expected age_distribution card in single payload');
const wasDataset = wasSingle?.sourceInfo.datasetsRight.find((dataset) => dataset.tag === 'was');
assert.ok(wasDataset, 'Expected WAS dataset attribution for age_distribution');
assert.equal(wasDataset?.fullName, 'Wealth and Assets Survey', 'Expected WAS full name');
assert.equal(wasDataset?.year, '2022', 'Expected WAS Round 8 year to resolve to 2022');
assert.equal(wasDataset?.edition, 'Round 8', 'Expected WAS edition to resolve to Round 8');

const nmgCompare = compareParameters(repoRoot, 'v1.3', 'v4.0', ['rental_price_lognormal'], 'range').items[0];
assert.ok(nmgCompare, 'Expected rental_price_lognormal card in compare payload');
const nmgLeft = nmgCompare?.sourceInfo.datasetsLeft.find((dataset) => dataset.tag === 'nmg');
const nmgRight = nmgCompare?.sourceInfo.datasetsRight.find((dataset) => dataset.tag === 'nmg');
assert.ok(nmgLeft, 'Expected left-side NMG attribution');
assert.ok(nmgRight, 'Expected right-side NMG attribution');
assert.notEqual(nmgLeft?.year, nmgRight?.year, 'Expected NMG attribution year to vary by version side (left vs right)');
assert.equal(nmgLeft?.year, '2016', 'Expected v1.3 NMG year to be 2016 for rental-price keys');
assert.equal(nmgRight?.year, '2024', 'Expected v4.0 NMG year to be 2024 for rental-price keys');

const fixture = createResultsFixtureRepo();
try {
  const resultsRuns = getResultsRuns(fixture.root);
  assert.equal(resultsRuns.length, 4, 'Expected only synthetic fixture runs to be discovered');
  for (let index = 1; index < resultsRuns.length; index += 1) {
    const prev = Date.parse(resultsRuns[index - 1]?.modifiedAt ?? '');
    const current = Date.parse(resultsRuns[index]?.modifiedAt ?? '');
    assert.ok(prev >= current, 'Expected runs to be sorted by modifiedAt descending');
  }

  const fullRun = resultsRuns.find((run) => run.runId === fixture.runIds.complete);
  assert.ok(fullRun, 'Expected complete fixture run in discovery results');
  assert.equal(fullRun?.status, 'complete', 'Expected complete fixture run to be classified as complete');

  const emptyRun = resultsRuns.find((run) => run.runId === fixture.runIds.emptyOutput);
  assert.ok(emptyRun, 'Expected empty-output fixture run in discovery results');
  assert.equal(emptyRun?.status, 'partial', 'Expected empty-output fixture run to be classified as partial');

  const sparseRun = resultsRuns.find((run) => run.runId === fixture.runIds.sparseCore);
  assert.ok(sparseRun, 'Expected sparse-core fixture run in discovery results');
  assert.equal(sparseRun?.status, 'partial', 'Expected sparse-core fixture run to be classified as partial');

  const runDetail = getResultsRunDetail(fixture.root, fixture.runIds.complete);
  assert.equal(runDetail.kpiSummary.length, 15, 'Expected 15 core KPI summary metrics');
  assert.equal(runDetail.indicators.length, 27, 'Expected 27 total indicator definitions (15 core + 12 output)');
  assert.ok(runDetail.configAvailable, 'Expected complete fixture run to report config.properties availability');
  assert.ok(
    runDetail.indicators.some((indicator) => indicator.id === 'output_interestRate' && indicator.available),
    'Expected output interest rate indicator to be available on complete fixture run'
  );

  const scenarioDetail = getResultsRunDetail(fixture.root, fixture.runIds.noConfig);
  assert.equal(
    scenarioDetail.configAvailable,
    false,
    'Expected no-config fixture run to report configAvailable=false'
  );

  const manifestFull = getResultsRunFiles(fixture.root, fixture.runIds.complete);
  assert.ok(
    manifestFull.some(
      (file) => file.fileName === 'Output-run1.csv' && file.coverageStatus === 'supported'
    ),
    'Expected Output-run1.csv to be marked supported in manifest'
  );
  assert.ok(
    manifestFull.some(
      (file) =>
        file.fileName === 'RentalTransactions-run1.csv' &&
        file.coverageStatus === 'unsupported' &&
        file.note?.includes('Manifest only (not charted)')
    ),
    'Expected heavy transaction files to be manifest-only (not charted)'
  );

  const manifestEmpty = getResultsRunFiles(fixture.root, fixture.runIds.emptyOutput);
  assert.ok(
    manifestEmpty.some((file) => file.fileName === 'Output-run1.csv' && file.coverageStatus === 'empty'),
    'Expected empty Output-run1.csv to be marked empty in manifest'
  );

  const missingMicroManifest = getResultsRunFiles(fixture.root, fixture.runIds.noConfig);
  assert.ok(
    !missingMicroManifest.some((file) => file.fileName === 'BankBalance-run1.csv'),
    'Expected manifest to tolerate runs missing optional micro snapshot files'
  );

  const rawSeries = getResultsSeries(fixture.root, fixture.runIds.complete, 'core_mortgageApprovals', 0);
  const smoothedSeries = getResultsSeries(fixture.root, fixture.runIds.complete, 'core_mortgageApprovals', 12);
  assert.equal(rawSeries.points.length, 2001, 'Expected full run to expose 2001 model-time points');
  assert.equal(smoothedSeries.points.length, rawSeries.points.length, 'Smoothing should preserve point count');
  assert.ok(
    smoothedSeries.points.some((point, index) => point.value !== rawSeries.points[index]?.value),
    'Expected smoothing to modify at least one time point'
  );

  const overlayCompare = getResultsCompare(
    fixture.root,
    [fixture.runIds.complete, fixture.runIds.sparseCore],
    ['core_mortgageApprovals'],
    'tail120',
    0
  );
  assert.equal(overlayCompare.indicators.length, 1, 'Expected single-indicator compare payload');
  const leftSeries = overlayCompare.indicators[0]?.seriesByRun.find((series) => series.runId === fixture.runIds.complete);
  const rightSeries = overlayCompare.indicators[0]?.seriesByRun.find((series) => series.runId === fixture.runIds.sparseCore);
  assert.ok(leftSeries && rightSeries, 'Expected aligned compare series for both selected runs');
  assert.equal(
    leftSeries?.points.length,
    rightSeries?.points.length,
    'Expected compare payload to align series on shared modelTime axis'
  );
  assert.ok(
    rightSeries?.points.every((point) => point.value === null),
    'Expected sparse core run to render as gap-only aligned series'
  );

  const postSpinUpCompare = getResultsCompare(
    fixture.root,
    [fixture.runIds.complete, fixture.runIds.sparseCore],
    ['core_mortgageApprovals'],
    'post200',
    0
  );
  const postSpinUpSeries = postSpinUpCompare.indicators[0]?.seriesByRun.find(
    (series) => series.runId === fixture.runIds.complete
  );
  assert.ok(postSpinUpSeries, 'Expected post200 compare series for complete run');
  assert.ok(
    postSpinUpSeries?.points.every((point) => point.modelTime >= 200),
    'Expected post200 compare window to exclude pre-spin-up ticks'
  );

  assert.throws(
    () =>
      getResultsCompare(
        fixture.root,
        ['r1', 'r2', 'r3', 'r4', 'r5', 'r6'],
        ['core_mortgageApprovals'],
        'tail120',
        0
      ),
    /maximum of 5 runIds/,
    'Expected compare endpoint guardrail for >5 runs'
  );

  assert.throws(
    () => getResultsRunDetail(fixture.root, '..'),
    /Unknown run: \.\./,
    'Expected traversal-style run ids to be rejected'
  );

  const deleted = deleteResultsRun(fixture.root, fixture.runIds.noConfig);
  assert.equal(deleted.deleted, true, 'Expected delete results API to report success');
  assert.equal(deleted.runId, fixture.runIds.noConfig, 'Expected delete payload to return the deleted runId');
  assert.ok(
    !getResultsRuns(fixture.root).some((run) => run.runId === fixture.runIds.noConfig),
    'Expected deleted run to be removed from run inventory'
  );
  assert.throws(
    () => deleteResultsRun(fixture.root, '..'),
    /Unknown run: \.\./,
    'Expected traversal-style run ids to be rejected for run deletion'
  );
  for (const protectedRunId of ['v0-output', 'v1.0-output', 'v2.0-output', 'v3.0-output', 'v4.0-output']) {
    assert.throws(
      () => deleteResultsRun(fixture.root, protectedRunId),
      /protected/,
      `Expected baseline run ${protectedRunId} to be protected from deletion`
    );
  }
} finally {
  fs.rmSync(fixture.root, { recursive: true, force: true });
}

const modelRunFixtureRoot = createModelRunFixtureRepo();
const spawnedProcesses: FakeModelProcess[] = [];

try {
  __resetModelRunManagerForTests();
  __setModelRunSpawnForTests(() => {
    const fakeProcess = new FakeModelProcess();
    spawnedProcesses.push(fakeProcess);
    return fakeProcess as never;
  });

  const runOptions = getModelRunOptions(modelRunFixtureRoot, undefined, true);
  assert.equal(runOptions.executionEnabled, true, 'Expected execution flag to be forwarded by options payload');
  assert.equal(runOptions.parameters.length, 30, 'Expected all 30 USER SET parameters in options payload');
  assert.equal(runOptions.defaultBaseline, 'v1.0', 'Expected latest stable baseline to exclude in-progress snapshots');
  assert.equal(runOptions.requestedBaseline, 'v1.0', 'Expected requested baseline default to latest stable snapshot');
  assert.ok(
    runOptions.snapshots.some((snapshot) => snapshot.version === 'v1.1' && snapshot.status === 'in_progress'),
    'Expected in-progress snapshot status in options payload'
  );

  const optionsForInProgress = getModelRunOptions(modelRunFixtureRoot, 'v1.1', true);
  assert.equal(optionsForInProgress.requestedBaseline, 'v1.1', 'Expected baseline override selection to be honored');

  const originalResultsCapMb = process.env.DASHBOARD_RESULTS_CAP_MB;
  try {
    process.env.DASHBOARD_RESULTS_CAP_MB = '2';

    const protectedRunPath = path.join(modelRunFixtureRoot, 'Results', 'v0-output');
    fs.mkdirSync(protectedRunPath, { recursive: true });
    writeSizedFile(path.join(protectedRunPath, 'protected.bin'), 1024 * 1024);

    const storageBefore = getResultsStorageSummary(modelRunFixtureRoot);
    assert.equal(storageBefore.capBytes, 2 * 1024 * 1024, 'Expected storage summary to reflect DASHBOARD_RESULTS_CAP_MB');
    assert.ok(storageBefore.usedBytes >= 1024 * 1024, 'Expected storage summary used bytes to include baseline fixture files');

    const overCapSubmit = submitModelRun(modelRunFixtureRoot, {
      baseline: 'v1.0',
      title: 'cap-overflow-visible',
      overrides: { SEED: 12 },
      confirmWarnings: true
    });
    assert.equal(overCapSubmit.accepted, true, 'Expected run submission to be accepted while still under cap');
    assert.equal(spawnedProcesses.length, 1, 'Expected accepted run to start immediately');

    const overCapOutputPath = path.join(modelRunFixtureRoot, overCapSubmit.job?.outputPath ?? '');
    writeSizedFile(path.join(overCapOutputPath, 'overflow.bin'), 1200 * 1024);

    spawnedProcesses[spawnedProcesses.length - 1]?.succeed();
    await waitForAsyncTick();
    const completedOverCapJob = listModelRunJobs().find((job) => job.jobId === overCapSubmit.job?.jobId);
    assert.equal(completedOverCapJob?.status, 'succeeded', 'Expected run to finish successfully when crossing cap');
    assert.ok(fs.existsSync(overCapOutputPath), 'Expected over-cap completed run output folder to remain visible');

    const storageAfter = getResultsStorageSummary(modelRunFixtureRoot);
    assert.ok(storageAfter.usedBytes > storageAfter.capBytes, 'Expected storage usage to exceed cap after completed run');
    assert.throws(
      () =>
        submitModelRun(modelRunFixtureRoot, {
          baseline: 'v1.0',
          title: 'blocked-after-over-cap',
          overrides: { SEED: 13 },
          confirmWarnings: true
        }),
      /Results storage cap reached/,
      'Expected submission to fail when Results storage is at or above configured cap'
    );
    assert.ok(
      fs.existsSync(overCapOutputPath),
      'Expected strict cap mode to keep completed over-cap run output visible'
    );
    clearModelRunJob(overCapSubmit.job?.jobId ?? '');
  } finally {
    if (originalResultsCapMb === undefined) {
      delete process.env.DASHBOARD_RESULTS_CAP_MB;
    } else {
      process.env.DASHBOARD_RESULTS_CAP_MB = originalResultsCapMb;
    }
  }
  __resetModelRunManagerForTests();
  spawnedProcesses.length = 0;
  __setModelRunSpawnForTests(() => {
    const fakeProcess = new FakeModelProcess();
    spawnedProcesses.push(fakeProcess);
    return fakeProcess as never;
  });

  const warningResponse = submitModelRun(modelRunFixtureRoot, {
    baseline: 'v1.0',
    title: 'warning-check',
    overrides: { N_STEPS: 5001 },
    confirmWarnings: false
  });
  assert.equal(warningResponse.accepted, false, 'Expected submit to request explicit warning confirmation');
  assert.ok((warningResponse.warnings?.length ?? 0) > 0, 'Expected warning payload when confirmation is missing');
  assert.equal(listModelRunJobs().length, 0, 'Expected warning-only submit not to enqueue a job');

  const firstSubmit = submitModelRun(modelRunFixtureRoot, {
    baseline: 'v1.0',
    title: 'first-run',
    overrides: { N_STEPS: 5001 },
    confirmWarnings: true
  });
  assert.equal(firstSubmit.accepted, true, 'Expected confirmed warning submit to enqueue run');
  assert.ok(firstSubmit.job, 'Expected accepted submit to include job payload');
  assert.equal(firstSubmit.job?.runId, 'first-run v1.0', 'Expected run title to determine output folder name');
  assert.equal(spawnedProcesses.length, 1, 'Expected first accepted submit to start runner immediately');

  const secondSubmit = submitModelRun(modelRunFixtureRoot, {
    baseline: 'v1.0',
    title: 'second-run',
    overrides: { SEED: 77 },
    confirmWarnings: true
  });
  assert.equal(secondSubmit.accepted, true, 'Expected second submit to be accepted into queue');
  const queuedJob = listModelRunJobs().find((job) => job.jobId === secondSubmit.job?.jobId);
  assert.equal(queuedJob?.status, 'queued', 'Expected second job to queue while first run is active');

  spawnedProcesses[0]?.emitStdout('sim line');
  spawnedProcesses[0]?.emitStderr('warn line');
  await waitForAsyncTick();
  const firstLogs = getModelRunJobLogs(firstSubmit.job?.jobId ?? '', 0, 50);
  assert.ok(firstLogs.lines.some((line) => line.includes('sim line')), 'Expected stdout log line in polling payload');
  assert.ok(firstLogs.lines.some((line) => line.includes('warn line')), 'Expected stderr log line in polling payload');

  cancelModelRunJob(modelRunFixtureRoot, secondSubmit.job?.jobId ?? '');
  const canceledQueuedJob = listModelRunJobs().find((job) => job.jobId === secondSubmit.job?.jobId);
  assert.equal(canceledQueuedJob?.status, 'canceled', 'Expected queued cancel to mark job as canceled');

  spawnedProcesses[0]?.succeed();
  await waitForAsyncTick();
  const completedFirstJob = listModelRunJobs().find((job) => job.jobId === firstSubmit.job?.jobId);
  assert.equal(completedFirstJob?.status, 'succeeded', 'Expected first job to complete successfully');
  assert.ok(
    completedFirstJob && fs.existsSync(path.join(modelRunFixtureRoot, completedFirstJob.outputPath)),
    'Expected successful run output folder to persist'
  );

  const warningCoreIndicatorsOff = submitModelRun(modelRunFixtureRoot, {
    baseline: 'v1.0',
    title: 'core-off-warning',
    overrides: { recordCoreIndicators: false },
    confirmWarnings: false
  });
  assert.equal(warningCoreIndicatorsOff.accepted, false, 'Expected submit to block until warnings are confirmed');
  assert.ok(
    warningCoreIndicatorsOff.warnings.some((warning) => warning.code === 'core_indicators_disabled'),
    'Expected warning when recordCoreIndicators is disabled'
  );

  const preexistingRunFolder = path.join(modelRunFixtureRoot, 'Results', 'overwrite-case v1.0');
  fs.mkdirSync(preexistingRunFolder, { recursive: true });
  fs.writeFileSync(path.join(preexistingRunFolder, 'Output-run1.csv'), 'Model time;nRenting\n0;1\n', 'utf-8');

  const overwriteWarning = submitModelRun(modelRunFixtureRoot, {
    baseline: 'v1.0',
    title: 'overwrite-case',
    overrides: { SEED: 5 },
    confirmWarnings: false
  });
  assert.equal(overwriteWarning.accepted, false, 'Expected overwrite warning to require explicit confirmation');
  assert.ok(
    overwriteWarning.warnings.some((warning) => warning.code === 'output_folder_exists'),
    'Expected overwrite warning when output folder already exists'
  );

  const overwriteSubmit = submitModelRun(modelRunFixtureRoot, {
    baseline: 'v1.0',
    title: 'overwrite-case',
    overrides: { SEED: 5 },
    confirmWarnings: true
  });
  assert.equal(overwriteSubmit.accepted, true, 'Expected overwrite-confirmed submit to enqueue run');
  assert.equal(spawnedProcesses.length, 2, 'Expected overwrite-confirmed run to start immediately');
  assert.throws(
    () =>
      submitModelRun(modelRunFixtureRoot, {
        baseline: 'v1.0',
        title: 'overwrite-case',
        overrides: { SEED: 6 },
        confirmWarnings: true
      }),
    /already targeting output folder/,
    'Expected active output-folder collision to be rejected'
  );
  assert.throws(
    () => clearModelRunJob(overwriteSubmit.job?.jobId ?? ''),
    /Only finished jobs can be cleared/,
    'Expected running jobs to be non-clearable'
  );
  spawnedProcesses[1]?.succeed();
  await waitForAsyncTick();
  const overwriteCompleted = listModelRunJobs().find((job) => job.jobId === overwriteSubmit.job?.jobId);
  assert.equal(overwriteCompleted?.status, 'succeeded', 'Expected overwrite-confirmed run to complete successfully');

  const thirdSubmit = submitModelRun(modelRunFixtureRoot, {
    baseline: 'v1.0',
    title: 'cancel-running',
    overrides: { SEED: 9 },
    confirmWarnings: true
  });
  assert.equal(thirdSubmit.accepted, true, 'Expected third submit accepted');
  assert.equal(spawnedProcesses.length, 3, 'Expected third submit to start another process after previous completion');
  cancelModelRunJob(modelRunFixtureRoot, thirdSubmit.job?.jobId ?? '');
  await waitForAsyncTick();
  const canceledRunningJob = listModelRunJobs().find((job) => job.jobId === thirdSubmit.job?.jobId);
  assert.equal(canceledRunningJob?.status, 'canceled', 'Expected running cancel to transition to canceled');
  assert.ok(
    canceledRunningJob && !fs.existsSync(path.join(modelRunFixtureRoot, canceledRunningJob.outputPath)),
    'Expected canceled running job output folder to be removed'
  );

  const lateCancelSubmit = submitModelRun(modelRunFixtureRoot, {
    baseline: 'v1.0',
    title: 'late-cancel-race',
    overrides: { SEED: 10 },
    confirmWarnings: true
  });
  assert.equal(lateCancelSubmit.accepted, true, 'Expected late-cancel race submit to be accepted');
  const lateCancelProcess = spawnedProcesses[spawnedProcesses.length - 1];
  assert.ok(lateCancelProcess, 'Expected late-cancel race submit to spawn a process');
  lateCancelProcess?.disableSigtermDelivery();
  cancelModelRunJob(modelRunFixtureRoot, lateCancelSubmit.job?.jobId ?? '');
  lateCancelProcess?.succeed();
  await waitForAsyncTick();
  const lateCancelCompleted = listModelRunJobs().find((job) => job.jobId === lateCancelSubmit.job?.jobId);
  assert.equal(
    lateCancelCompleted?.status,
    'succeeded',
    'Expected failed SIGTERM delivery to preserve successful completion status'
  );
  assert.ok(
    lateCancelCompleted && fs.existsSync(path.join(modelRunFixtureRoot, lateCancelCompleted.outputPath)),
    'Expected successful run output folder to be retained when cancel signal is not delivered'
  );

  const firstOutputPath = completedFirstJob?.outputPath;
  clearModelRunJob(firstSubmit.job?.jobId ?? '');
  assert.ok(
    !listModelRunJobs().some((job) => job.jobId === firstSubmit.job?.jobId),
    'Expected clear job action to remove finished job from queue history'
  );
  assert.ok(
    firstOutputPath && fs.existsSync(path.join(modelRunFixtureRoot, firstOutputPath)),
    'Expected clear job action not to delete successful run outputs'
  );

  __resetModelRunManagerForTests();
  __setModelRunSpawnForTests(() => new FakeModelProcess() as never);
  const untitledSubmit = submitModelRun(modelRunFixtureRoot, {
    baseline: 'v1.0',
    title: '   ',
    overrides: { SEED: 88 },
    confirmWarnings: true
  });
  assert.equal(untitledSubmit.accepted, true, 'Expected untitled submit to be accepted with fallback folder naming');
  assert.match(
    untitledSubmit.job?.runId ?? '',
    /^run-\d{8}T\d{6}Z v1\.0$/,
    'Expected untitled submit to use run-<timestamp> <baseline> output folder naming'
  );

  __resetModelRunManagerForTests();
  __setModelRunSpawnForTests(() => new FakeModelProcess() as never);
  for (let index = 0; index < 10; index += 1) {
    const response = submitModelRun(modelRunFixtureRoot, {
      baseline: 'v1.0',
      title: `queue-fill-${index + 1}`,
      overrides: { SEED: index + 1 },
      confirmWarnings: true
    });
    assert.equal(response.accepted, true, 'Expected queue fill submissions to succeed before cap');
  }
  assert.throws(
    () =>
      submitModelRun(modelRunFixtureRoot, {
        baseline: 'v1.0',
        overrides: { SEED: 999 },
        confirmWarnings: true
      }),
    /capacity reached/,
    'Expected queue cap guardrail to reject submissions above limit'
  );
} finally {
  __resetModelRunManagerForTests();
  fs.rmSync(modelRunFixtureRoot, { recursive: true, force: true });
}

const writeAuthDisabled = createWriteAuthController(undefined, undefined);
const disabledStatus = writeAuthDisabled.resolveAccess(undefined);
assert.equal(disabledStatus.authEnabled, false, 'Expected auth to be disabled when credentials are unset');
assert.equal(disabledStatus.canWrite, true, 'Expected local write access when auth is disabled');

const misconfiguredAuthStatus = resolveDashboardWriteAccess(writeAuthDisabled, undefined, true);
assert.equal(
  misconfiguredAuthStatus.authEnabled,
  true,
  'Expected model-runs-enabled auth misconfiguration to report auth-enabled read-only mode'
);
assert.equal(
  misconfiguredAuthStatus.canWrite,
  false,
  'Expected model-runs-enabled auth misconfiguration to block write access'
);
assert.equal(
  misconfiguredAuthStatus.authMisconfigured,
  true,
  'Expected auth misconfiguration status to be surfaced for UI and API handling'
);
const misconfiguredLoginError = getWriteAuthConfigurationError(writeAuthDisabled, true);
assert.ok(
  misconfiguredLoginError?.includes('DASHBOARD_WRITE_USERNAME'),
  'Expected auth misconfiguration to surface actionable login-blocking configuration error'
);

const writeAuthEnabled = createWriteAuthController('writer', 'secret');
const enabledStatusWithoutToken = writeAuthEnabled.resolveAccess(undefined);
assert.equal(enabledStatusWithoutToken.authEnabled, true, 'Expected auth to be enabled when credentials are configured');
assert.equal(enabledStatusWithoutToken.canWrite, false, 'Expected write access to require login in auth-enabled mode');

const badLogin = writeAuthEnabled.login('writer', 'incorrect');
assert.equal(badLogin.ok, false, 'Expected login to fail for invalid credentials');

const goodLogin = writeAuthEnabled.login('writer', 'secret');
assert.equal(goodLogin.ok, true, 'Expected login to succeed for valid credentials');
assert.ok(goodLogin.token, 'Expected successful login to issue a token');

const enabledStatusWithToken = writeAuthEnabled.resolveAccess(`Bearer ${goodLogin.token}`);
assert.equal(enabledStatusWithToken.canWrite, true, 'Expected bearer token to grant write access');
writeAuthEnabled.logout(goodLogin.token ?? null);
const afterLogoutStatus = writeAuthEnabled.resolveAccess(`Bearer ${goodLogin.token}`);
assert.equal(afterLogoutStatus.canWrite, false, 'Expected logout to revoke write access token');

const compareCardSource = fs.readFileSync(path.resolve(repoRoot, 'dashboard/src/components/CompareCard.tsx'), 'utf-8');
assert.ok(
  !compareCardSource.includes('Validation dataset'),
  'Compare card should not render Validation dataset field'
);

const gitStatsSource = fs.readFileSync(path.resolve(repoRoot, 'dashboard/server/lib/gitStats.ts'), 'utf-8');
assert.ok(
  gitStatsSource.includes("execFileSync('git', ['diff', '--shortstat', baseCommit]"),
  'git-stats should compute totals with local git shortstat semantics'
);
assert.ok(
  gitStatsSource.includes("['rev-list', '--count', `${baseCommit}..HEAD`]"),
  'git-stats should compute total commits with local git rev-list semantics'
);
assert.ok(
  gitStatsSource.includes("['diff', '--shortstat', weeklyDiffBase, 'HEAD']"),
  'git-stats should compute weekly totals with local git shortstat semantics'
);
assert.ok(
  gitStatsSource.includes("['rev-list', '--count', `--since=${sinceIso}`, 'HEAD']"),
  'git-stats should compute weekly commits with local git rev-list semantics'
);
assert.ok(
  gitStatsSource.includes('api.github.com/repos'),
  'git-stats should include GitHub API fallback for production environments without local git'
);

console.log('Smoke tests passed.');
