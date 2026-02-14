import type { ParameterCardMeta } from './types';

export const PARAMETER_CATALOG: ParameterCardMeta[] = [
  {
    id: 'income_given_age_joint',
    title: 'How Gross Income Is Distributed Across Age Groups',
    group: 'Household Demographics & Wealth',
    format: 'joint_distribution',
    configKeys: ['DATA_INCOME_GIVEN_AGE'],
    dataFileConfigKeys: ['DATA_INCOME_GIVEN_AGE'],
    explanation:
      'This joint distribution maps age bands to logarithmic gross-income bands. Shifts toward higher-income bins increase households\' purchasing capacity and can amplify demand pressure in owner-occupier and rental decisions. Changes in low-income mass can increase vulnerability to affordability constraints.'
  },
  {
    id: 'wealth_given_income_joint',
    title: 'How Household Wealth Is Distributed Across Income Groups',
    group: 'Household Demographics & Wealth',
    format: 'joint_distribution',
    configKeys: ['DATA_WEALTH_GIVEN_INCOME'],
    dataFileConfigKeys: ['DATA_WEALTH_GIVEN_INCOME'],
    explanation:
      'This matrix links gross-income bins to net-wealth bins. More mass in higher-wealth cells implies larger available buffers and greater ability to meet down-payment requirements. Lower-wealth concentration tends to tighten borrowing constraints and reduce transaction flexibility.'
  },
  {
    id: 'btl_probability_bins',
    title: 'Buy-to-Let Investor Probability by Income Percentile',
    group: 'BTL & Investor Behavior',
    format: 'binned_distribution',
    configKeys: ['DATA_BTL_PROBABILITY'],
    dataFileConfigKeys: ['DATA_BTL_PROBABILITY'],
    explanation:
      'This binned series sets the baseline probability of a household being a buy-to-let investor by income percentile. Higher probabilities in upper percentiles increase investor participation and potential competition with owner-occupiers. Lower values reduce investor-driven demand in the housing market.'
  },
  {
    id: 'age_distribution',
    title: 'Household Population Share by Age Group',
    group: 'Household Demographics & Wealth',
    format: 'binned_distribution',
    configKeys: ['DATA_AGE_DISTRIBUTION'],
    dataFileConfigKeys: ['DATA_AGE_DISTRIBUTION'],
    explanation:
      'This distribution controls household density by age band. It affects how many agents are likely to be entering, moving within, or exiting ownership and rental pathways. Age-mix shifts can indirectly change mortgage demand, tenure transitions, and portfolio turnover.'
  },
  {
    id: 'national_insurance_rates',
    title: 'National Insurance Rates Across Income Thresholds',
    group: 'Government & Tax',
    format: 'binned_distribution',
    configKeys: ['DATA_NATIONAL_INSURANCE_RATES'],
    dataFileConfigKeys: ['DATA_NATIONAL_INSURANCE_RATES'],
    explanation:
      'These NI contribution bands map income thresholds to marginal rates. Higher effective deductions reduce disposable income and may weaken affordability for rent and mortgage payments. Lower deductions increase net income and can support stronger effective demand.'
  },
  {
    id: 'income_tax_rates',
    title: 'Income Tax Rates Across Income Thresholds',
    group: 'Government & Tax',
    format: 'binned_distribution',
    configKeys: ['DATA_TAX_RATES'],
    dataFileConfigKeys: ['DATA_TAX_RATES'],
    explanation:
      'Tax bands define marginal tax rates across taxable income levels. Higher rates or earlier threshold transitions reduce post-tax income and can compress housing budgets. Lower tax burden increases spendable income and may relax affordability pressure.'
  },
  {
    id: 'government_allowance_support',
    title: 'Government Personal Allowance and Monthly Income Support',
    group: 'Government & Tax',
    format: 'scalar_pair',
    configKeys: ['GOVERNMENT_GENERAL_PERSONAL_ALLOWANCE', 'GOVERNMENT_MONTHLY_INCOME_SUPPORT'],
    explanation:
      'Personal allowance influences taxable income, while monthly income support sets a floor for low-income households. Increases generally improve disposable-income resilience and can reduce financial stress in consumption and housing decisions. Decreases have the opposite effect and may tighten constraints.'
  },
  {
    id: 'house_price_lognormal',
    title: 'House Price Distribution Shape (Scale and Spread)',
    group: 'Housing & Rental Market',
    format: 'lognormal_pair',
    configKeys: ['HOUSE_PRICES_SCALE', 'HOUSE_PRICES_SHAPE'],
    explanation:
      'These parameters define the lognormal distribution used for house prices. A higher scale shifts the overall price level upward, while a higher shape increases dispersion and tail weight. Together they influence affordability, leverage needs, and transaction stratification by budget.'
  },
  {
    id: 'rental_price_lognormal',
    title: 'Rental Price Distribution Shape (Scale and Spread)',
    group: 'Housing & Rental Market',
    format: 'lognormal_pair',
    configKeys: ['RENTAL_PRICES_SCALE', 'RENTAL_PRICES_SHAPE'],
    explanation:
      'These parameters define the lognormal distribution of rental prices. Higher scale raises typical rent levels, and higher shape broadens rent dispersion across properties. This can alter rental affordability and tenure decisions between renting and buying.'
  },
  {
    id: 'desired_rent_power',
    title: 'Desired Rent as Income Changes (Power Curve)',
    group: 'Housing & Rental Market',
    format: 'power_law_pair',
    configKeys: ['DESIRED_RENT_SCALE', 'DESIRED_RENT_EXPONENT'],
    explanation:
      'Desired rent is modeled as a power function of income. Increasing scale lifts rent willingness at all income levels, while increasing exponent steepens the response for higher incomes. This affects bid intensity in the rental market and competitive pressure on rental prices.'
  },
  {
    id: 'btl_strategy_split',
    title: 'Buy-to-Let Strategy Mix: Income Yield vs Capital Growth',
    group: 'BTL & Investor Behavior',
    format: 'scalar_pair',
    configKeys: ['BTL_P_INCOME_DRIVEN', 'BTL_P_CAPITAL_DRIVEN'],
    explanation:
      'These probabilities set how many BTL investors primarily target rental income versus capital gains. A higher capital-driven share can increase sensitivity to expected price appreciation. A higher income-driven share emphasizes yield and may stabilize behavior toward rental cash flow.'
  },
  {
    id: 'mortgage_duration_years',
    title: 'Typical Mortgage Term Length (Years)',
    group: 'Purchase & Mortgage',
    format: 'scalar',
    configKeys: ['MORTGAGE_DURATION_YEARS'],
    explanation:
      'Mortgage duration governs repayment horizon for loans. Longer terms reduce monthly repayments for a given principal, potentially easing affordability checks and raising feasible loan sizes. Shorter terms do the reverse and can tighten borrowing capacity.'
  },
  {
    id: 'downpayment_ftb_lognormal',
    title: 'First-Time Buyer Down-Payment Distribution',
    group: 'Purchase & Mortgage',
    format: 'lognormal_pair',
    configKeys: ['DOWNPAYMENT_FTB_SCALE', 'DOWNPAYMENT_FTB_SHAPE'],
    explanation:
      'These parameters control the first-time-buyer down-payment distribution. Higher scale generally implies larger typical down-payments, while higher shape increases dispersion across households. This directly affects entry feasibility and loan-to-value dynamics for FTB cohorts.'
  },
  {
    id: 'downpayment_oo_lognormal',
    title: 'Owner-Occupier Down-Payment Distribution',
    group: 'Purchase & Mortgage',
    format: 'lognormal_pair',
    configKeys: ['DOWNPAYMENT_OO_SCALE', 'DOWNPAYMENT_OO_SHAPE'],
    explanation:
      'These parameters define down-payment behavior for owner-occupiers beyond first-time buyers. Higher scale increases typical equity contribution at purchase, while higher shape broadens variation between households. This influences leverage, mortgage demand, and transaction pacing.'
  },
  {
    id: 'market_average_price_decay',
    title: 'Speed of Market Average Price Adjustment',
    group: 'Housing & Rental Market',
    format: 'scalar',
    configKeys: ['MARKET_AVERAGE_PRICE_DECAY'],
    explanation:
      'This decay constant sets the responsiveness of the moving average used for market prices. Higher values make average-price signals adapt faster to new transactions, while lower values smooth shocks and delay adjustment. It influences short-run dynamics and expectation feedback.'
  },
  {
    id: 'buy_quad',
    title: 'Purchase Budget Curve and Bid Variation Noise',
    group: 'Purchase & Mortgage',
    format: 'buy_quad',
    configKeys: ['BUY_SCALE', 'BUY_EXPONENT', 'BUY_MU', 'BUY_SIGMA'],
    explanation:
      'This combined set defines desired purchase budget as a power function of income, multiplied by a lognormal noise term. Scale and exponent shape deterministic budget growth with income, while mu and sigma govern multiplicative variation between similar households. Larger sigma creates wider bid dispersion and can increase price-outcome heterogeneity.'
  }
];

export const PARAMETER_IDS = PARAMETER_CATALOG.map((entry) => entry.id);
