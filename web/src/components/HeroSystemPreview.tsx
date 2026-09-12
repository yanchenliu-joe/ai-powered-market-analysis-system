const HERO_FLOW = [
  {
    id: "data",
    title: "MARKET DATA",
    display: "Market Data",
    badge: "Deterministic",
    tone: "blue",
    items: [
      "Daily U.S. equity prices",
      "Treasury-yield observations",
      "Validated input handling",
    ],
  },
  {
    id: "quant",
    title: "QUANT ENGINE",
    display: "Quantitative Engine",
    short: "Quant Engine",
    badge: "Validated",
    tone: "green",
    items: [
      "Market breadth",
      "SPY trend structure",
      "HC3 sector-rate regressions",
    ],
  },
  {
    id: "validation",
    title: "VALIDATION",
    display: "Validation Layer",
    short: "Validated Signals",
    badge: "Structured",
    tone: "violet",
    items: ["Typed schemas", "Consistency checks", "Evidence pack"],
  },
  {
    id: "ai",
    title: "GROUNDED AI",
    display: "Grounded AI",
    badge: "Evidence-grounded",
    tone: "orange",
    items: [
      "Validated evidence only",
      "Structured interpretation",
      "No metric recomputation",
    ],
  },
  {
    id: "report",
    title: "REPORT",
    display: "Research Report",
    short: "Grounded AI Report",
    badge: "Deliverable",
    tone: "yellow",
    items: ["Interactive analysis", "Research narrative", "Downloadable PDF"],
  },
] as const;

export function HeroSystemPreview() {
  return (
    <aside className="hero-preview" aria-label="Analysis Engine">
      <p className="kicker brutal-label">Analysis Engine</p>
      <p className="visually-hidden">System flow</p>
      <ol className="hero-preview-stack">
        {HERO_FLOW.map((step, index) => (
          <li key={step.id}>
            <article className={`hero-preview-card brutal-card tone-${step.tone}`}>
              <header className="brutal-card-head">{step.title}</header>
              <div className="brutal-card-body">
                <span className="hero-preview-badge">{step.badge}</span>
                <strong>{step.display}</strong>
                {"short" in step ? (
                  <span className="visually-hidden">{step.short}</span>
                ) : null}
                <ul className="hero-preview-detail-list">
                  {step.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </article>
            {index < HERO_FLOW.length - 1 ? (
              <span className="hero-preview-arrow" aria-hidden="true">
                ↓
              </span>
            ) : null}
          </li>
        ))}
      </ol>
    </aside>
  );
}
