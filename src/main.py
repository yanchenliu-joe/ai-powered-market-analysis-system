"""Command-line entry point for the market analysis workflow."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date
from enum import IntEnum
from pathlib import Path

from src.config import AppConfig, load_config
from src.pipeline import RunOptions, execute_analysis


class ExitCode(IntEnum):
    """Process outcomes for the integrated pipeline."""

    SUCCESS = 0
    FAILURE = 1
    PARTIAL = 2


class RedactingFilter(logging.Filter):
    """Prevent secret values from appearing in log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        secret = os.getenv("OPENAI_API_KEY")
        if secret:
            message = message.replace(secret, "[REDACTED]")
        lowered = message.lower()
        if "openai_api_key=" in lowered and "redacted" not in lowered:
            message = "[REDACTED log line containing API key name]"
        record.msg = message
        record.args = ()
        return True


def configure_logging(level: str) -> None:
    """Initialize reusable standard-library logging."""

    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s "
            "run_id=%(run_id)s stage=%(stage)s status=%(status)s %(message)s",
            defaults={"run_id": "-", "stage": "-", "status": "-"},
        )
    )
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addFilter(RedactingFilter())
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI-powered market analysis")
    parser.add_argument(
        "--config",
        type=Path,
        help="YAML configuration path (relative paths start at the project root)",
    )
    parser.add_argument("--start-date", help="Inclusive analysis start date YYYY-MM-DD")
    parser.add_argument("--end-date", help="Inclusive analysis end date YYYY-MM-DD")
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore raw caches and re-download provider data",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory that will contain outputs/<run_id>/",
    )
    parser.add_argument("--run-id", help="Reuse this run identifier for all artifacts")
    parser.add_argument(
        "--skip-openai",
        action="store_true",
        help="Skip OpenAI calls and write an unavailable interpretation",
    )
    parser.add_argument(
        "--export-web-snapshot",
        action="store_true",
        help=(
            "After the accepted run artifacts exist, serialize the web "
            "dashboard snapshot into web/public/data/"
        ),
    )
    parser.add_argument(
        "--web-snapshot-dir",
        type=Path,
        help=(
            "Optional snapshot directory used only with --export-web-snapshot "
            "(default: web/public/data)"
        ),
    )
    parser.add_argument(
        "--export-run-bundle",
        action="store_true",
        help=(
            "After accepted run artifacts exist, serialize a temporary live-run "
            "bundle next to outputs/<run_id>/bundle. Never writes web/public/data."
        ),
    )
    parser.add_argument(
        "--run-bundle-dir",
        type=Path,
        help="Optional directory used only with --export-run-bundle",
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Developer/demo path using deterministic synthetic data (no internet)",
    )
    parser.add_argument(
        "--log-level",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Override the configured logging level",
    )
    return parser


def _parse_optional_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


def run(config: AppConfig, options: RunOptions) -> ExitCode:
    """Execute the accepted end-to-end workflow."""

    result = execute_analysis(config, options)
    return ExitCode(result.exit_code)


def main(argv: list[str] | None = None) -> int:
    """Load configuration, initialize logging, and run the application."""

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        code = error.code
        if code in (0, None):
            return int(ExitCode.SUCCESS)
        return int(ExitCode.FAILURE)

    overrides: dict[str, object] = {"logging.level": args.log_level}
    if args.output_dir is not None:
        overrides["output.directory"] = str(args.output_dir)
    try:
        start_date = _parse_optional_date(args.start_date)
        end_date = _parse_optional_date(args.end_date)
        config = load_config(args.config, overrides)
        configure_logging(config.logging.level)
        options = RunOptions(
            run_id=args.run_id,
            start_date=start_date,
            end_date=end_date,
            force_refresh=args.force_refresh,
            skip_openai=args.skip_openai,
            fixture=args.fixture,
            export_web_snapshot=args.export_web_snapshot,
            web_snapshot_directory=args.web_snapshot_dir,
            export_run_bundle=args.export_run_bundle,
            run_bundle_directory=args.run_bundle_dir,
        )
        return int(run(config, options))
    except Exception as error:
        print(f"Application startup failed: {error}", file=sys.stderr)
        return int(ExitCode.FAILURE)


if __name__ == "__main__":
    raise SystemExit(main())
