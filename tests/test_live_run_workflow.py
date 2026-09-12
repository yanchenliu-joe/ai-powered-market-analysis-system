"""Guard the owner-only GitHub Actions live-run workflow."""

from __future__ import annotations

from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "run-market-analysis.yml"
)


def test_workflow_executes_pipeline_and_bundle_export() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python -m src.main" in text
    assert "--export-run-bundle" in text
    assert "--export-web-snapshot" not in text
    assert "web/public/data" not in text
    assert "python -m src.live_run_publish" in text
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in text
    assert "BLOB_READ_WRITE_TOKEN" not in text
    assert "publish_authorization:" in text
    assert "run_id:" in text
    assert "access_token:" in text
    assert "Mask runtime capabilities" in text
    assert "echo \"::add-mask::$RAW_ACCESS_TOKEN\"" in text
    assert "echo \"::add-mask::$RAW_PUBLISH_AUTHORIZATION\"" in text
    assert "      PUBLISH_AUTHORIZATION: ${{ inputs.publish_authorization }}" not in text
    assert "          ACCESS_TOKEN: ${{ inputs.access_token }}" not in text
    assert "RAW_PUBLISH_AUTHORIZATION: ${{ inputs.publish_authorization }}" in text
    assert "RAW_ACCESS_TOKEN: ${{ inputs.access_token }}" in text
    assert all(
        "publish_authorization" not in line
        for line in text.splitlines()
        if "echo" in line.lower()
    )
