import { DownloadPdfButton } from "@/components/DownloadPdfButton";
import { HeroRunButton } from "@/components/HeroRunButton";
import {
  collectPresentationAlerts,
  displayEvidenceMetric,
  displayEvidenceSource,
  humanizeAiProse,
  uniqueLimitations,
} from "@/lib/dashboard-state";
import {
  displaySensitivityLabel,
  formatAdvanceDeclineRatio,
  formatBeta,
  formatBreadthMomentum,
  formatBreadthPercent,
  formatCi,
  formatEffect10bp,
  formatEvidenceValue,
  formatGeneratedAt,
  formatPValue,
} from "@/lib/format";
import { reportIdentity } from "@/lib/reports";
import { displaySectorName, orderSectorRegressions } from "@/lib/sectors";
import type { DashboardSnapshot } from "@/types/market";

export function ReportView({
  snapshot,
  pdfHref,
  sample = false,
}: {
  snapshot: DashboardSnapshot;
  pdfHref?: string;
  sample?: boolean;
}) {
  const { quant, market } = snapshot;
  const alerts = collectPresentationAlerts(snapshot);
  const identity = reportIdentity(snapshot);
  const interpretationAvailable = market?.status === "available";
  const evidence = market?.evidence.length
    ? market.evidence
    : market?.evidence_used;
  const sectorRows = quant ? orderSectorRegressions(quant.sector_regressions) : [];

  return (
    <article className="report-page report-page-follow">
      <header className="report-header">
        <p className="kicker">
          {sample ? "Sample report (development snapshot)" : "Generated analysis"}
        </p>
        <h1>Analysis Report</h1>
        <p className="lede-secondary">
          As of {identity.asOfDate ?? "Unavailable"}
          {identity.runId ? ` · Run ID ${identity.runId}` : ""}
          {identity.generatedAt
            ? ` · Generated ${formatGeneratedAt(identity.generatedAt)}`
            : ""}
          {identity.status ? ` · Status ${identity.status}` : ""}
        </p>
        <div className="hero-actions">
          <DownloadPdfButton href={pdfHref} />
          <HeroRunButton />
        </div>
      </header>

      {!snapshot.snapshotConsistent ? (
        <div className="banner banner-critical" role="alert">
          Snapshot identity is inconsistent. Artifacts do not share the same
          run_id and as-of date.
        </div>
      ) : null}

      {alerts
        .filter((item) => item.level === "critical")
        .map((item) => (
          <div className="banner banner-critical" role="alert" key={item.message}>
            {item.message}
          </div>
        ))}

      <section id="ai-analysis-detail">
        <h2>Executive Summary</h2>
        {interpretationAvailable && market?.executive_summary ? (
          <p className="prose">{humanizeAiProse(market.executive_summary)}</p>
        ) : (
          <p className="empty-note">
            AI interpretation was unavailable for this run.
          </p>
        )}
      </section>

      <section>
        <h2>Market Participation</h2>
        {quant ? (
          <ul className="report-metrics">
            <li>
              50DMA Participation:{" "}
              {formatBreadthPercent(quant.breadth.pct_above_50dma)}
            </li>
            <li>
              200DMA Participation:{" "}
              {formatBreadthPercent(quant.breadth.pct_above_200dma)}
            </li>
            <li>
              20D Breadth Momentum:{" "}
              {formatBreadthMomentum(quant.breadth.breadth_momentum_20d)}
            </li>
            <li>
              Advance / Decline Ratio:{" "}
              {formatAdvanceDeclineRatio(quant.breadth.advance_decline_ratio)}
            </li>
          </ul>
        ) : null}
        {interpretationAvailable ? (
          <p className="prose">{humanizeAiProse(market?.market_participation)}</p>
        ) : null}
      </section>

      <section>
        <h2>Trend Conditions</h2>
        {interpretationAvailable ? (
          <p className="prose">{humanizeAiProse(market?.trend_conditions)}</p>
        ) : null}
      </section>

      <section>
        <h2>Sector Rate Sensitivity</h2>
        {interpretationAvailable ? (
          <p className="prose">{humanizeAiProse(market?.sector_rate_risk)}</p>
        ) : null}
        {quant ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Sector</th>
                  <th>Beta</th>
                  <th>95% CI</th>
                  <th>p-value</th>
                  <th>+10bp Effect</th>
                  <th>Significance</th>
                </tr>
              </thead>
              <tbody>
                {sectorRows.map((row) => (
                  <tr key={row.ticker}>
                    <td>{displaySectorName(row.ticker)}</td>
                    <td>{formatBeta(row.beta_yield)}</td>
                    <td>{formatCi(row.ci_95_lower, row.ci_95_upper)}</td>
                    <td>{formatPValue(row.p_value)}</td>
                    <td>{formatEffect10bp(row.effect_10bp)}</td>
                    <td>{displaySensitivityLabel(row.sensitivity_label)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      {quant ? (
        <section>
          <h2>Data Quality</h2>
          <ul className="report-metrics">
            <li>
              Equity coverage: {quant.data_quality.available_equity_tickers} /{" "}
              {quant.data_quality.universe_size}
            </li>
            <li>
              Latest 50DMA valid count: {quant.data_quality.latest_50dma_valid_count}
            </li>
            <li>
              Latest 200DMA valid count:{" "}
              {quant.data_quality.latest_200dma_valid_count}
            </li>
            <li>
              DGS10 usable: {quant.data_quality.dgs10_usable_observation_count} /{" "}
              {quant.data_quality.dgs10_raw_row_count}
            </li>
            <li>
              Sectors valid / insufficient: {quant.data_quality.valid_sector_count}{" "}
              / {quant.data_quality.insufficient_sector_count}
            </li>
          </ul>
          {quant.data_quality.warnings.length > 0 ? (
            <ul className="notes">
              {quant.data_quality.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          ) : (
            <p className="caption">No data-quality warnings recorded.</p>
          )}
        </section>
      ) : null}

      <section>
        <h2 id="methodology">Methodology &amp; Limitations</h2>
        {quant ? (
          <ul className="notes">
            {uniqueLimitations(quant.limitations).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : null}
        {interpretationAvailable ? (
          <p className="prose">
            {humanizeAiProse(market?.risks_and_limitations)}
          </p>
        ) : null}
      </section>

      {interpretationAvailable ? (
        <section>
          <h2>Evidence</h2>
          <details>
            <summary>View evidence</summary>
            <table className="evidence-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Metric</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                {evidence?.map((item, index) => (
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
          </details>
        </section>
      ) : null}

      <section>
        <h2>Disclaimer</h2>
        <p className="disclaimer">
          {market?.disclaimer ??
            "This report is for research and educational purposes only and does not constitute investment advice."}
        </p>
      </section>
    </article>
  );
}
