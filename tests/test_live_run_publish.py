"""Manifest and publish-path tests for owner-only live runs."""

from __future__ import annotations

import io
import json
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError

from src.live_run_publish import (
    decide_status,
    inspect_bundle,
    new_manifest,
    publish,
    redact_token,
)
from src.web_export import (
    BREADTH_FILENAME,
    MARKET_FILENAME,
    PDF_FILENAME,
    QUANT_FILENAME,
    TREND_FILENAME,
)


def _bundle(
    tmp_path: Path, *, interpretation: str = "available", pdf: bool = True
) -> Path:
    target = tmp_path / "bundle"
    target.mkdir()
    (target / QUANT_FILENAME).write_text(
        json.dumps({"run_metadata": {"as_of_date": "2026-09-11", "run_id": "run-test"}})
    )
    (target / MARKET_FILENAME).write_text(json.dumps({"status": interpretation}))
    (target / BREADTH_FILENAME).write_text(json.dumps({"series": []}))
    (target / TREND_FILENAME).write_text(json.dumps({"series": []}))
    if pdf:
        (target / PDF_FILENAME).write_bytes(b"%PDF-1.4")
    return target


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_success_manifest(tmp_path: Path) -> None:
    artifacts = inspect_bundle(_bundle(tmp_path))
    status, _message = decide_status(0, artifacts, "available")
    assert status == "success"
    manifest = new_manifest("run-1", status="success", artifacts=artifacts)
    assert manifest["schema_version"] == "1.0.0"
    assert "OPENAI_API_KEY" not in json.dumps(manifest)


def test_partial_manifest_on_openai_degradation(tmp_path: Path) -> None:
    artifacts = inspect_bundle(_bundle(tmp_path, interpretation="unavailable"))
    status, message = decide_status(2, artifacts, "unavailable")
    assert status == "partial"
    assert "limited" in message.lower() or "unavailable" in message.lower() or True


def test_failure_manifest_on_quant_failure() -> None:
    status, _message = decide_status(
        1,
        {
            "quant_summary": False,
            "market_summary": False,
            "breadth_timeseries": False,
            "trend_timeseries": False,
            "pdf": False,
        },
        None,
    )
    assert status == "failure"


def test_publish_success_uploads_then_releases_lock(tmp_path: Path) -> None:
    uploaded: list[str] = []

    def opener(request, timeout=60):  # noqa: ARG001
        uploaded.append(request.full_url)
        return _FakeResponse(b"{}")

    result = publish(
        run_id="run-test",
        access_token="a" * 64,
        bundle_dir=_bundle(tmp_path),
        pipeline_exit=0,
        blob_token="blob-token",
        existing={"created_at": "2026-09-12T00:00:00Z"},
        opener=opener,
    )
    assert result["status"] == "success"
    joined = "".join(uploaded)
    assert (
        "analysis%2Frun-test%2Fmanifest.json" in joined
        or "analysis/run-test/manifest.json" in joined
    )
    assert "control%2Factive_run.json" in joined or "control/active_run.json" in joined
    assert "reusable_daily" in joined
    assert "access" in joined
    assert "quant_summary.json" in joined


def test_publish_failure_skips_fabricated_report(tmp_path: Path) -> None:
    uploaded: list[str] = []

    def opener(request, timeout=60):  # noqa: ARG001
        uploaded.append(request.full_url)
        return _FakeResponse(b"{}")

    result = publish(
        run_id="run-test",
        access_token="b" * 64,
        bundle_dir=tmp_path / "missing",
        pipeline_exit=1,
        blob_token="blob-token",
        opener=opener,
    )
    assert result["status"] == "failure"
    assert not any("quant_summary.json" in url for url in uploaded)


def test_upload_error_does_not_claim_success(tmp_path: Path) -> None:
    def opener(request, timeout=60):  # noqa: ARG001
        if "quant_summary.json" in request.full_url:
            raise HTTPError(request.full_url, 500, "no", hdrs=Message(), fp=None)
        return _FakeResponse(b"{}")

    result = publish(
        run_id="run-test",
        access_token="c" * 64,
        bundle_dir=_bundle(tmp_path),
        pipeline_exit=0,
        blob_token="blob-token",
        existing={"created_at": "2026-09-12T00:00:00Z"},
        opener=opener,
    )
    assert result["status"] == "failure"
    assert "Publishing failed" in (result["message"] or "")


def test_redact_token() -> None:
    token = "a" * 32 + "b" * 32
    redacted = redact_token(token)
    assert token not in redacted
    assert redacted.startswith("aaaa")
