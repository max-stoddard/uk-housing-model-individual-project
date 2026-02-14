import { PARAMETER_IDS } from '../../shared/catalog';

export interface ChartAxisSpec {
  scalar: { xTitle: string; yTitle: string };
  binned: { xTitle: string; yTitle: string; yDeltaTitle: string };
  joint: { xTitle: string; yTitle: string; legendTitle: string };
  curve: { xTitle: string; yTitle: string };
  buyBudget: { xTitle: string; yTitle: string };
  buyMultiplier: { xTitle: string; yTitle: string };
}

const AXIS_SPECS: Record<string, ChartAxisSpec> = {
  income_given_age_joint: {
    scalar: { xTitle: 'Parameter (-)', yTitle: 'Value (-)' },
    binned: { xTitle: 'Bin range (-)', yTitle: 'Value (-)', yDeltaTitle: 'Delta (-)' },
    joint: {
      xTitle: 'Age band (years)',
      yTitle: 'Gross income band (£/year)',
      legendTitle: 'Probability mass (-)'
    },
    curve: { xTitle: 'Value (-)', yTitle: 'Density (1/unit)' },
    buyBudget: { xTitle: 'Household income (£/year)', yTitle: 'Purchase budget (£)' },
    buyMultiplier: { xTitle: 'Budget multiplier (-)', yTitle: 'Probability density (1/unit)' }
  },
  wealth_given_income_joint: {
    scalar: { xTitle: 'Parameter (-)', yTitle: 'Value (-)' },
    binned: { xTitle: 'Bin range (-)', yTitle: 'Value (-)', yDeltaTitle: 'Delta (-)' },
    joint: {
      xTitle: 'Gross income band (£/year)',
      yTitle: 'Net wealth band (£)',
      legendTitle: 'Probability mass (-)'
    },
    curve: { xTitle: 'Value (-)', yTitle: 'Density (1/unit)' },
    buyBudget: { xTitle: 'Household income (£/year)', yTitle: 'Purchase budget (£)' },
    buyMultiplier: { xTitle: 'Budget multiplier (-)', yTitle: 'Probability density (1/unit)' }
  },
  btl_probability_bins: {
    scalar: { xTitle: 'Parameter (-)', yTitle: 'Value (-)' },
    binned: {
      xTitle: 'Income percentile (%)',
      yTitle: 'BTL investor probability (-)',
      yDeltaTitle: 'Probability delta (-)'
    },
    joint: { xTitle: 'X bin (-)', yTitle: 'Y bin (-)', legendTitle: 'Probability mass (-)' },
    curve: { xTitle: 'Value (-)', yTitle: 'Density (1/unit)' },
    buyBudget: { xTitle: 'Household income (£/year)', yTitle: 'Purchase budget (£)' },
    buyMultiplier: { xTitle: 'Budget multiplier (-)', yTitle: 'Probability density (1/unit)' }
  },
  age_distribution: {
    scalar: { xTitle: 'Parameter (-)', yTitle: 'Value (-)' },
    binned: { xTitle: 'Age band (years)', yTitle: 'Household share (-)', yDeltaTitle: 'Share delta (-)' },
    joint: { xTitle: 'X bin (-)', yTitle: 'Y bin (-)', legendTitle: 'Probability mass (-)' },
    curve: { xTitle: 'Value (-)', yTitle: 'Density (1/unit)' },
    buyBudget: { xTitle: 'Household income (£/year)', yTitle: 'Purchase budget (£)' },
    buyMultiplier: { xTitle: 'Budget multiplier (-)', yTitle: 'Probability density (1/unit)' }
  },
  national_insurance_rates: {
    scalar: { xTitle: 'Parameter (-)', yTitle: 'Value (-)' },
    binned: {
      xTitle: 'Gross income band (£/year)',
      yTitle: 'Marginal NI rate (-)',
      yDeltaTitle: 'Rate delta (-)'
    },
    joint: { xTitle: 'X bin (-)', yTitle: 'Y bin (-)', legendTitle: 'Probability mass (-)' },
    curve: { xTitle: 'Value (-)', yTitle: 'Density (1/unit)' },
    buyBudget: { xTitle: 'Household income (£/year)', yTitle: 'Purchase budget (£)' },
    buyMultiplier: { xTitle: 'Budget multiplier (-)', yTitle: 'Probability density (1/unit)' }
  },
  income_tax_rates: {
    scalar: { xTitle: 'Parameter (-)', yTitle: 'Value (-)' },
    binned: {
      xTitle: 'Gross income band (£/year)',
      yTitle: 'Marginal income tax rate (-)',
      yDeltaTitle: 'Rate delta (-)'
    },
    joint: { xTitle: 'X bin (-)', yTitle: 'Y bin (-)', legendTitle: 'Probability mass (-)' },
    curve: { xTitle: 'Value (-)', yTitle: 'Density (1/unit)' },
    buyBudget: { xTitle: 'Household income (£/year)', yTitle: 'Purchase budget (£)' },
    buyMultiplier: { xTitle: 'Budget multiplier (-)', yTitle: 'Probability density (1/unit)' }
  },
  government_allowance_support: {
    scalar: { xTitle: 'Policy parameter (-)', yTitle: 'Amount (£/month or £/year)' },
    binned: { xTitle: 'Bin range (-)', yTitle: 'Value (-)', yDeltaTitle: 'Delta (-)' },
    joint: { xTitle: 'X bin (-)', yTitle: 'Y bin (-)', legendTitle: 'Probability mass (-)' },
    curve: { xTitle: 'Value (-)', yTitle: 'Density (1/unit)' },
    buyBudget: { xTitle: 'Household income (£/year)', yTitle: 'Purchase budget (£)' },
    buyMultiplier: { xTitle: 'Budget multiplier (-)', yTitle: 'Probability density (1/unit)' }
  },
  house_price_lognormal: {
    scalar: { xTitle: 'Parameter (-)', yTitle: 'Value (-)' },
    binned: { xTitle: 'Bin range (-)', yTitle: 'Value (-)', yDeltaTitle: 'Delta (-)' },
    joint: { xTitle: 'X bin (-)', yTitle: 'Y bin (-)', legendTitle: 'Probability mass (-)' },
    curve: { xTitle: 'House price (£)', yTitle: 'Probability density (1/£)' },
    buyBudget: { xTitle: 'Household income (£/year)', yTitle: 'Purchase budget (£)' },
    buyMultiplier: { xTitle: 'Budget multiplier (-)', yTitle: 'Probability density (1/unit)' }
  },
  rental_price_lognormal: {
    scalar: { xTitle: 'Parameter (-)', yTitle: 'Value (-)' },
    binned: { xTitle: 'Bin range (-)', yTitle: 'Value (-)', yDeltaTitle: 'Delta (-)' },
    joint: { xTitle: 'X bin (-)', yTitle: 'Y bin (-)', legendTitle: 'Probability mass (-)' },
    curve: { xTitle: 'Rent value (£)', yTitle: 'Probability density (1/£)' },
    buyBudget: { xTitle: 'Household income (£/year)', yTitle: 'Purchase budget (£)' },
    buyMultiplier: { xTitle: 'Budget multiplier (-)', yTitle: 'Probability density (1/unit)' }
  },
  desired_rent_power: {
    scalar: { xTitle: 'Parameter (-)', yTitle: 'Value (-)' },
    binned: { xTitle: 'Bin range (-)', yTitle: 'Value (-)', yDeltaTitle: 'Delta (-)' },
    joint: { xTitle: 'X bin (-)', yTitle: 'Y bin (-)', legendTitle: 'Probability mass (-)' },
    curve: { xTitle: 'Household income (£/year)', yTitle: 'Desired rent (£)' },
    buyBudget: { xTitle: 'Household income (£/year)', yTitle: 'Purchase budget (£)' },
    buyMultiplier: { xTitle: 'Budget multiplier (-)', yTitle: 'Probability density (1/unit)' }
  },
  btl_strategy_split: {
    scalar: { xTitle: 'Investor strategy parameter (-)', yTitle: 'Probability share (-)' },
    binned: { xTitle: 'Bin range (-)', yTitle: 'Value (-)', yDeltaTitle: 'Delta (-)' },
    joint: { xTitle: 'X bin (-)', yTitle: 'Y bin (-)', legendTitle: 'Probability mass (-)' },
    curve: { xTitle: 'Value (-)', yTitle: 'Density (1/unit)' },
    buyBudget: { xTitle: 'Household income (£/year)', yTitle: 'Purchase budget (£)' },
    buyMultiplier: { xTitle: 'Budget multiplier (-)', yTitle: 'Probability density (1/unit)' }
  },
  mortgage_duration_years: {
    scalar: { xTitle: 'Mortgage parameter (-)', yTitle: 'Duration (years)' },
    binned: { xTitle: 'Bin range (-)', yTitle: 'Value (-)', yDeltaTitle: 'Delta (-)' },
    joint: { xTitle: 'X bin (-)', yTitle: 'Y bin (-)', legendTitle: 'Probability mass (-)' },
    curve: { xTitle: 'Value (-)', yTitle: 'Density (1/unit)' },
    buyBudget: { xTitle: 'Household income (£/year)', yTitle: 'Purchase budget (£)' },
    buyMultiplier: { xTitle: 'Budget multiplier (-)', yTitle: 'Probability density (1/unit)' }
  },
  downpayment_ftb_lognormal: {
    scalar: { xTitle: 'Parameter (-)', yTitle: 'Value (-)' },
    binned: { xTitle: 'Bin range (-)', yTitle: 'Value (-)', yDeltaTitle: 'Delta (-)' },
    joint: { xTitle: 'X bin (-)', yTitle: 'Y bin (-)', legendTitle: 'Probability mass (-)' },
    curve: { xTitle: 'Down-payment (£)', yTitle: 'Probability density (1/£)' },
    buyBudget: { xTitle: 'Household income (£/year)', yTitle: 'Purchase budget (£)' },
    buyMultiplier: { xTitle: 'Budget multiplier (-)', yTitle: 'Probability density (1/unit)' }
  },
  downpayment_oo_lognormal: {
    scalar: { xTitle: 'Parameter (-)', yTitle: 'Value (-)' },
    binned: { xTitle: 'Bin range (-)', yTitle: 'Value (-)', yDeltaTitle: 'Delta (-)' },
    joint: { xTitle: 'X bin (-)', yTitle: 'Y bin (-)', legendTitle: 'Probability mass (-)' },
    curve: { xTitle: 'Down-payment (£)', yTitle: 'Probability density (1/£)' },
    buyBudget: { xTitle: 'Household income (£/year)', yTitle: 'Purchase budget (£)' },
    buyMultiplier: { xTitle: 'Budget multiplier (-)', yTitle: 'Probability density (1/unit)' }
  },
  market_average_price_decay: {
    scalar: { xTitle: 'Market pricing parameter (-)', yTitle: 'Decay factor (-)' },
    binned: { xTitle: 'Bin range (-)', yTitle: 'Value (-)', yDeltaTitle: 'Delta (-)' },
    joint: { xTitle: 'X bin (-)', yTitle: 'Y bin (-)', legendTitle: 'Probability mass (-)' },
    curve: { xTitle: 'Value (-)', yTitle: 'Density (1/unit)' },
    buyBudget: { xTitle: 'Household income (£/year)', yTitle: 'Purchase budget (£)' },
    buyMultiplier: { xTitle: 'Budget multiplier (-)', yTitle: 'Probability density (1/unit)' }
  },
  buy_quad: {
    scalar: { xTitle: 'Parameter (-)', yTitle: 'Value (-)' },
    binned: { xTitle: 'Bin range (-)', yTitle: 'Value (-)', yDeltaTitle: 'Delta (-)' },
    joint: { xTitle: 'X bin (-)', yTitle: 'Y bin (-)', legendTitle: 'Probability mass (-)' },
    curve: { xTitle: 'Value (-)', yTitle: 'Density (1/unit)' },
    buyBudget: { xTitle: 'Household income (£/year)', yTitle: 'Purchase budget (£)' },
    buyMultiplier: { xTitle: 'Budget multiplier (-)', yTitle: 'Probability density (1/unit)' }
  }
};

function hasUnitLabel(label: string): boolean {
  return /\(.+\)/.test(label);
}

function assertUnitLabel(label: string, key: string): void {
  if (!label.trim()) {
    throw new Error(`Axis label "${key}" must not be empty`);
  }
  if (label.toLowerCase().includes('native units')) {
    throw new Error(`Axis label "${key}" must not use generic native-units placeholder`);
  }
  if (!hasUnitLabel(label)) {
    throw new Error(`Axis label "${key}" must include explicit units in parentheses`);
  }
}

function assertAxisSpecValidity(id: string, spec: ChartAxisSpec): void {
  assertUnitLabel(spec.scalar.xTitle, `${id}.scalar.xTitle`);
  assertUnitLabel(spec.scalar.yTitle, `${id}.scalar.yTitle`);
  assertUnitLabel(spec.binned.xTitle, `${id}.binned.xTitle`);
  assertUnitLabel(spec.binned.yTitle, `${id}.binned.yTitle`);
  assertUnitLabel(spec.binned.yDeltaTitle, `${id}.binned.yDeltaTitle`);
  assertUnitLabel(spec.joint.xTitle, `${id}.joint.xTitle`);
  assertUnitLabel(spec.joint.yTitle, `${id}.joint.yTitle`);
  assertUnitLabel(spec.joint.legendTitle, `${id}.joint.legendTitle`);
  assertUnitLabel(spec.curve.xTitle, `${id}.curve.xTitle`);
  assertUnitLabel(spec.curve.yTitle, `${id}.curve.yTitle`);
  assertUnitLabel(spec.buyBudget.xTitle, `${id}.buyBudget.xTitle`);
  assertUnitLabel(spec.buyBudget.yTitle, `${id}.buyBudget.yTitle`);
  assertUnitLabel(spec.buyMultiplier.xTitle, `${id}.buyMultiplier.xTitle`);
  assertUnitLabel(spec.buyMultiplier.yTitle, `${id}.buyMultiplier.yTitle`);
}

export function getAxisSpec(parameterId: string): ChartAxisSpec {
  const spec = AXIS_SPECS[parameterId];
  if (!spec) {
    throw new Error(`Missing axis specification for parameter id "${parameterId}"`);
  }
  return spec;
}

export function assertAxisSpecComplete(parameterIds: string[] = PARAMETER_IDS): void {
  for (const id of parameterIds) {
    if (!AXIS_SPECS[id]) {
      throw new Error(`Missing chart axis spec for "${id}"`);
    }
  }
  for (const [id, spec] of Object.entries(AXIS_SPECS)) {
    assertAxisSpecValidity(id, spec);
  }
}

