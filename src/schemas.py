"""Validated Pydantic contracts for deterministic quantitative output."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0.0"

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
Percentage = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class QuantStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"


class BreadthStatus(StrEnum):
    AVAILABLE = "available"
    INSUFFICIENT_DATA = "insufficient_data"


class TrendRegime(StrEnum):
    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    TRANSITION = "transition"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"
    INSUFFICIENT_DATA = "insufficient_data"


class SensitivityLabel(StrEnum):
    POSITIVE_SIGNIFICANT = "positive_significant"
    NEGATIVE_SIGNIFICANT = "negative_significant"
    POSITIVE_NOT_SIGNIFICANT = "positive_not_significant"
    NEGATIVE_NOT_SIGNIFICANT = "negative_not_significant"
    INSUFFICIENT_DATA = "insufficient_data"


class RegressionStatus(StrEnum):
    SUCCESS = "success"
    INSUFFICIENT_DATA = "insufficient_data"


class OutputModel(BaseModel):
    """Strictly shaped immutable output model."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class DataSources(OutputModel):
    price_provider: str = Field(min_length=1)
    treasury_provider: str = Field(min_length=1)
    universe_provider: str = Field(min_length=1)


class RunMetadata(OutputModel):
    run_id: str = Field(min_length=1)
    as_of_date: date
    generated_at: datetime
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    analysis_start: date
    analysis_end: date
    regression_window: int = Field(gt=0)
    min_regression_obs: int = Field(gt=0)
    moving_average_windows: list[int] = Field(min_length=1)
    yield_unit: Literal["percentage_points"]
    data_sources: DataSources

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value

    @field_validator("moving_average_windows")
    @classmethod
    def validate_windows(cls, windows: list[int]) -> list[int]:
        if any(window <= 0 for window in windows):
            raise ValueError("moving-average windows must be positive")
        if len(set(windows)) != len(windows):
            raise ValueError("moving-average windows must be unique")
        return windows

    @model_validator(mode="after")
    def validate_ranges(self) -> RunMetadata:
        if self.analysis_start > self.analysis_end:
            raise ValueError("analysis_start must not exceed analysis_end")
        if not self.analysis_start <= self.as_of_date <= self.analysis_end:
            raise ValueError("as_of_date must fall within the analysis range")
        if self.min_regression_obs > self.regression_window:
            raise ValueError("min_regression_obs must not exceed regression_window")
        return self


class DataQuality(OutputModel):
    requested_start: date
    requested_end: date
    equity_raw_row_count: NonNegativeInt
    equity_cleaned_row_count: NonNegativeInt
    available_equity_tickers: NonNegativeInt
    universe_size: NonNegativeInt
    latest_50dma_valid_count: NonNegativeInt
    latest_200dma_valid_count: NonNegativeInt
    spy_raw_row_count: NonNegativeInt
    spy_cleaned_row_count: NonNegativeInt
    spy_observation_count: NonNegativeInt
    dgs10_raw_row_count: NonNegativeInt
    dgs10_cleaned_row_count: NonNegativeInt
    dgs10_usable_observation_count: NonNegativeInt
    sector_raw_row_count: NonNegativeInt
    sector_cleaned_row_count: NonNegativeInt
    available_sector_tickers: NonNegativeInt
    sector_result_count: NonNegativeInt
    valid_sector_count: NonNegativeInt
    insufficient_sector_count: NonNegativeInt
    exclusions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_counts(self) -> DataQuality:
        if self.requested_start > self.requested_end:
            raise ValueError("requested_start must not exceed requested_end")
        if (
            self.valid_sector_count + self.insufficient_sector_count
            != self.sector_result_count
        ):
            raise ValueError("sector result counts are inconsistent")
        if self.available_equity_tickers > self.universe_size:
            raise ValueError("available equity tickers exceed universe size")
        return self


class BreadthSummary(OutputModel):
    as_of_date: date
    pct_above_50dma: Percentage | None
    above_50dma_count: NonNegativeInt
    valid_count_50dma: NonNegativeInt
    pct_above_200dma: Percentage | None
    above_200dma_count: NonNegativeInt
    valid_count_200dma: NonNegativeInt
    advancers: NonNegativeInt
    decliners: NonNegativeInt
    valid_return_count: NonNegativeInt
    advance_decline_ratio: FiniteFloat | None
    net_advances: int
    breadth_momentum_20d: FiniteFloat | None
    status: BreadthStatus
    unavailable_fields: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_breadth(self) -> BreadthSummary:
        if self.above_50dma_count > self.valid_count_50dma:
            raise ValueError("above_50dma_count exceeds valid_count_50dma")
        if self.above_200dma_count > self.valid_count_200dma:
            raise ValueError("above_200dma_count exceeds valid_count_200dma")
        if self.advancers + self.decliners > self.valid_return_count:
            raise ValueError("advance/decline counts exceed valid returns")
        if self.net_advances != self.advancers - self.decliners:
            raise ValueError("net_advances is inconsistent")
        if self.valid_count_50dma == 0 and self.pct_above_50dma is not None:
            raise ValueError("50dma percentage requires a valid denominator")
        if self.valid_count_200dma == 0 and self.pct_above_200dma is not None:
            raise ValueError("200dma percentage requires a valid denominator")
        return self


class TrendSummary(OutputModel):
    as_of_date: date
    adjusted_close: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    sma_20: FiniteFloat | None
    sma_50: FiniteFloat | None
    sma_200: FiniteFloat | None
    distance_to_sma_20: FiniteFloat | None
    distance_to_sma_50: FiniteFloat | None
    distance_to_sma_200: FiniteFloat | None
    trend_regime: TrendRegime


class SectorRegressionSummary(OutputModel):
    ticker: str = Field(min_length=1)
    alpha: FiniteFloat | None
    beta_yield: FiniteFloat | None
    beta_std_error: Annotated[float | None, Field(ge=0, allow_inf_nan=False)]
    beta_t_value: FiniteFloat | None
    p_value: Annotated[float | None, Field(ge=0, le=1, allow_inf_nan=False)]
    ci_95_lower: FiniteFloat | None
    ci_95_upper: FiniteFloat | None
    r_squared: Annotated[float | None, Field(ge=0, le=1, allow_inf_nan=False)]
    adjusted_r_squared: FiniteFloat | None
    n_obs: NonNegativeInt
    start_date: date | None
    end_date: date | None
    effect_10bp: FiniteFloat | None
    sensitivity_label: SensitivityLabel
    status: RegressionStatus
    error_reason: str | None

    @model_validator(mode="after")
    def validate_regression(self) -> SectorRegressionSummary:
        inferential_fields = (
            "alpha",
            "beta_yield",
            "beta_std_error",
            "beta_t_value",
            "p_value",
            "ci_95_lower",
            "ci_95_upper",
            "r_squared",
            "adjusted_r_squared",
            "effect_10bp",
        )
        values = [getattr(self, field) for field in inferential_fields]
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("regression dates must both be present or absent")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("regression start_date must not exceed end_date")

        if self.status == RegressionStatus.SUCCESS:
            if any(value is None for value in values):
                raise ValueError("successful regression requires all statistics")
            if self.sensitivity_label == SensitivityLabel.INSUFFICIENT_DATA:
                raise ValueError("successful regression requires a valid label")
            assert self.beta_yield is not None
            assert self.ci_95_lower is not None
            assert self.ci_95_upper is not None
            if self.ci_95_lower > self.ci_95_upper:
                raise ValueError("regression confidence interval is reversed")
            if not self.ci_95_lower <= self.beta_yield <= self.ci_95_upper:
                raise ValueError("beta_yield lies outside its confidence interval")
        else:
            if self.sensitivity_label != SensitivityLabel.INSUFFICIENT_DATA:
                raise ValueError("insufficient regression requires matching label")
            if any(value is not None for value in values):
                raise ValueError("insufficient regression statistics must remain null")
        return self


class QuantSummary(OutputModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    run_metadata: RunMetadata
    data_quality: DataQuality
    breadth: BreadthSummary
    trend: TrendSummary
    sector_regressions: list[SectorRegressionSummary] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    status: QuantStatus

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, limitations: list[str]) -> list[str]:
        if any(not limitation.strip() for limitation in limitations):
            raise ValueError("limitations must not contain empty strings")
        return limitations

    @model_validator(mode="after")
    def validate_summary(self) -> QuantSummary:
        if self.run_metadata.schema_version != self.schema_version:
            raise ValueError("metadata schema version does not match summary")
        tickers = [record.ticker for record in self.sector_regressions]
        if len(set(tickers)) != len(tickers):
            raise ValueError("sector regression tickers must be unique")
        return self


class InterpretationStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class InterpretationConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceReference(OutputModel):
    metric: str = Field(min_length=1)
    value: str | int | float | None = None
    source_section: str = Field(min_length=1)


class InterpretationSection(OutputModel):
    summary: str = Field(min_length=1)
    evidence: list[EvidenceReference] = Field(min_length=1)
    confidence: InterpretationConfidence


class LLMInterpretationPayload(OutputModel):
    """Structured model response; run identity is stamped by the pipeline."""

    market_regime_summary: InterpretationSection
    breadth_interpretation: InterpretationSection
    trend_interpretation: InterpretationSection
    rates_and_sectors_interpretation: InterpretationSection
    key_confirmed_signals: list[str]
    key_uncertainties: list[str]
    risk_flags: list[str]
    evidence_used: list[EvidenceReference] = Field(min_length=1)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    executive_summary: str | None = None
    market_participation: str | None = None
    trend_conditions: str | None = None
    sector_rate_risk: str | None = None
    risks_and_limitations: str | None = None
    disclaimer: str | None = None


class MarketInterpretation(OutputModel):
    run_id: str = Field(min_length=1)
    as_of_date: date
    status: InterpretationStatus
    reason: str | None = None
    market_regime_summary: InterpretationSection | None = None
    breadth_interpretation: InterpretationSection | None = None
    trend_interpretation: InterpretationSection | None = None
    rates_and_sectors_interpretation: InterpretationSection | None = None
    key_confirmed_signals: list[str] = Field(default_factory=list)
    key_uncertainties: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    evidence_used: list[EvidenceReference] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    executive_summary: str | None = None
    market_participation: str | None = None
    trend_conditions: str | None = None
    sector_rate_risk: str | None = None
    risks_and_limitations: str | None = None
    disclaimer: str | None = None
    model: str | None = None
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_availability(self) -> MarketInterpretation:
        sections = (
            self.market_regime_summary,
            self.breadth_interpretation,
            self.trend_interpretation,
            self.rates_and_sectors_interpretation,
        )
        if self.status == InterpretationStatus.AVAILABLE:
            if self.reason is not None:
                raise ValueError("available interpretation must not include a reason")
            if self.model is None or not self.model.strip():
                raise ValueError("available interpretation requires a model name")
            if any(section is None for section in sections):
                raise ValueError("available interpretation requires all sections")
            canonical = (
                self.executive_summary,
                self.market_participation,
                self.trend_conditions,
                self.sector_rate_risk,
                self.risks_and_limitations,
                self.disclaimer,
            )
            if any(item is None or not item.strip() for item in canonical):
                raise ValueError(
                    "available interpretation requires canonical specification fields"
                )
            if not self.evidence_used and not self.evidence:
                raise ValueError("available interpretation requires evidence")
            if self.evidence_used and not self.evidence:
                return self.model_copy(update={"evidence": list(self.evidence_used)})
            if self.evidence and not self.evidence_used:
                return self.model_copy(update={"evidence_used": list(self.evidence)})
        else:
            if not self.reason:
                raise ValueError("unavailable interpretation requires a reason")
            if any(section is not None for section in sections):
                raise ValueError("unavailable interpretation must not include sections")
            if (
                self.key_confirmed_signals
                or self.key_uncertainties
                or self.risk_flags
                or self.evidence_used
                or self.evidence
                or self.executive_summary
                or self.market_participation
                or self.trend_conditions
                or self.sector_rate_risk
                or self.risks_and_limitations
                or self.disclaimer
            ):
                raise ValueError(
                    "unavailable interpretation must not invent commentary"
                )
        return self
