import { HeroRunButton } from "@/components/HeroRunButton";
import { HeroSystemPreview } from "@/components/HeroSystemPreview";
import { HomeCapabilityIcon } from "@/components/HomeCapabilityIcon";
import { HowItWorksPipeline } from "@/components/HowItWorksPipeline";
import { RunAnalysisButton } from "@/components/RunAnalysisButton";
import { SiteFooter } from "@/components/SiteFooter";
import { TrustAccordion } from "@/components/TrustAccordion";

const CAPABILITIES = [
  {
    header: "01 / PARTICIPATION",
    title: "Market Breadth",
    icon: "breadth" as const,
    identity: "breadth",
    tag: "50DMA · 200DMA · A/D",
    copy: "Measure participation across S&P 500 constituents using accepted 50-day and 200-day moving-average breadth.",
  },
  {
    header: "02 / TREND",
    title: "SPY Trend Structure",
    icon: "trend" as const,
    identity: "trend",
    tag: "SMA20 · SMA50 · SMA200",
    copy: "Track price relative to 20 / 50 / 200-day moving averages and validated trend regime logic.",
  },
  {
    header: "03 / MACRO",
    title: "Sector Rate Sensitivity",
    icon: "rates" as const,
    identity: "rates",
    tag: "OLS · HC3 · DGS10",
    copy: "Estimate sector exposure to changes in the 10-year Treasury yield using one-factor OLS with HC3 robust inference.",
  },
  {
    header: "04 / INTELLIGENCE",
    title: "Grounded AI Interpretation",
    icon: "ai" as const,
    identity: "ai",
    tag: "Structured Output · Evidence Grounding",
    extra: "STRUCTURED · GROUNDED",
    copy: "Transform validated quantitative output into evidence-backed market research without allowing the model to recompute metrics.",
  },
] as const;

const WORKFLOW = [
  {
    number: "01",
    title: "FETCH MARKET DATA",
    accent: "blue",
    copy: "Acquire and validate the latest market inputs.",
    legacy: "Fetch market data",
  },
  {
    number: "02",
    title: "COMPUTE BREADTH & TREND",
    accent: "green",
    copy: "Calculate accepted market participation and SPY trend structure.",
    legacy: "Compute breadth and trend",
  },
  {
    number: "03",
    title: "RUN SECTOR REGRESSIONS",
    accent: "violet",
    copy: "Estimate rate sensitivity using the accepted HC3 regression layer.",
    legacy: "Run sector-rate regressions",
  },
  {
    number: "04",
    title: "VALIDATE OUTPUTS",
    accent: "violet",
    copy: "Check typed schemas and cross-artifact consistency.",
    legacy: "Validate quantitative outputs",
  },
  {
    number: "05",
    title: "GENERATE GROUNDED AI",
    accent: "orange",
    copy: "Interpret only validated quantitative evidence.",
    legacy: "Generate grounded AI interpretation",
  },
  {
    number: "06",
    title: "PUBLISH REPORT",
    accent: "yellow",
    copy: "Assemble the interactive report and downloadable PDF.",
    legacy: "Publish a new report",
  },
] as const;

export function ProductHome() {
  return (
    <div className="home-page">
      <section className="home-hero home-hero-split">
        <div className="home-hero-left">
          <div className="home-hero-copy home-hero-copy-sticky">
            <div className="home-hero-copy-inner">
              <p className="kicker brutal-label">01 / Quantitative market intelligence</p>
              <h1>AI-Powered Market Analysis</h1>
              <p className="lede home-lede">
                Turn U.S. equity market data into validated quantitative signals and
                evidence-grounded AI research.
              </p>
              <p className="lede-secondary">
                Deterministic analytics · Statistical modeling · Grounded AI
              </p>
              <div className="hero-actions">
                <HeroRunButton />
              </div>
              <p className="hero-microcopy">
                Free · No account required · Daily market analysis
              </p>
            </div>
          </div>
        </div>
        <div className="home-hero-right home-hero-engine">
          <HeroSystemPreview />
        </div>
      </section>

      <section id="product" className="home-section">
        <p className="kicker brutal-label">02 / Capabilities</p>
        <h2>What the system analyzes</h2>
        <div className="capability-grid">
          {CAPABILITIES.map((item) => (
            <article
              key={item.title}
              className={`capability-card identity-${item.identity}`}
              tabIndex={0}
            >
              <header className="brutal-card-head">{item.header}</header>
              <div className="brutal-card-body">
                <HomeCapabilityIcon name={item.icon} />
                <h3>{item.title}</h3>
                <p>{item.copy}</p>
                <p className="capability-tag">{item.tag}</p>
                {"extra" in item ? (
                  <p className="visually-hidden">{item.extra}</p>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section id="how-it-works" className="home-section">
        <p className="kicker brutal-label">03 / Architecture</p>
        <h2>How it works</h2>
        <HowItWorksPipeline />
      </section>

      <section id="methodology" className="home-section home-section-light">
        <p className="kicker brutal-label">04 / Method</p>
        <h2>Research methodology</h2>
        <p className="lede">
          Breadth and trend use accepted moving-average windows. Sector rate
          exposure is estimated with one-factor OLS and HC3 robust standard
          errors. AI text may only cite validated quantitative evidence and
          cannot recompute statistics in the browser or the language model.
        </p>
      </section>

      <section className="home-section home-section-light">
        <p className="kicker brutal-label">05 / Trust</p>
        <h2>Built for reproducible market research</h2>
        <TrustAccordion />
      </section>

      <section className="home-section home-workflow-section">
        <div className="home-workflow-intro">
          <p className="kicker brutal-label">06 / Workflow</p>
          <h2>Run the analysis pipeline</h2>
          <p className="lede">
            Anyone can start a free analysis. If today&apos;s validated result
            already exists, it is reused instead of rerunning the pipeline.
          </p>
          <RunAnalysisButton />
        </div>
        <ol className="home-workflow">
          {WORKFLOW.map((step) => (
            <li key={step.number} className={`home-workflow-step accent-${step.accent}`}>
              <span className="home-workflow-number">{step.number}</span>
              <div>
                <h3>{step.title}</h3>
                <p>{step.copy}</p>
                <p className="visually-hidden">{step.legacy}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="home-section home-final-cta home-cta-panel">
        <p className="kicker brutal-label">07 / Run the engine</p>
        <h2>Ready to generate a fresh market analysis?</h2>
        <p className="lede">
          Generate the latest validated daily U.S. market analysis. Free · No
          account required
        </p>
        <div className="hero-actions">
          <RunAnalysisButton label="START ANALYSIS" />
          <span className="visually-hidden">
            <RunAnalysisButton />
          </span>
        </div>
      </section>

      <SiteFooter />
    </div>
  );
}
