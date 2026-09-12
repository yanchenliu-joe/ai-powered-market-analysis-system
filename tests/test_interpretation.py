"""Mocked tests for the Phase 8 grounded interpretation layer."""

from __future__ import annotations

import ast
import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.interpretation import (
    SYSTEM_PROMPT,
    EmptyStructuredResponseError,
    InterpretationError,
    _sanitize_diagnostic,
    _values_equivalent,
    allowed_evidence_index,
    build_evidence_pack,
    build_messages,
    interpret_quant_summary,
    interpret_quant_summary_file,
    serialize_market_interpretation,
    validate_grounded_payload,
    write_market_summary,
)
from src.quant_pipeline import write_quant_summary
from src.schemas import (
    InterpretationStatus,
    LLMInterpretationPayload,
    MarketInterpretation,
    QuantSummary,
)
from tests.test_schemas import insufficient_regression, valid_summary_payload

GENERATED_AT = datetime(2024, 1, 2, 15, 30, tzinfo=UTC)
INTERPRETATION_SOURCE = (
    Path(__file__).resolve().parents[1] / "src" / "interpretation.py"
)


def _summary(*, with_insufficient: bool = False) -> QuantSummary:
    payload = copy.deepcopy(valid_summary_payload())
    if with_insufficient:
        payload["sector_regressions"] = [
            payload["sector_regressions"][0],
            insufficient_regression(),
        ]
        payload["data_quality"]["sector_result_count"] = 2
        payload["data_quality"]["insufficient_sector_count"] = 1
        payload["status"] = "partial"
    return QuantSummary.model_validate(payload)


def _ref(source_section: str, metric: str, value: object) -> dict[str, object]:
    return {
        "metric": metric,
        "value": value,
        "source_section": source_section,
    }


def valid_llm_payload(summary: QuantSummary | None = None) -> dict[str, object]:
    pack = build_evidence_pack(summary or _summary())
    trend_regime = pack["spy_trend"]["trend_regime"]
    pct_50 = pack["breadth"]["pct_above_50dma"]
    sma_200 = pack["spy_trend"]["sma_200"]
    label = pack["sector_rate_sensitivity"][0]["sensitivity_label"]
    refs = [
        _ref("spy_trend", "trend_regime", trend_regime),
        _ref("breadth", "pct_above_50dma", pct_50),
        _ref("spy_trend", "sma_200", sma_200),
        _ref("sector_rate_sensitivity", "XLK.sensitivity_label", label),
    ]
    section = {
        "summary": "Validated signals are internally consistent.",
        "evidence": refs[:1],
        "confidence": "high",
    }
    return {
        "market_regime_summary": {
            **section,
            "summary": f"Accepted trend regime is {trend_regime}.",
        },
        "breadth_interpretation": {
            "summary": f"Participation pct_above_50dma is {pct_50}.",
            "evidence": [_ref("breadth", "pct_above_50dma", pct_50)],
            "confidence": "medium",
        },
        "trend_interpretation": {
            "summary": f"SMA200 remains {sma_200} in the validated snapshot.",
            "evidence": [_ref("spy_trend", "sma_200", sma_200)],
            "confidence": "high",
        },
        "rates_and_sectors_interpretation": {
            "summary": f"XLK sensitivity_label is {label}.",
            "evidence": [
                _ref("sector_rate_sensitivity", "XLK.sensitivity_label", label)
            ],
            "confidence": "medium",
        },
        "key_confirmed_signals": [f"trend_regime={trend_regime}"],
        "key_uncertainties": ["Regression describes association, not causation."],
        "risk_flags": [],
        "evidence_used": refs,
        "evidence": refs,
        "executive_summary": f"Accepted trend regime is {trend_regime}.",
        "market_participation": f"Participation pct_above_50dma is {pct_50}.",
        "trend_conditions": f"SMA200 remains {sma_200} in the validated snapshot.",
        "sector_rate_risk": f"XLK sensitivity_label is {label}.",
        "risks_and_limitations": "Regression describes association, not causation.",
        "disclaimer": (
            "This report is for research and educational purposes only and does not "
            "constitute investment advice."
        ),
    }


def test_evidence_pack_uses_only_validated_summary_fields() -> None:
    pack = build_evidence_pack(_summary(with_insufficient=True))

    assert set(pack) == {
        "run_id",
        "as_of_date",
        "quant_status",
        "yield_unit",
        "limitations",
        "breadth",
        "spy_trend",
        "sector_rate_sensitivity",
    }
    assert pack["as_of_date"] == "2023-12-29"
    assert pack["spy_trend"]["trend_regime"] == "strong_uptrend"
    xlre = next(
        record
        for record in pack["sector_rate_sensitivity"]
        if record["sector"] == "XLRE"
    )
    assert xlre["beta_yield"] is None
    assert xlre["sensitivity_label"] == "insufficient_data"
    assert xlre["status"] == "insufficient_data"
    serialized = json.dumps(pack, allow_nan=False)
    assert "NaN" not in serialized


def test_evidence_builder_does_not_create_synthetic_metrics() -> None:
    pack = build_evidence_pack(_summary())

    assert "pct_above_100dma" not in pack["breadth"]
    assert "forecast" not in pack
    assert "price_path" not in pack
    assert pack["sector_rate_sensitivity"][0]["sector"] == "XLK"


def test_evidence_value_equivalence_handles_nulls_bools_and_numbers() -> None:
    assert _values_equivalent(None, None)
    assert not _values_equivalent(None, 0)
    assert _values_equivalent(True, True)
    assert not _values_equivalent(True, False)
    assert _values_equivalent(1, 1.0)
    assert _values_equivalent(38.12375249500998, 38.12375249500998)
    assert _values_equivalent(38.1, 38.12375249500998)
    assert _values_equivalent(2.30, 2.2960526315789473)
    assert _values_equivalent(765.63, 765.6300048828125)
    assert _values_equivalent(-0.0647, -0.06469150073507576)
    assert not _values_equivalent(40.0, 38.12375249500998)
    assert not _values_equivalent(0.0647, -0.06469150073507576)
    assert _values_equivalent("uptrend", "uptrend")
    assert not _values_equivalent("uptrend", "downtrend")


def test_accepted_labels_are_preserved_in_allowed_index() -> None:
    pack = build_evidence_pack(_summary(with_insufficient=True))
    allowed = allowed_evidence_index(pack)

    assert allowed[("spy_trend", "trend_regime")] == "strong_uptrend"
    assert allowed[("sector_rate_sensitivity", "XLK.sensitivity_label")] == (
        "negative_significant"
    )
    assert allowed[("sector_rate_sensitivity", "XLRE.beta_yield")] is None
    assert ("sector_rate_sensitivity", "beta_yield") not in allowed


def test_skip_flag_does_not_invoke_complete() -> None:
    calls: list[int] = []

    def complete(messages: list[dict[str, str]], model: str, timeout: float) -> dict:
        calls.append(1)
        return valid_llm_payload()

    result = interpret_quant_summary(
        _summary(),
        complete=complete,
        skip=True,
        generated_at=GENERATED_AT,
    )
    assert calls == []
    assert result.status is InterpretationStatus.UNAVAILABLE
    assert result.reason == "skipped"


def test_prompt_forbids_unsupported_data_and_recalculation() -> None:
    lowered = SYSTEM_PROMPT.lower()
    messages = build_messages(build_evidence_pack(_summary()))

    assert "validated quantitative evidence" in lowered
    assert "do not invent" in lowered
    assert "do not recompute" in lowered
    assert "causality" in lowered
    assert "insufficient-data" in lowered
    assert "investment advice" in lowered
    assert "source_section=breadth" in SYSTEM_PROMPT
    assert "source_section=spy_trend" in SYSTEM_PROMPT
    assert "source_section=sector_rate_sensitivity" in SYSTEM_PROMPT
    assert "XLK.beta_yield" in SYSTEM_PROMPT
    assert "do not shorten" in lowered
    assert messages[0]["role"] == "system"
    assert "pct_above_50dma" in messages[1]["content"]


def test_successful_mocked_interpretation_writes_market_summary(
    tmp_path: Path,
) -> None:
    summary = _summary()
    payload = valid_llm_payload(summary)
    calls: list[tuple[str, float]] = []

    def complete(messages: list[dict[str, str]], model: str, timeout: float) -> dict:
        calls.append((model, timeout))
        assert "Do not recompute" in messages[0]["content"]
        return payload

    result = interpret_quant_summary(
        summary,
        output_directory=tmp_path,
        model="test-model",
        api_key="unused",
        complete=complete,
        generated_at=GENERATED_AT,
        max_attempts=3,
    )
    path = tmp_path / "fixed-run" / "market_summary.json"
    written = json.loads(path.read_text(encoding="utf-8"))

    assert result.status is InterpretationStatus.AVAILABLE
    assert result.run_id == "fixed-run"
    assert result.as_of_date.isoformat() == "2023-12-29"
    assert result.model == "test-model"
    assert result.market_regime_summary is not None
    assert result.evidence_used[0].source_section in {
        "spy_trend",
        "breadth",
        "sector_rate_sensitivity",
    }
    assert written["status"] == "available"
    assert written["run_id"] == "fixed-run"
    assert written["model"] == "test-model"
    assert written["generated_at"] == "2024-01-02T15:30:00Z"
    assert (tmp_path / "fixed-run" / ".market_summary.json.tmp").exists() is False
    assert calls == [("test-model", 30.0)]


def test_interpret_quant_summary_file_reads_validated_json(tmp_path: Path) -> None:
    summary = _summary()
    quant_path = write_quant_summary(summary, tmp_path)

    result = interpret_quant_summary_file(
        quant_path,
        complete=lambda messages, model, timeout: valid_llm_payload(summary),
        model="file-model",
        generated_at=GENERATED_AT,
    )
    sibling = quant_path.with_name("market_summary.json")

    assert sibling.exists()
    assert quant_path.exists()
    assert result.status is InterpretationStatus.AVAILABLE
    assert json.loads(quant_path.read_text())["schema_version"] == "1.0.0"


def test_missing_api_key_writes_unavailable_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    summary = _summary()

    result = interpret_quant_summary(
        summary,
        output_directory=tmp_path,
        generated_at=GENERATED_AT,
    )
    written = json.loads((tmp_path / "fixed-run" / "market_summary.json").read_text())

    assert result.status is InterpretationStatus.UNAVAILABLE
    assert result.reason == "missing_api_key"
    assert result.market_regime_summary is None
    assert result.evidence_used == []
    assert written["status"] == "unavailable"
    assert written["reason"] == "missing_api_key"
    assert written["market_regime_summary"] is None


def test_missing_model_degrades_when_key_is_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    result = interpret_quant_summary(
        _summary(),
        output_directory=tmp_path,
        generated_at=GENERATED_AT,
    )

    assert result.reason == "missing_model"
    assert result.status is InterpretationStatus.UNAVAILABLE


def test_api_failure_retries_then_degrades(tmp_path: Path) -> None:
    attempts: list[int] = []
    sleeps: list[float] = []

    def complete(messages: list[dict[str, str]], model: str, timeout: float) -> dict:
        attempts.append(1)
        raise TimeoutError("network timeout")

    result = interpret_quant_summary(
        _summary(),
        output_directory=tmp_path,
        model="retry-model",
        api_key="sk-test",
        complete=complete,
        generated_at=GENERATED_AT,
        max_attempts=3,
        sleep=sleeps.append,
        backoff_seconds=0.25,
    )

    assert attempts == [1, 1, 1]
    assert sleeps == [0.25, 0.5]
    assert result.status is InterpretationStatus.UNAVAILABLE
    assert result.reason == "openai_unavailable"
    assert result.model == "retry-model"


def test_malformed_response_is_retried_then_unavailable(tmp_path: Path) -> None:
    attempts: list[int] = []

    def complete(messages: list[dict[str, str]], model: str, timeout: float) -> dict:
        attempts.append(1)
        return {"not": "a valid payload"}

    result = interpret_quant_summary(
        _summary(),
        output_directory=tmp_path,
        model="bad-model",
        api_key="sk-test",
        complete=complete,
        generated_at=GENERATED_AT,
        sleep=lambda _: None,
    )

    assert attempts == [1, 1, 1]
    assert result.reason == "invalid_structured_response"
    assert result.market_regime_summary is None


def test_ungrounded_evidence_is_rejected(tmp_path: Path) -> None:
    payload = valid_llm_payload()
    payload["evidence_used"].append(_ref("breadth", "invented_metric", 12.0))

    result = interpret_quant_summary(
        _summary(),
        output_directory=tmp_path,
        model="ground-model",
        complete=lambda messages, model, timeout: payload,
        generated_at=GENERATED_AT,
        sleep=lambda _: None,
    )

    assert result.reason == "ungrounded_or_malformed_response"
    assert result.status is InterpretationStatus.UNAVAILABLE


def test_mismatched_evidence_value_is_rejected() -> None:
    payload = valid_llm_payload()
    payload["breadth_interpretation"]["evidence"][0]["value"] = 0.0

    result = interpret_quant_summary(
        _summary(),
        model="ground-model",
        complete=lambda messages, model, timeout: payload,
        generated_at=GENERATED_AT,
        max_attempts=1,
    )

    assert result.reason == "ungrounded_or_malformed_response"


def test_non_retryable_errors_do_not_retry() -> None:
    class AuthenticationError(Exception):
        pass

    attempts: list[int] = []

    def complete(messages: list[dict[str, str]], model: str, timeout: float) -> dict:
        attempts.append(1)
        raise AuthenticationError("invalid key")

    result = interpret_quant_summary(
        _summary(),
        model="auth-model",
        api_key="sk-test",
        complete=complete,
        generated_at=GENERATED_AT,
        max_attempts=3,
        sleep=lambda _: None,
    )

    assert attempts == [1]
    assert result.reason == "openai_unavailable"


def test_retry_then_success() -> None:
    attempts: list[int] = []
    summary = _summary()
    payload = valid_llm_payload(summary)

    def complete(messages: list[dict[str, str]], model: str, timeout: float) -> dict:
        attempts.append(1)
        if len(attempts) < 2:
            raise ConnectionError("temporary")
        return payload

    result = interpret_quant_summary(
        summary,
        model="retry-ok",
        complete=complete,
        generated_at=GENERATED_AT,
        sleep=lambda _: None,
    )

    assert attempts == [1, 1]
    assert result.status is InterpretationStatus.AVAILABLE


def test_atomic_write_replaces_destination(tmp_path: Path) -> None:
    interpretation = interpret_quant_summary(
        _summary(),
        complete=lambda messages, model, timeout: valid_llm_payload(),
        model="atomic-model",
        generated_at=GENERATED_AT,
    )
    path = write_market_summary(interpretation, tmp_path)
    parsed = json.loads(path.read_text(encoding="utf-8"))

    assert path.name == "market_summary.json"
    json.dumps(parsed, allow_nan=False)
    assert parsed["status"] == "available"
    assert not path.with_name(".market_summary.json.tmp").exists()
    assert serialize_market_interpretation(interpretation) == path.read_text(
        encoding="utf-8"
    )


def test_write_failure_cleans_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    interpretation = interpret_quant_summary(
        _summary(),
        complete=lambda messages, model, timeout: valid_llm_payload(),
        model="atomic-model",
        generated_at=GENERATED_AT,
    )

    def fail_replace(self: Path, target: Path) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(InterpretationError, match="unable to write"):
        write_market_summary(interpretation, tmp_path)
    assert not (tmp_path / "fixed-run" / ".market_summary.json.tmp").exists()


def test_llm_payload_rejects_extra_fields() -> None:
    payload = valid_llm_payload()
    payload["forecast"] = "prices will rise"

    with pytest.raises(ValidationError):
        LLMInterpretationPayload.model_validate(payload)


def test_unavailable_schema_forbids_commentary() -> None:
    with pytest.raises(ValidationError, match="invent commentary"):
        MarketInterpretation.model_validate(
            {
                "run_id": "fixed-run",
                "as_of_date": "2023-12-29",
                "status": "unavailable",
                "reason": "openai_unavailable",
                "key_confirmed_signals": ["made up"],
                "generated_at": GENERATED_AT,
            }
        )


def test_interpret_uses_live_complete_when_no_complete_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary = _summary()
    payload = valid_llm_payload(summary)

    def fake_live(messages: list[dict[str, str]], model: str, timeout: float) -> dict:
        assert model == "live-model"
        return payload

    monkeypatch.setattr("src.interpretation._live_complete", fake_live)
    result = interpret_quant_summary(
        summary,
        generated_at=GENERATED_AT,
        complete=None,
        api_key="sk-test",
        model="live-model",
    )
    assert result.status is InterpretationStatus.AVAILABLE
    assert result.model == "live-model"


def test_real_live_complete_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    from src import interpretation as module

    summary = _summary()
    payload = LLMInterpretationPayload.model_validate(valid_llm_payload(summary))

    def parse(**kwargs: object) -> SimpleNamespace:
        assert kwargs["temperature"] == 0
        assert kwargs["response_format"] is LLMInterpretationPayload
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=payload))]
        )

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.timeout = kwargs.get("timeout")
            self.beta = SimpleNamespace(
                chat=SimpleNamespace(completions=SimpleNamespace(parse=parse))
            )

    monkeypatch.setattr(module, "OpenAI", FakeOpenAI, raising=False)

    import openai as openai_module

    monkeypatch.setattr(openai_module, "OpenAI", FakeOpenAI)
    result = module._live_complete([{"role": "system", "content": "x"}], "m", 12.0)
    assert result["market_regime_summary"]["confidence"] == "high"


def test_live_complete_falls_back_and_rejects_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src import interpretation as module

    class Completions:
        def parse(self, **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(parsed=None))]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.beta = SimpleNamespace(chat=SimpleNamespace(completions=object()))
            self.chat = SimpleNamespace(completions=Completions())

    import openai as openai_module

    monkeypatch.setattr(openai_module, "OpenAI", FakeOpenAI)

    with pytest.raises(InterpretationError, match="empty"):
        module._live_complete([], "m", 1.0)


def _high_precision_summary() -> QuantSummary:
    payload = copy.deepcopy(valid_summary_payload())
    payload["breadth"]["pct_above_50dma"] = 38.12375249500998
    payload["breadth"]["advance_decline_ratio"] = 2.2960526315789473
    payload["trend"]["adjusted_close"] = 765.6300048828125
    payload["sector_regressions"][0]["beta_yield"] = -0.06469150073507576
    payload["sector_regressions"][0]["ci_95_lower"] = -0.09661022263917288
    payload["sector_regressions"][0]["ci_95_upper"] = -0.03277277883097865
    payload["sector_regressions"][0]["effect_10bp"] = -0.006469150073507577
    return QuantSummary.model_validate(payload)


def test_rounded_numeric_evidence_is_accepted() -> None:
    summary = _high_precision_summary()
    payload = valid_llm_payload(summary)
    payload["evidence_used"][1]["value"] = 38.1
    payload["breadth_interpretation"]["evidence"][0]["value"] = 38.1
    payload["evidence_used"].append(_ref("breadth", "advance_decline_ratio", 2.30))
    payload["evidence_used"].append(_ref("spy_trend", "adjusted_close", 765.63))
    payload["evidence_used"].append(
        _ref("sector_rate_sensitivity", "XLK.beta_yield", -0.0647)
    )

    result = interpret_quant_summary(
        summary,
        model="round-model",
        complete=lambda messages, model, timeout: payload,
        generated_at=GENERATED_AT,
        max_attempts=1,
    )

    assert result.status is InterpretationStatus.AVAILABLE
    validate_grounded_payload(
        LLMInterpretationPayload.model_validate(payload),
        build_evidence_pack(summary),
    )


def test_materially_wrong_and_sign_flipped_evidence_fail() -> None:
    summary = _high_precision_summary()
    wrong = valid_llm_payload(summary)
    wrong["breadth_interpretation"]["evidence"][0]["value"] = 40.0
    flipped = valid_llm_payload(summary)
    flipped["evidence_used"].append(
        _ref("sector_rate_sensitivity", "XLK.beta_yield", 0.0647)
    )

    for payload in (wrong, flipped):
        result = interpret_quant_summary(
            summary,
            model="wrong-model",
            complete=lambda messages, model, timeout, data=payload: data,
            generated_at=GENERATED_AT,
            max_attempts=1,
        )
        assert result.reason == "ungrounded_or_malformed_response"


def test_unknown_source_section_and_metric_fail() -> None:
    summary = _summary()
    unknown_section = valid_llm_payload(summary)
    unknown_section["evidence_used"].append(_ref("trend", "trend_regime", "uptrend"))
    unknown_metric = valid_llm_payload(summary)
    unknown_metric["evidence_used"].append(_ref("breadth", "invented_metric", 12.0))
    short_sector = valid_llm_payload(summary)
    short_sector["evidence_used"].append(
        _ref("sector_rate_sensitivity", "beta_yield", -0.02)
    )

    for payload in (unknown_section, unknown_metric, short_sector):
        result = interpret_quant_summary(
            summary,
            model="path-model",
            complete=lambda messages, model, timeout, data=payload: data,
            generated_at=GENERATED_AT,
            max_attempts=1,
        )
        assert result.reason == "ungrounded_or_malformed_response"


def test_correct_sector_path_and_string_labels_must_match() -> None:
    summary = _summary()
    payload = valid_llm_payload(summary)
    payload["evidence_used"].append(
        _ref("sector_rate_sensitivity", "XLK.beta_yield", -0.02)
    )
    invented_regime = valid_llm_payload(summary)
    invented_regime["evidence_used"][0]["value"] = "bullish"

    accepted = interpret_quant_summary(
        summary,
        model="sector-model",
        complete=lambda messages, model, timeout: payload,
        generated_at=GENERATED_AT,
        max_attempts=1,
    )
    rejected = interpret_quant_summary(
        summary,
        model="regime-model",
        complete=lambda messages, model, timeout: invented_regime,
        generated_at=GENERATED_AT,
        max_attempts=1,
    )

    assert accepted.status is InterpretationStatus.AVAILABLE
    assert rejected.reason == "ungrounded_or_malformed_response"


def test_retry_diagnostics_capture_attempt_and_redact_secrets(
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = valid_llm_payload()
    payload["evidence_used"].append(_ref("breadth", "invented_metric", 12.0))

    with caplog.at_level("INFO", logger="src.interpretation"):
        interpret_quant_summary(
            _summary(),
            model="diag-model",
            complete=lambda messages, model, timeout: payload,
            generated_at=GENERATED_AT,
            sleep=lambda _: None,
        )

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "attempt=1" in message and "stage=groundedness" in message
        for message in messages
    )
    assert any("attempt=2" in message for message in messages)
    assert any("attempt=3" in message for message in messages)
    assert any("invented_metric" in message for message in messages)
    leaked = _sanitize_diagnostic(InterpretationError("key=sk-secretvalueOPENAI"))
    assert "sk-secretvalueOPENAI" not in leaked
    assert "[redacted]" in leaked
    assert all("sk-test" not in message for message in messages)
    assert all("OPENAI_API_KEY" not in message for message in messages)


def test_empty_parsed_response_has_distinct_reason() -> None:
    def complete(messages: list[dict[str, str]], model: str, timeout: float) -> dict:
        raise EmptyStructuredResponseError("structured response was empty")

    result = interpret_quant_summary(
        _summary(),
        model="empty-model",
        complete=complete,
        generated_at=GENERATED_AT,
        max_attempts=1,
    )

    assert result.reason == "empty_structured_response"
    assert result.status is InterpretationStatus.UNAVAILABLE


def test_interpretation_module_does_not_import_quantitative_engines() -> None:
    tree = ast.parse(INTERPRETATION_SOURCE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
            imported.add(node.module)

    forbidden = {
        "yfinance",
        "pandas_datareader",
        "src.data_loader",
        "src.preprocessing",
        "src.breadth",
        "src.trend",
        "src.regression",
        "src.visualization",
        "src.quant_pipeline",
        "data_loader",
        "breadth",
        "trend",
        "regression",
        "visualization",
    }
    assert imported.isdisjoint(forbidden)
    assert "src.schemas" in imported
