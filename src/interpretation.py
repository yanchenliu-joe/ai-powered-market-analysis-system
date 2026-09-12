"""Grounded OpenAI interpretation of validated quantitative summaries."""

from __future__ import annotations

import json
import logging
import math
import os
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.schemas import (
    InterpretationStatus,
    LLMInterpretationPayload,
    MarketInterpretation,
    QuantSummary,
)

MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 30.0
DEFAULT_BACKOFF_SECONDS = 0.5
NUMERIC_REL_TOL = 1e-4
NUMERIC_ABS_TOL = 1e-6
LOGGER = logging.getLogger(__name__)

SYSTEM_PROMPT = "\n".join(
    [
        "You are a market interpretation layer operating on validated "
        "quantitative evidence.",
        "",
        "Rules:",
        "- Use only the supplied quantitative evidence pack.",
        "- Do not infer unavailable values or treat insufficient-data records "
        "as zero or neutral.",
        "- Do not invent market prices, yields, dates, sectors, returns, or "
        "statistics.",
        "- Do not recompute indicators, moving averages, regressions, or "
        "confidence intervals.",
        "- Do not claim causality; sector-rate results describe statistical "
        "association and exposure.",
        "- Distinguish significant sector-rate relationships from "
        "non-significant results using the supplied sensitivity_label values "
        "exactly.",
        "- Preserve accepted trend_regime and sensitivity_label enumerations "
        "exactly; do not reinterpret them.",
        "- Explicitly mention uncertainty when evidence is incomplete.",
        "- Explain what the validated signals collectively suggest, not what "
        "outside market knowledge would imply.",
        "- Do not give investment advice, forecasts, or trading " "recommendations.",
        "- Return only the requested structured sections. Each section "
        "summary must cite evidence that exists in the evidence pack.",
        "- Also populate specification fields: executive_summary, "
        "market_participation, trend_conditions, sector_rate_risk, "
        "risks_and_limitations, evidence, and disclaimer.",
        "",
        "Evidence reference contract:",
        "- Every evidence item must use source_section and metric exactly as "
        "they appear in the evidence pack. Do not shorten, rename, or invent "
        "aliases such as trend, sectors, or quant_summary.",
        "- Allowed source_section values: breadth, spy_trend, "
        "sector_rate_sensitivity, run_metadata.",
        "- Breadth example: source_section=breadth, metric=pct_above_50dma.",
        "- Trend example: source_section=spy_trend, metric=trend_regime.",
        "- Sector example: source_section=sector_rate_sensitivity, "
        "metric=XLK.beta_yield. Do not cite a ticker alone or beta_yield "
        "without the ticker prefix.",
        "- Run metadata example: source_section=run_metadata, " "metric=as_of_date.",
        "- Use only paths present in the provided evidence pack.",
        "- Evidence values must come directly from the evidence pack. Prose "
        "may round numbers for readability, but evidence values should "
        "preserve the pack value as closely as possible.",
    ]
)

CompleteFn = Callable[[list[dict[str, str]], str, float], dict[str, Any]]


class InterpretationError(RuntimeError):
    """Raised for retryable structured-response or provider failures."""

    stage = "groundedness"


class EmptyStructuredResponseError(InterpretationError):
    """Raised when structured parse returns no parsed object."""

    stage = "empty_parsed"


def build_evidence_pack(summary: QuantSummary) -> dict[str, Any]:
    """Build a deterministic evidence payload from a validated QuantSummary."""

    breadth = summary.breadth
    trend = summary.trend
    return {
        "run_id": summary.run_metadata.run_id,
        "as_of_date": summary.run_metadata.as_of_date.isoformat(),
        "quant_status": summary.status.value,
        "yield_unit": summary.run_metadata.yield_unit,
        "limitations": list(summary.limitations),
        "breadth": {
            "as_of_date": breadth.as_of_date.isoformat(),
            "pct_above_50dma": breadth.pct_above_50dma,
            "above_50dma_count": breadth.above_50dma_count,
            "valid_count_50dma": breadth.valid_count_50dma,
            "pct_above_200dma": breadth.pct_above_200dma,
            "above_200dma_count": breadth.above_200dma_count,
            "valid_count_200dma": breadth.valid_count_200dma,
            "advancers": breadth.advancers,
            "decliners": breadth.decliners,
            "valid_return_count": breadth.valid_return_count,
            "advance_decline_ratio": breadth.advance_decline_ratio,
            "net_advances": breadth.net_advances,
            "breadth_momentum_20d": breadth.breadth_momentum_20d,
            "status": breadth.status.value,
        },
        "spy_trend": {
            "as_of_date": trend.as_of_date.isoformat(),
            "adjusted_close": trend.adjusted_close,
            "sma_20": trend.sma_20,
            "sma_50": trend.sma_50,
            "sma_200": trend.sma_200,
            "distance_to_sma_20": trend.distance_to_sma_20,
            "distance_to_sma_50": trend.distance_to_sma_50,
            "distance_to_sma_200": trend.distance_to_sma_200,
            "trend_regime": trend.trend_regime.value,
        },
        "sector_rate_sensitivity": [
            {
                "sector": record.ticker,
                "beta_yield": record.beta_yield,
                "ci_95_lower": record.ci_95_lower,
                "ci_95_upper": record.ci_95_upper,
                "p_value": record.p_value,
                "effect_10bp": record.effect_10bp,
                "n_obs": record.n_obs,
                "sensitivity_label": record.sensitivity_label.value,
                "status": record.status.value,
            }
            for record in summary.sector_regressions
        ],
    }


def allowed_evidence_index(pack: dict[str, Any]) -> dict[tuple[str, str], Any]:
    """Map (source_section, metric) pairs to values present in the evidence pack."""

    allowed: dict[tuple[str, str], Any] = {}
    for section_name in ("breadth", "spy_trend"):
        section = pack[section_name]
        for metric, value in section.items():
            allowed[(section_name, metric)] = value
    for record in pack["sector_rate_sensitivity"]:
        sector = record["sector"]
        for metric, value in record.items():
            if metric == "sector":
                continue
            allowed[("sector_rate_sensitivity", f"{sector}.{metric}")] = value
    allowed[("run_metadata", "as_of_date")] = pack["as_of_date"]
    allowed[("run_metadata", "quant_status")] = pack["quant_status"]
    allowed[("run_metadata", "yield_unit")] = pack["yield_unit"]
    return allowed


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            return None
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped.lower() in {"true", "false"}:
            return None
        try:
            number = float(stripped)
        except ValueError:
            return None
        if not math.isfinite(number):
            return None
        return number
    return None


def _cited_decimal_places(value: float) -> int:
    text = format(value, ".12f").rstrip("0").rstrip(".")
    if "." not in text:
        return 0
    return min(len(text.split(".", 1)[1]), 12)


def _numeric_values_equivalent(cited: float, expected: float) -> bool:
    if math.isclose(cited, expected, rel_tol=NUMERIC_REL_TOL, abs_tol=NUMERIC_ABS_TOL):
        return True
    places = _cited_decimal_places(cited)
    return math.isclose(cited, round(expected, places), rel_tol=0.0, abs_tol=0.0)


def _values_equivalent(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, bool) or isinstance(right, bool):
        return left == right
    cited = _as_number(left)
    expected = _as_number(right)
    if cited is not None and expected is not None:
        return _numeric_values_equivalent(cited, expected)
    return str(left) == str(right)


def validate_grounded_payload(
    payload: LLMInterpretationPayload, pack: dict[str, Any]
) -> None:
    """Reject evidence references that are not present in the evidence pack."""

    allowed = allowed_evidence_index(pack)
    references = list(payload.evidence_used)
    for section in (
        payload.market_regime_summary,
        payload.breadth_interpretation,
        payload.trend_interpretation,
        payload.rates_and_sectors_interpretation,
    ):
        references.extend(section.evidence)
    for reference in references:
        key = (reference.source_section, reference.metric)
        if key not in allowed:
            raise InterpretationError(
                f"ungrounded evidence reference: {reference.source_section}."
                f"{reference.metric}"
            )
        if not _values_equivalent(reference.value, allowed[key]):
            raise InterpretationError(
                "evidence value mismatch: "
                f"{reference.source_section}.{reference.metric}"
            )


def serialize_evidence_pack(pack: dict[str, Any]) -> str:
    return json.dumps(pack, allow_nan=False, indent=2, sort_keys=True) + "\n"


def build_messages(pack: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Interpret the following validated quantitative evidence pack. "
                "Cite only pack fields using the evidence reference contract.\n\n"
                + serialize_evidence_pack(pack)
            ),
        },
    ]


def _unavailable(
    summary: QuantSummary,
    reason: str,
    *,
    generated_at: datetime,
    model: str | None = None,
) -> MarketInterpretation:
    return MarketInterpretation(
        run_id=summary.run_metadata.run_id,
        as_of_date=summary.run_metadata.as_of_date,
        status=InterpretationStatus.UNAVAILABLE,
        reason=reason,
        generated_at=generated_at,
        model=model,
    )


def _is_retryable(error: Exception) -> bool:
    retryable_names = {
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
        "RateLimitError",
        "TimeoutError",
    }
    if type(error).__name__ in retryable_names:
        return True
    return isinstance(
        error,
        (TimeoutError, ConnectionError, InterpretationError, ValidationError),
    )


def _failure_stage(error: Exception) -> str:
    if isinstance(error, EmptyStructuredResponseError):
        return "empty_parsed"
    if isinstance(error, InterpretationError):
        return "groundedness"
    if isinstance(error, ValidationError):
        return "pydantic"
    if type(error).__name__ in {
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
        "RateLimitError",
        "TimeoutError",
        "ConnectionError",
    } or isinstance(error, (TimeoutError, ConnectionError)):
        return "structured_parsing"
    return "structured_parsing"


def _sanitize_diagnostic(error: Exception) -> str:
    text = f"{type(error).__name__}: {error}"
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "[redacted]", text)
    text = re.sub(
        r"(?i)(openai_api_key|api[_-]?key)\s*[:=]\s*\S+",
        r"\1=[redacted]",
        text,
    )
    return text.replace("\n", " ")[:300]


def _log_attempt_failure(attempt: int, error: Exception) -> None:
    LOGGER.info(
        "attempt=%s stage=%s error=%s",
        attempt,
        _failure_stage(error),
        _sanitize_diagnostic(error),
    )


def _live_complete(
    messages: list[dict[str, str]], model: str, timeout_seconds: float
) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=timeout_seconds)
    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=LLMInterpretationPayload,
            temperature=0,
        )
    except AttributeError:
        completion = client.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=LLMInterpretationPayload,
            temperature=0,
        )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise EmptyStructuredResponseError("structured response was empty")
    return parsed.model_dump(mode="json")


def _resolve_model(model: str | None) -> str | None:
    if model:
        return model
    return os.getenv("OPENAI_MODEL")


DEFAULT_DISCLAIMER = (
    "This report is for research and educational purposes only and does not "
    "constitute investment advice."
)
SKIPPED_REASON = "skipped"


def _canonical_text(payload: LLMInterpretationPayload) -> dict[str, str]:
    return {
        "executive_summary": (
            payload.executive_summary or payload.market_regime_summary.summary
        ),
        "market_participation": (
            payload.market_participation or payload.breadth_interpretation.summary
        ),
        "trend_conditions": (
            payload.trend_conditions or payload.trend_interpretation.summary
        ),
        "sector_rate_risk": (
            payload.sector_rate_risk or payload.rates_and_sectors_interpretation.summary
        ),
        "risks_and_limitations": (
            payload.risks_and_limitations
            or " ".join(payload.key_uncertainties)
            or "Sector regressions estimate statistical association, not causation."
        ),
        "disclaimer": payload.disclaimer or DEFAULT_DISCLAIMER,
    }


def interpret_quant_summary(
    summary: QuantSummary,
    *,
    output_directory: str | Path | None = None,
    model: str | None = None,
    api_key: str | None = None,
    complete: CompleteFn | None = None,
    generated_at: datetime | None = None,
    max_attempts: int = MAX_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
    timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    skip: bool = False,
) -> MarketInterpretation:
    """Interpret a validated QuantSummary without failing the quantitative run."""

    resolved_generated_at = generated_at or datetime.now(UTC)
    resolved_model = _resolve_model(model)
    resolved_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")
    pack = build_evidence_pack(summary)

    if skip:
        interpretation = _unavailable(
            summary, SKIPPED_REASON, generated_at=resolved_generated_at
        )
        if output_directory is not None:
            write_market_summary(interpretation, output_directory)
        return interpretation
    if not resolved_key and complete is None:
        interpretation = _unavailable(
            summary, "missing_api_key", generated_at=resolved_generated_at
        )
        if output_directory is not None:
            write_market_summary(interpretation, output_directory)
        return interpretation
    if not resolved_model and complete is None:
        interpretation = _unavailable(
            summary, "missing_model", generated_at=resolved_generated_at
        )
        if output_directory is not None:
            write_market_summary(interpretation, output_directory)
        return interpretation

    completer = complete or _live_complete
    messages = build_messages(pack)
    last_error: Exception | None = None
    attempts = max(1, max_attempts)
    for attempt in range(attempts):
        try:
            raw = completer(messages, resolved_model or "injected", timeout_seconds)
            payload = LLMInterpretationPayload.model_validate(raw)
            validate_grounded_payload(payload, pack)
            refs = (
                list(payload.evidence)
                if payload.evidence
                else list(payload.evidence_used)
            )
            canonical = _canonical_text(payload)
            interpretation = MarketInterpretation(
                run_id=summary.run_metadata.run_id,
                as_of_date=summary.run_metadata.as_of_date,
                status=InterpretationStatus.AVAILABLE,
                market_regime_summary=payload.market_regime_summary,
                breadth_interpretation=payload.breadth_interpretation,
                trend_interpretation=payload.trend_interpretation,
                rates_and_sectors_interpretation=payload.rates_and_sectors_interpretation,
                key_confirmed_signals=payload.key_confirmed_signals,
                key_uncertainties=payload.key_uncertainties,
                risk_flags=payload.risk_flags,
                evidence_used=refs,
                evidence=refs,
                executive_summary=canonical["executive_summary"],
                market_participation=canonical["market_participation"],
                trend_conditions=canonical["trend_conditions"],
                sector_rate_risk=canonical["sector_rate_risk"],
                risks_and_limitations=canonical["risks_and_limitations"],
                disclaimer=canonical["disclaimer"],
                model=resolved_model or "injected",
                generated_at=resolved_generated_at,
            )
            if output_directory is not None:
                write_market_summary(interpretation, output_directory)
            return interpretation
        except Exception as error:
            last_error = error
            _log_attempt_failure(attempt + 1, error)
            if attempt + 1 >= attempts or not _is_retryable(error):
                break
            sleep(backoff_seconds * (2**attempt))

    reason = "openai_unavailable"
    if isinstance(last_error, ValidationError):
        reason = "invalid_structured_response"
    elif isinstance(last_error, EmptyStructuredResponseError):
        reason = "empty_structured_response"
    elif isinstance(last_error, InterpretationError):
        reason = "ungrounded_or_malformed_response"
    interpretation = _unavailable(
        summary,
        reason,
        generated_at=resolved_generated_at,
        model=resolved_model,
    )
    if output_directory is not None:
        write_market_summary(interpretation, output_directory)
    return interpretation


def interpret_quant_summary_file(
    quant_summary_path: str | Path,
    *,
    output_directory: str | Path | None = None,
    **kwargs: Any,
) -> MarketInterpretation:
    """Load validated quant_summary.json and write market_summary.json beside it."""

    path = Path(quant_summary_path)
    summary = QuantSummary.model_validate_json(path.read_text(encoding="utf-8"))
    destination = (
        output_directory if output_directory is not None else path.parent.parent
    )
    return interpret_quant_summary(summary, output_directory=destination, **kwargs)


def serialize_market_interpretation(interpretation: MarketInterpretation) -> str:
    return (
        json.dumps(
            interpretation.model_dump(mode="json"),
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def write_market_summary(
    interpretation: MarketInterpretation, output_directory: str | Path
) -> Path:
    """Atomically write outputs/<run_id>/market_summary.json."""

    payload = serialize_market_interpretation(interpretation)
    run_directory = Path(output_directory) / interpretation.run_id
    destination = run_directory / "market_summary.json"
    temporary = run_directory / ".market_summary.json.tmp"
    try:
        run_directory.mkdir(parents=True, exist_ok=True)
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(destination)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise InterpretationError(
            f"unable to write market summary: {destination}"
        ) from error
    return destination
