import {
  displayEvidenceMetric,
  displayEvidenceSource,
  uniqueLimitations,
} from "@/lib/dashboard-state";
import { formatEvidenceValue, formatGeneratedAt, formatRunStatus } from "@/lib/format";
import { reportIdentity } from "@/lib/reports";
import type { DashboardSnapshot } from "@/types/market";

export function TechnicalAppendix({ snapshot }: { snapshot: DashboardSnapshot }) {
  const { quant, market } = snapshot;
  const identity = reportIdentity(snapshot);
  const evidence = market?.evidence.length
    ? market.evidence
    : market?.evidence_used;
  const warnings = quant?.data_quality.warnings ?? [];
  const limitations = quant ? uniqueLimitations(quant.limitations) : [];

  return (
    <section id="appendix" className="home-section report-section report-appendix">
      <header className="report-section-head">
        <p className="kicker brutal-label">07 / Technical appendix</p>
        <h2>Methodology &amp; Evidence</h2>
      </header>
      <p className="lede report-appendix-lede">
        Supporting methodology, evidence paths, data-quality warnings, and run
        identity. Collapsed by default.
      </p>

      <details>
        <summary>Methodology &amp; limitations</summary>
        {limitations.length > 0 ? (
          <ul className="notes">
            {limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="caption">No methodology notes recorded for this run.</p>
        )}
      </details>

      <details>
        <summary>AI grounding evidence</summary>
        {evidence && evidence.length > 0 ? (
          <div className="table-wrap">
            <table className="evidence-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Metric</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                {evidence.map((item, index) => (
                  <tr key={`${item.source_section}-${item.metric}-${index}`}>
                    <td>{displayEvidenceSource(item.source_section)}</td>
                    <td>
                      <code>{displayEvidenceMetric(item.metric)}</code>
                    </td>
                    <td>{formatEvidenceValue(item.metric, item.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="caption">No grounded evidence was published for this run.</p>
        )}
      </details>

      <details>
        <summary>Data quality warnings</summary>
        {warnings.length > 0 ? (
          <ul className="notes">
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        ) : (
          <p className="caption">No data-quality warnings recorded.</p>
        )}
      </details>

      <details>
        <summary>Run metadata</summary>
        <dl className="report-metadata">
          <div>
            <dt>run_id</dt>
            <dd>{identity.runId ?? "Unavailable"}</dd>
          </div>
          <div>
            <dt>as_of_date</dt>
            <dd>{identity.asOfDate ?? "Unavailable"}</dd>
          </div>
          <div>
            <dt>generated_at</dt>
            <dd>
              {identity.generatedAt
                ? formatGeneratedAt(identity.generatedAt)
                : "Unavailable"}
            </dd>
          </div>
          <div>
            <dt>quant status</dt>
            <dd>{formatRunStatus(identity.quantStatus)}</dd>
          </div>
          <div>
            <dt>interpretation status</dt>
            <dd>{formatRunStatus(identity.interpretationStatus)}</dd>
          </div>
          <div>
            <dt>schema version</dt>
            <dd>{identity.schemaVersion ?? "Unavailable"}</dd>
          </div>
        </dl>
      </details>

      <p className="disclaimer">
        {market?.disclaimer ??
          "This report is for research and educational purposes only and does not constitute investment advice."}
      </p>
    </section>
  );
}
