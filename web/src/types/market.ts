export type QuantStatus = "success" | "partial" | "failure";
export type BreadthStatus = "available" | "insufficient_data";
export type TrendRegime =
  | "strong_uptrend"
  | "uptrend"
  | "transition"
  | "downtrend"
  | "strong_downtrend"
  | "insufficient_data";
export type SensitivityLabel =
  | "positive_significant"
  | "negative_significant"
  | "positive_not_significant"
  | "negative_not_significant"
  | "insufficient_data";
export type RegressionStatus = "success" | "insufficient_data";
export type InterpretationStatus = "available" | "unavailable";
export type InterpretationConfidence = "high" | "medium" | "low";

export interface DataSources {
  price_provider: string;
  treasury_provider: string;
  universe_provider: string;
}

export interface RunMetadata {
  run_id: string;
  as_of_date: string;
  generated_at: string;
  schema_version: "1.0.0";
  analysis_start: string;
  analysis_end: string;
  regression_window: number;
  min_regression_obs: number;
  moving_average_windows: number[];
  yield_unit: "percentage_points";
  data_sources: DataSources;
}

export interface DataQuality {
  requested_start: string;
  requested_end: string;
  equity_raw_row_count: number;
  equity_cleaned_row_count: number;
  available_equity_tickers: number;
  universe_size: number;
  latest_50dma_valid_count: number;
  latest_200dma_valid_count: number;
  spy_raw_row_count: number;
  spy_cleaned_row_count: number;
  spy_observation_count: number;
  dgs10_raw_row_count: number;
  dgs10_cleaned_row_count: number;
  dgs10_usable_observation_count: number;
  sector_raw_row_count: number;
  sector_cleaned_row_count: number;
  available_sector_tickers: number;
  sector_result_count: number;
  valid_sector_count: number;
  insufficient_sector_count: number;
  exclusions: string[];
  warnings: string[];
}

export interface BreadthSummary {
  as_of_date: string;
  pct_above_50dma: number | null;
  above_50dma_count: number;
  valid_count_50dma: number;
  pct_above_200dma: number | null;
  above_200dma_count: number;
  valid_count_200dma: number;
  advancers: number;
  decliners: number;
  valid_return_count: number;
  advance_decline_ratio: number | null;
  net_advances: number;
  breadth_momentum_20d: number | null;
  status: BreadthStatus;
  unavailable_fields: string[];
}

export interface TrendSummary {
  as_of_date: string;
  adjusted_close: number;
  sma_20: number | null;
  sma_50: number | null;
  sma_200: number | null;
  distance_to_sma_20: number | null;
  distance_to_sma_50: number | null;
  distance_to_sma_200: number | null;
  trend_regime: TrendRegime;
}

export interface SectorRegressionSummary {
  ticker: string;
  alpha: number | null;
  beta_yield: number | null;
  beta_std_error: number | null;
  beta_t_value: number | null;
  p_value: number | null;
  ci_95_lower: number | null;
  ci_95_upper: number | null;
  r_squared: number | null;
  adjusted_r_squared: number | null;
  n_obs: number;
  start_date: string | null;
  end_date: string | null;
  effect_10bp: number | null;
  sensitivity_label: SensitivityLabel;
  status: RegressionStatus;
  error_reason: string | null;
}

export interface QuantSummary {
  schema_version: "1.0.0";
  run_metadata: RunMetadata;
  data_quality: DataQuality;
  breadth: BreadthSummary;
  trend: TrendSummary;
  sector_regressions: SectorRegressionSummary[];
  limitations: string[];
  status: QuantStatus;
}

export interface EvidenceItem {
  metric: string;
  value: string | number | null;
  source_section: string;
}

export interface InterpretationSection {
  summary: string;
  evidence: EvidenceItem[];
  confidence: InterpretationConfidence;
}

export interface MarketInterpretation {
  run_id: string;
  as_of_date: string;
  status: InterpretationStatus;
  reason: string | null;
  market_regime_summary: InterpretationSection | null;
  breadth_interpretation: InterpretationSection | null;
  trend_interpretation: InterpretationSection | null;
  rates_and_sectors_interpretation: InterpretationSection | null;
  key_confirmed_signals: string[];
  key_uncertainties: string[];
  risk_flags: string[];
  evidence_used: EvidenceItem[];
  evidence: EvidenceItem[];
  executive_summary: string | null;
  market_participation: string | null;
  trend_conditions: string | null;
  sector_rate_risk: string | null;
  risks_and_limitations: string | null;
  disclaimer: string | null;
  model: string | null;
  generated_at: string;
}

export type MarketSummary = MarketInterpretation;

export interface SnapshotManifest {
  schema_version: string;
  run_id: string;
  as_of_date: string;
  generated_at: string;
  quant_status: QuantStatus;
  interpretation_status: InterpretationStatus;
  artifacts: {
    quant_summary: string;
    market_summary: string;
    breadth_timeseries: string;
    trend_timeseries: string;
  };
}

export interface BreadthTimeseriesPoint {
  date: string;
  pct_above_50dma: number | null;
  pct_above_200dma: number | null;
  advancers: number | null;
  decliners: number | null;
  advance_decline_ratio: number | null;
  net_advances: number | null;
  breadth_momentum_20d: number | null;
}

export interface BreadthTimeseries {
  schema_version: string;
  run_id: string;
  as_of_date: string;
  series: BreadthTimeseriesPoint[];
}

export interface TrendTimeseriesPoint {
  date: string;
  adjusted_close: number;
  sma_20: number | null;
  sma_50: number | null;
  sma_200: number | null;
  trend_regime: TrendRegime;
}

export interface TrendTimeseries {
  schema_version: string;
  run_id: string;
  as_of_date: string;
  series: TrendTimeseriesPoint[];
}

export interface SnapshotLoadError {
  file: string;
  message: string;
}

export interface DashboardSnapshot {
  quant: QuantSummary | null;
  market: MarketInterpretation | null;
  manifest: SnapshotManifest | null;
  breadthSeries: BreadthTimeseries | null;
  trendSeries: TrendTimeseries | null;
  errors: SnapshotLoadError[];
  snapshotConsistent: boolean;
}
