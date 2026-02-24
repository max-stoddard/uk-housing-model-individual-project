import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { compareParameters, getInProgressVersions, getParameterCatalog, getVersions } from '../server/lib/service.js';
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

function gaussianPercentDensity(percent: number, mu: number, sigma: number): number {
  const denominator = percent * sigma * Math.sqrt(2 * Math.PI);
  const exponent = -((Math.log(percent) - mu) ** 2) / (2 * sigma ** 2);
  return Math.exp(exponent) / denominator;
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
assert.ok(inProgressVersions.includes('v3.8'), 'Expected v3.8 to be reported as an in-progress snapshot');
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
assert.ok(
  buyQuadV38Origin?.parameterChanges.every(
    (change) => !change.configParameter.startsWith('BUY_') || change.datasetSource === null
  ),
  'Expected v3.8 BUY_* parameter changes to have null dataset_source'
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

const unchangedSingleSource = compareParameters(repoRoot, latestVersion, latestVersion, ['uk_housing_stock_totals'], 'through_right')
  .items[0];
assert.ok(unchangedSingleSource, 'Expected uk_housing_stock_totals in single compare payload');
assert.ok(unchangedSingleSource.unchanged, 'Expected uk_housing_stock_totals to be unchanged at same-version compare');
assert.ok(
  unchangedSingleSource.sourceInfo.datasetsRight.length > 0,
  'Expected unchanged single-version card to include source dataset attribution'
);

const wasSingle = compareParameters(repoRoot, 'v3.8', 'v3.8', ['age_distribution'], 'through_right').items[0];
assert.ok(wasSingle, 'Expected age_distribution card in single payload');
const wasDataset = wasSingle?.sourceInfo.datasetsRight.find((dataset) => dataset.tag === 'was');
assert.ok(wasDataset, 'Expected WAS dataset attribution for age_distribution');
assert.equal(wasDataset?.fullName, 'Wealth and Assets Survey', 'Expected WAS full name');
assert.equal(wasDataset?.year, '2022', 'Expected WAS Round 8 year to resolve to 2022');
assert.equal(wasDataset?.edition, 'Round 8', 'Expected WAS edition to resolve to Round 8');

const nmgCompare = compareParameters(repoRoot, 'v1.3', 'v3.8', ['rental_price_lognormal'], 'range').items[0];
assert.ok(nmgCompare, 'Expected rental_price_lognormal card in compare payload');
const nmgLeft = nmgCompare?.sourceInfo.datasetsLeft.find((dataset) => dataset.tag === 'nmg');
const nmgRight = nmgCompare?.sourceInfo.datasetsRight.find((dataset) => dataset.tag === 'nmg');
assert.ok(nmgLeft, 'Expected left-side NMG attribution');
assert.ok(nmgRight, 'Expected right-side NMG attribution');
assert.notEqual(nmgLeft?.year, nmgRight?.year, 'Expected NMG attribution year to vary by version side (left vs right)');
assert.equal(nmgLeft?.year, '2016', 'Expected v1.3 NMG year to be 2016 for rental-price keys');
assert.equal(nmgRight?.year, '2024', 'Expected v3.8 NMG year to be 2024 for rental-price keys');

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
