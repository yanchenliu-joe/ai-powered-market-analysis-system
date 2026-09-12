"use client";

import { useState } from "react";

const PHASES = [
  {
    number: "01",
    title: "MARKET DATA",
    legacy: "Data",
    accent: "blue",
    copy: "Acquire and validate market inputs.",
    details: [
      "U.S. equity market data",
      "Treasury-yield observations",
      "Input validation",
    ],
    concepts: ["Market Data", "Data Validation"],
  },
  {
    number: "02",
    title: "QUANT ENGINE",
    legacy: "Quant Analytics",
    accent: "green",
    copy: "Compute accepted breadth, trend, and sector-rate models.",
    details: [
      "Market breadth",
      "SPY trend structure",
      "HC3 sector regressions",
    ],
    concepts: ["Breadth & Trend", "HC3 Sector Regressions"],
  },
  {
    number: "03",
    title: "VALIDATION",
    legacy: "Validation",
    accent: "violet",
    copy: "Publish only typed, contract-checked quantitative output.",
    details: [
      "Typed schemas",
      "QuantSummary validation",
      "Evidence contract",
    ],
    concepts: ["Validated QuantSummary"],
  },
  {
    number: "04",
    title: "GROUNDED AI",
    legacy: "AI Research",
    accent: "orange",
    copy: "Interpret validated evidence without recomputing metrics.",
    details: [
      "Structured interpretation",
      "Evidence grounding",
      "Graceful degradation",
    ],
    concepts: ["Grounded AI Interpretation"],
  },
  {
    number: "05",
    title: "REPORT",
    legacy: "Research Report",
    accent: "yellow",
    copy: "Interactive analysis plus a downloadable PDF.",
    details: [
      "Interactive analysis",
      "Downloadable PDF",
      "Run-scoped report access",
    ],
    concepts: ["Research Report"],
  },
] as const;

export function HowItWorksPipeline() {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <ol className="pipeline-phases">
      {PHASES.map((phase, index) => {
        const isOpen = expanded === phase.title;
        return (
          <li
            key={phase.title}
            className={`pipeline-phase accent-${phase.accent}${isOpen ? " is-expanded" : ""}`}
          >
            <button
              type="button"
              className="pipeline-phase-card"
              aria-expanded={isOpen}
              onClick={() =>
                setExpanded((current) => (current === phase.title ? null : phase.title))
              }
            >
              <div className="pipeline-phase-layers">
                <div className="pipeline-phase-front">
                  <p className="pipeline-phase-number">{phase.number}</p>
                  <h3>{phase.title}</h3>
                  <p>{phase.copy}</p>
                </div>
                <div className="pipeline-phase-detail">
                  <p className="pipeline-phase-number">{phase.number}</p>
                  <h3>{phase.title}</h3>
                  <ul className="pipeline-detail-list">
                    {phase.details.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              </div>
              <p className="pipeline-phase-hint">
                {isOpen ? "Click to return ←" : "Click to view details →"}
              </p>
              <p className="visually-hidden">{phase.legacy}</p>
              <ul className="visually-hidden">
                {phase.concepts.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ul>
            </button>
            {index < PHASES.length - 1 ? (
              <span className="pipeline-phase-arrow" aria-hidden="true">
                →
              </span>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
