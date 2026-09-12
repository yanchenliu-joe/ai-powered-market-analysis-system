"""Upload a serialize-only live-run bundle to private object storage."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REQUIRED_FILES = {
    "quant_summary": "quant_summary.json",
    "market_summary": "market_summary.json",
    "breadth_timeseries": "breadth_timeseries.json",
    "trend_timeseries": "trend_timeseries.json",
    "pdf": "market_report.pdf",
}
OPTIONAL_FILES = (
    "market_report.md",
    "breadth_timeseries.png",
    "spy_trend.png",
    "sector_rate_beta.png",
)
SECRET_MARKERS = (
    "OPENAI_API_KEY",
    "RUN_ANALYSIS_SECRET",
    "GITHUB_TOKEN",
    "BLOB_READ_WRITE_TOKEN",
)
BLOB_API = "https://blob.vercel-storage.com"
PUBLIC_DATA = Path("web") / "public" / "data"


class LiveRunPublishError(RuntimeError):
    """Raised when a live-run bundle cannot be published."""


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def redact_token(token: str) -> str:
    if len(token) < 8:
        return "[redacted]"
    return f"{token[:4]}…{token[-4:]}"


def empty_artifacts() -> dict[str, bool]:
    return {
        "quant_summary": False,
        "market_summary": False,
        "breadth_timeseries": False,
        "trend_timeseries": False,
        "pdf": False,
    }


def new_manifest(
    run_id: str,
    *,
    status: str,
    created_at: str | None = None,
    message: str | None = None,
    as_of_date: str | None = None,
    interpretation_status: str | None = None,
    artifacts: dict[str, bool] | None = None,
) -> dict[str, Any]:
    stamp = created_at or utc_now()
    return {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "created_at": stamp,
        "updated_at": stamp,
        "status": status,
        "as_of_date": as_of_date,
        "interpretation_status": interpretation_status,
        "message": message,
        "artifacts": artifacts or empty_artifacts(),
    }


def assert_no_secrets(payload: str) -> None:
    for marker in SECRET_MARKERS:
        if marker in payload:
            raise LiveRunPublishError(
                "refusing to write secret material into artifacts"
            )


def inspect_bundle(bundle_dir: Path) -> dict[str, bool]:
    flags = empty_artifacts()
    for key, name in REQUIRED_FILES.items():
        flags[key] = (bundle_dir / name).is_file()
    return flags


def decide_status(
    pipeline_exit: int,
    artifacts: dict[str, bool],
    interpretation_status: str | None,
) -> tuple[str, str]:
    if pipeline_exit == 1 or not artifacts["quant_summary"]:
        return "failure", "Quantitative analysis failed."
    required_core = (
        artifacts["quant_summary"]
        and artifacts["market_summary"]
        and artifacts["breadth_timeseries"]
        and artifacts["trend_timeseries"]
    )
    if not required_core:
        return "failure", "Required run bundle artifacts are missing."
    if (
        pipeline_exit == 2
        or interpretation_status == "unavailable"
        or not artifacts["pdf"]
    ):
        return (
            "partial",
            "Analysis completed with limited AI interpretation or incomplete PDF.",
        )
    if pipeline_exit == 0 and artifacts["pdf"]:
        return "success", "Analysis complete."
    return "failure", "Run did not produce a complete bundle."


def read_interpretation_status(bundle_dir: Path) -> str | None:
    path = bundle_dir / "market_summary.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    status = payload.get("status")
    return status if isinstance(status, str) else None


def read_as_of_date(bundle_dir: Path) -> str | None:
    path = bundle_dir / "quant_summary.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    metadata = payload.get("run_metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("as_of_date"), str):
        return metadata["as_of_date"]
    return None


def blob_put(
    pathname: str,
    body: bytes,
    content_type: str,
    token: str,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> None:
    query = urllib.parse.urlencode({"pathname": pathname})
    request = urllib.request.Request(
        f"{BLOB_API}/?{query}",
        data=body,
        method="PUT",
        headers={
            "authorization": f"Bearer {token}",
            "x-api-version": "7",
            "x-vercel-blob-access": "private",
            "x-add-random-suffix": "0",
            "x-allow-overwrite": "1",
            "x-content-type": content_type,
        },
    )
    try:
        with opener(request, timeout=60):
            return
    except urllib.error.HTTPError as error:
        raise LiveRunPublishError(
            f"blob upload failed for {pathname.split('/')[-1]}"
        ) from error


def blob_get_text(
    pathname: str,
    token: str,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> str | None:
    query = urllib.parse.urlencode({"pathname": pathname})
    request = urllib.request.Request(
        f"{BLOB_API}/get?{query}",
        method="GET",
        headers={
            "authorization": f"Bearer {token}",
            "x-api-version": "7",
        },
    )
    try:
        with opener(request, timeout=30) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError:
        return None
    except OSError:
        return None


def content_type_for(name: str) -> str:
    if name.endswith(".json"):
        return "application/json"
    if name.endswith(".pdf"):
        return "application/pdf"
    if name.endswith(".md"):
        return "text/markdown"
    if name.endswith(".png"):
        return "image/png"
    return "application/octet-stream"


def write_manifest_object(
    run_id: str,
    manifest: dict[str, Any],
    token: str,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> None:
    payload = json.dumps(manifest, indent=2, sort_keys=False)
    assert_no_secrets(payload)
    blob_put(
        f"analysis/{run_id}/manifest.json",
        payload.encode("utf-8"),
        "application/json",
        token,
        opener=opener,
    )


def write_access_alias(
    access_token: str,
    run_id: str,
    token: str,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> None:
    created = utc_now()
    expires = (
        (datetime.now(UTC) + timedelta(days=7))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    payload = json.dumps(
        {
            "schema_version": "1.0.0",
            "analysis_id": run_id,
            "source_run_id": run_id,
            "created_at": created,
            "expires_at": expires,
            "reused": False,
        }
    )
    assert_no_secrets(payload)
    blob_put(
        f"access/{access_token}.json",
        payload.encode("utf-8"),
        "application/json",
        token,
        opener=opener,
    )


def write_reusable_daily(
    manifest: dict[str, Any],
    token: str,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> None:
    payload = json.dumps(
        {
            "as_of_date": manifest.get("as_of_date"),
            "source_run_id": manifest["run_id"],
            "analysis_id": manifest["run_id"],
            "generated_at": manifest.get("updated_at") or utc_now(),
            "status": manifest["status"],
        }
    )
    assert_no_secrets(payload)
    blob_put(
        "control/reusable_daily.json",
        payload.encode("utf-8"),
        "application/json",
        token,
        opener=opener,
    )


def upload_bundle(
    run_id: str,
    bundle_dir: Path,
    token: str,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> None:
    resolved = bundle_dir.resolve()
    public = (Path.cwd() / PUBLIC_DATA).resolve()
    if resolved == public or public in resolved.parents:
        raise LiveRunPublishError("live publish must not read web/public/data")
    names = list(REQUIRED_FILES.values()) + list(OPTIONAL_FILES)
    for name in names:
        path = bundle_dir / name
        if not path.is_file():
            continue
        data = path.read_bytes()
        if name.endswith(".json"):
            assert_no_secrets(data.decode("utf-8"))
        blob_put(
            f"analysis/{run_id}/{name}",
            data,
            content_type_for(name),
            token,
            opener=opener,
        )


def release_lock(
    token: str,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> None:
    payload = json.dumps({"active": False, "updated_at": utc_now()})
    blob_put(
        "control/active_run.json",
        payload.encode("utf-8"),
        "application/json",
        token,
        opener=opener,
    )


def publish(
    *,
    run_id: str,
    access_token: str,
    bundle_dir: Path | None,
    pipeline_exit: int,
    blob_token: str,
    existing: dict[str, Any] | None = None,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> dict[str, Any]:
    created_at = existing["created_at"] if existing else utc_now()
    if pipeline_exit == 1 or bundle_dir is None or not bundle_dir.is_dir():
        manifest = new_manifest(
            run_id,
            status="failure",
            created_at=created_at,
            message="Quantitative analysis failed.",
        )
        manifest["updated_at"] = utc_now()
        write_manifest_object(run_id, manifest, blob_token, opener=opener)
        write_access_alias(access_token, run_id, blob_token, opener=opener)
        release_lock(blob_token, opener=opener)
        return manifest

    artifacts = inspect_bundle(bundle_dir)
    interpretation_status = read_interpretation_status(bundle_dir)
    as_of_date = read_as_of_date(bundle_dir)
    status, message = decide_status(pipeline_exit, artifacts, interpretation_status)
    publishing = new_manifest(
        run_id,
        status="publishing",
        created_at=created_at,
        message="Publishing report.",
        as_of_date=as_of_date,
        interpretation_status=interpretation_status,
        artifacts=artifacts,
    )
    publishing["updated_at"] = utc_now()
    write_manifest_object(run_id, publishing, blob_token, opener=opener)
    try:
        if status != "failure":
            upload_bundle(run_id, bundle_dir, blob_token, opener=opener)
        final = new_manifest(
            run_id,
            status=status,
            created_at=created_at,
            message=message,
            as_of_date=as_of_date,
            interpretation_status=interpretation_status,
            artifacts=artifacts,
        )
        final["updated_at"] = utc_now()
        write_manifest_object(run_id, final, blob_token, opener=opener)
        write_access_alias(access_token, run_id, blob_token, opener=opener)
        if status in {"success", "partial"}:
            write_reusable_daily(final, blob_token, opener=opener)
        release_lock(blob_token, opener=opener)
        return final
    except LiveRunPublishError as error:
        failed = new_manifest(
            run_id,
            status="failure",
            created_at=created_at,
            message=f"Publishing failed: {error}",
            as_of_date=as_of_date,
            interpretation_status=interpretation_status,
            artifacts=artifacts,
        )
        failed["updated_at"] = utc_now()
        try:
            write_manifest_object(run_id, failed, blob_token, opener=opener)
        except LiveRunPublishError:
            pass
        return failed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish a live-run artifact bundle")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--access-token", required=True)
    parser.add_argument("--bundle-dir")
    parser.add_argument("--pipeline-exit", type=int, default=1)
    parser.add_argument(
        "--set-status",
        choices=("running", "publishing", "failure"),
        help="Update manifest status only",
    )
    parser.add_argument("--message")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    blob_token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not blob_token:
        print("BLOB_READ_WRITE_TOKEN is required", flush=True)
        return 1
    existing_text = blob_get_text(
        f"analysis/{args.run_id}/manifest.json",
        blob_token,
    )
    existing = json.loads(existing_text) if existing_text else None
    if args.set_status:
        created = existing["created_at"] if existing else utc_now()
        manifest = new_manifest(
            args.run_id,
            status=args.set_status,
            created_at=created,
            message=args.message,
            as_of_date=existing.get("as_of_date") if existing else None,
            artifacts=existing.get("artifacts") if existing else None,
        )
        manifest["updated_at"] = utc_now()
        write_manifest_object(args.run_id, manifest, blob_token)
        print(
            f"manifest status={args.set_status} run_id={args.run_id} "
            f"token={redact_token(args.access_token)}",
            flush=True,
        )
        return 0
    bundle = Path(args.bundle_dir) if args.bundle_dir else None
    result = publish(
        run_id=args.run_id,
        access_token=args.access_token,
        bundle_dir=bundle,
        pipeline_exit=args.pipeline_exit,
        blob_token=blob_token,
        existing=existing,
    )
    print(
        f"published status={result['status']} run_id={args.run_id} "
        f"token={redact_token(args.access_token)}",
        flush=True,
    )
    return 0 if result["status"] in {"success", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
