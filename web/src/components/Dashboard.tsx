import { BreadthChart } from "@/components/BreadthChart";
import { ReportHeader } from "@/components/ReportHeader";
import { Section } from "@/components/Section";
import { SectorChart } from "@/components/SectorChart";
import { TechnicalAppendix } from "@/components/TechnicalAppendix";
import { TrendChart } from "@/components/TrendChart";
import { collectPresentationAlerts, humanizeAiProse } from "@/lib/dashboard-state";
import {
  displayTrendRegime,
  formatAdvanceDeclineRatio,
  formatBreadthMomentum,
  formatBreadthPercent,
  formatHeaderDate,
} from "@/lib/format";
import type { DashboardSnapshot } from "@/types/market";

export function Dashboard({
  snapshot,
  pdfHref,
  sample = false,
}: {
  snapshot: DashboardSnapshot;
  pdfHref?: string;
  sample?: boolean;
}) {
  const { quant, market, breadthSeries, trendSeries } = snapshot;
  const interpretationAvailable = market?.status === "available";
  const alerts = collectPresentationAlerts(snapshot);
  const criticalAlerts = alerts.filter((item) => item.level === "critical");
  const noticeAlerts = alerts.filter((item) => item.level === "notice");
  const asOf = quant?.run_metadata.as_of_date ?? market?.as_of_date;
  const evidenceCount = (market?.evidence.length
    ? market.evidence
    : market?.evidence_used)?.length ?? 0;

  return (
    <div className="page page-report">
      <ReportHeader snapshot={snapshot} pdfHref={pdfHref} sample={sample} />
      {criticalAlerts.length > 0 ? (
        <div className="banner banner-critical" role="alert">
          <p className="banner-title">Dashboard data issue</p>
          {criticalAlerts.map((item) => (
            <p key={item.message}>{item.message}</p>
          ))}
        </div>
      ) : null}

      {noticeAlerts.map((item) => (
        <div className="banner" role="status" key={item.message}>
          {item.message}
        </div>
      ))}

      {quant ? (
        <Section
          id="overview"
          index="01 / Market state"
          kicker="Validated quantitative output"
          title="Overall Market State"
          variant="quant"
        >
          <p className="lede">
            Headline is the accepted SPY trend regime. No composite score is
            computed.
          </p>
          <dl className="state-grid">
            <div>
              <dt>Trend</dt>
              <dd>{displayTrendRegime(quant.trend.trend_regime)}</dd>
            </div>
            <div>
              <dt>50DMA Participation</dt>
              <dd>{formatBreadthPercent(quant.breadth.pct_above_50dma)}</dd>
            </div>
            <div>
              <dt>200DMA Participation</dt>
              <dd>{formatBreadthPercent(quant.breadth.pct_above_200dma)}</dd>
            </div>
            <div>
              <dt>20D Breadth Momentum</dt>
              <dd>{formatBreadthMomentum(quant.breadth.breadth_momentum_20d)}</dd>
            </div>
            <div>
              <dt>Advance / Decline Ratio</dt>
              <dd>
                {formatAdvanceDeclineRatio(quant.breadth.advance_decline_ratio)}
              </dd>
            </div>
            <div>
              <dt>As of</dt>
              <dd>{formatHeaderDate(asOf)}</dd>
            </div>
          </dl>
        </Section>
      ) : null}

      <Section
        id="ai-analysis"
        index="02 / AI interpretation"
        kicker="Grounded AI interpretation"
        title="Grounded AI Market Brief"
        variant="ai"
      >
        {interpretationAvailable && market?.executive_summary ? (
          <>
            <p className="lede">
              Generated exclusively from validated quantitative outputs.
            </p>
            <p className="prose brief-prose">
              {humanizeAiProse(market.executive_summary)}
            </p>
            <dl className="report-ai-stats">
              <div>
                <dt>Confirmed signals</dt>
                <dd>{market.key_confirmed_signals.length}</dd>
              </div>
              <div>
                <dt>Risk flags</dt>
                <dd>{market.risk_flags.length}</dd>
              </div>
              <div>
                <dt>Evidence references</dt>
                <dd>{evidenceCount}</dd>
              </div>
            </dl>
          </>
        ) : (
          <p className="empty-note">
            AI interpretation was unavailable for this run. Quantitative
            results remain valid.
          </p>
        )}
      </Section>

      <Section
        id="breadth"
        index="03 / Market breadth"
        kicker="Validated quantitative output"
        title="Market breadth"
        variant="quant"
      >
        <BreadthChart data={breadthSeries} />
      </Section>

      <Section
        id="trend"
        index="04 / SPY trend"
        kicker="Validated quantitative output"
        title="SPY trend structure"
        variant="quant"
      >
        <TrendChart
          data={trendSeries}
          trendRegime={quant?.trend.trend_regime ?? null}
        />
      </Section>

      {quant ? (
        <Section
          id="sector-rates"
          index="05 / Sector rates"
          kicker="Validated quantitative output"
          title="Sector rate sensitivity"
          variant="quant"
        >
          <SectorChart rows={quant.sector_regressions} />
        </Section>
      ) : null}

      {quant ? (
        <Section
          id="data-quality"
          index="06 / Data quality"
          kicker="Validated quantitative output"
          title="Data quality"
          variant="quant"
        >
          <dl className="quality quality-compact">
            <div>
              <dt>Data coverage</dt>
              <dd>
                {quant.data_quality.available_equity_tickers} /{" "}
                {quant.data_quality.universe_size} equities
              </dd>
            </div>
            <div>
              <dt>Valid regressions</dt>
              <dd>
                {quant.data_quality.valid_sector_count} /{" "}
                {quant.data_quality.available_sector_tickers}
              </dd>
            </div>
            <div>
              <dt>DGS10 usable observations</dt>
              <dd>{quant.data_quality.dgs10_usable_observation_count}</dd>
            </div>
            <div>
              <dt>Warnings</dt>
              <dd>{quant.data_quality.warnings.length}</dd>
            </div>
          </dl>
        </Section>
      ) : null}

      <TechnicalAppendix snapshot={snapshot} />
    </div>
  );
}
