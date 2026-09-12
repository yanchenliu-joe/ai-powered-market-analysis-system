import { DownloadPdfButton } from "@/components/DownloadPdfButton";
import { HeroRunButton } from "@/components/HeroRunButton";
import { formatHeaderDate, formatRunStatus } from "@/lib/format";
import { reportIdentity } from "@/lib/reports";
import type { DashboardSnapshot } from "@/types/market";

export function ReportHeader({
  snapshot,
  pdfHref,
  sample = false,
}: {
  snapshot: DashboardSnapshot;
  pdfHref?: string;
  sample?: boolean;
}) {
  const identity = reportIdentity(snapshot);
  const status = formatRunStatus(identity.status);
  const statusKey = identity.status ?? "unavailable";

  return (
    <header className="report-masthead">
      <p className="kicker brutal-label report-masthead-kicker">
        {sample ? "Sample report · Development snapshot" : "Analysis report"}
      </p>
      <h1>U.S. Equity Market Analysis</h1>
      <p className="lede report-masthead-lede">
        Daily quantitative market research combining deterministic analytics,
        statistical modeling, and grounded AI interpretation.
      </p>
      <dl className="report-masthead-meta">
        <div>
          <dt>As of</dt>
          <dd>{formatHeaderDate(identity.asOfDate)}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd className={`report-status report-status-${statusKey}`}>
            <span className="report-status-dot" aria-hidden="true" />
            {status}
          </dd>
        </div>
        <div>
          <dt>Generated</dt>
          <dd>{formatHeaderDate(identity.generatedAt)}</dd>
        </div>
        <div>
          <dt>Run ID</dt>
          <dd>{identity.runId ?? "Unavailable"}</dd>
        </div>
      </dl>
      <div className="report-masthead-actions">
        <DownloadPdfButton href={pdfHref} prominent />
        <HeroRunButton />
      </div>
    </header>
  );
}
