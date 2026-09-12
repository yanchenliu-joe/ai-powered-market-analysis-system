"use client";

import { useEffect, useState } from "react";

import {
  PIPELINE_STATUS_LABELS,
  PIPELINE_STEPS,
  type PipelinePhase,
  type RunAnalysisResponse,
} from "@/lib/pipeline";

const POLL_MS = 4000;
const POLL_PHASES = new Set<PipelinePhase>(["queued", "running", "publishing"]);

export function RunAnalysisModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [phase, setPhase] = useState<PipelinePhase>("idle");
  const [message, setMessage] = useState(
    "Generate a fresh quantitative analysis using the latest available daily U.S. market data.",
  );
  const [statusUrl, setStatusUrl] = useState<string | null>(null);
  const [reportUrl, setReportUrl] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [reused, setReused] = useState(false);

  useEffect(() => {
    if (!open || !statusUrl || !POLL_PHASES.has(phase)) {
      return;
    }
    const handle = window.setInterval(async () => {
      try {
        const response = await fetch(statusUrl);
        if (response.status === 404) {
          setPhase("failure");
          setMessage("This report is no longer available.");
          setReportUrl(null);
          setDownloadUrl(null);
          return;
        }
        const body = (await response.json()) as {
          phase?: PipelinePhase;
          message?: string | null;
          reportUrl?: string | null;
          downloadUrl?: string | null;
        };
        if (body.phase) {
          setPhase(body.phase);
        }
        if (body.message) {
          setMessage(body.message);
        }
        setReportUrl(body.reportUrl ?? null);
        setDownloadUrl(body.downloadUrl ?? null);
      } catch {
        setMessage("Waiting for analysis status… This can take a few minutes.");
      }
    }, POLL_MS);
    return () => window.clearInterval(handle);
  }, [open, statusUrl, phase]);

  if (!open) {
    return null;
  }

  const canView =
    (phase === "success" || phase === "partial" || phase === "reused") &&
    Boolean(reportUrl);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPhase("checking");
    setMessage("Checking whether today's validated analysis can be reused…");
    setStatusUrl(null);
    setReportUrl(null);
    setDownloadUrl(null);
    setReused(false);
    try {
      const response = await fetch("/api/run-analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const body = (await response.json()) as RunAnalysisResponse;
      const nextPhase =
        body.reused && (body.phase === "success" || body.phase === "partial")
          ? "reused"
          : body.phase;
      setPhase(nextPhase);
      setReused(Boolean(body.reused));
      setMessage(body.message);
      setReportUrl(body.reportUrl ?? null);
      setDownloadUrl(body.downloadUrl ?? null);
      if (body.phase === "queued" && body.statusUrl) {
        setStatusUrl(body.statusUrl);
      }
    } catch {
      setPhase("failure");
      setMessage("The analysis service could not be reached.");
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="run-analysis-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="brutal-card-head">
          <p className="kicker">Free public analysis</p>
          <h2 id="run-analysis-title">Run Market Analysis</h2>
        </header>
        <p className="caption">
          This system analyzes the latest available daily U.S. equity market
          data using deterministic quantitative models and grounded AI
          interpretation.
        </p>
        <p className="caption">No account required.</p>
        <ol className="pipeline-steps">
          {[
            "01 MARKET DATA",
            "02 BREADTH + TREND",
            "03 SECTOR REGRESSION",
            "04 VALIDATION",
            "05 GROUNDED AI",
            "06 REPORT",
          ].map((label, index) => (
            <li
              key={label}
              className={`step-accent-${["data", "quant", "quant", "validation", "ai", "report"][index]}`}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              {label.slice(3)}
              <span className="visually-hidden">{PIPELINE_STEPS[index]}</span>
            </li>
          ))}
        </ol>
        <p className="caption">
          Analysis typically takes a few minutes when a new daily run is
          required. If today&apos;s validated analysis is already available, it
          may be reused instead of rerunning the pipeline.
        </p>
        <p className="chart-latest status-badge nb-status">
          Status: {PIPELINE_STATUS_LABELS[phase]}
        </p>
        <p className="caption">{message}</p>
        <form onSubmit={submit} className="run-form">
          <div className="hero-actions">
            <button type="submit" className="btn btn-primary">
              Start Analysis
            </button>
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Close
            </button>
          </div>
        </form>
        {phase === "reused" || reused ? (
          <p className="caption">
            Today&apos;s analysis is ready. This report uses today&apos;s
            existing validated market analysis, so no duplicate pipeline run
            was required.
          </p>
        ) : null}
        {phase === "success" && !reused ? (
          <p className="caption">Analysis complete.</p>
        ) : null}
        {phase === "partial" && !reused ? (
          <p className="caption">
            Analysis completed with limited AI interpretation.
          </p>
        ) : null}
        {phase === "rate_limited" ? (
          <p className="caption">
            Please wait before requesting another fresh analysis.
          </p>
        ) : null}
        {phase === "capacity_reached" ? (
          <p className="caption">
            Today&apos;s new-analysis capacity has been reached. Please try
            again later.
          </p>
        ) : null}
        {canView ? (
          <div className="hero-actions">
            <a className="btn btn-data" href={reportUrl ?? undefined}>
              View Report
            </a>
            {downloadUrl ? (
              <a
                className="btn btn-ai"
                href={downloadUrl}
                download="market_report.pdf"
              >
                Download PDF
              </a>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
