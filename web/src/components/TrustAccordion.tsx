"use client";

import { useState } from "react";

const PRINCIPLES = [
  {
    number: "01",
    title: "DETERMINISTIC",
    display: "Deterministic analytics",
    accent: "green",
    copy: "Same accepted inputs produce the same quantitative output.",
    details: [
      "Market breadth, trend, and regression outputs come from accepted Python logic",
      "The language model does not recompute quantitative metrics",
      "Reused inputs produce the same deterministic quantitative layer",
    ],
  },
  {
    number: "02",
    title: "VALIDATED",
    display: "Structured validation",
    accent: "violet",
    copy: "Typed schemas guard published artifacts.",
    details: [
      "Typed schemas validate published quantitative and AI artifacts",
      "Snapshot identity checks prevent mixed run outputs",
      "Malformed or inconsistent artifacts are rejected before presentation",
    ],
  },
  {
    number: "03",
    title: "GROUNDED",
    display: "Evidence-grounded AI",
    accent: "orange",
    copy: "AI text is constrained to accepted evidence.",
    details: [
      "AI interpretation may cite only validated evidence paths",
      "Evidence values must correspond to accepted quantitative outputs",
      "The model cannot invent unsupported metrics or recalculate statistics",
    ],
  },
  {
    number: "04",
    title: "RESILIENT",
    display: "Graceful degradation",
    accent: "blue",
    copy: "Quantitative results survive AI degradation.",
    details: [
      "Quantitative outputs remain available even if AI interpretation fails",
      "Partial runs degrade gracefully instead of fabricating results",
      "Reports preserve validated numerical results independently of LLM availability",
    ],
  },
] as const;

export function TrustAccordion() {
  const [open, setOpen] = useState<string | null>(null);

  return (
    <ol className="trust-list">
      {PRINCIPLES.map((item) => {
        const expanded = open === item.title;
        return (
          <li key={item.title} className={`trust-item accent-${item.accent}`}>
            <button
              type="button"
              className="trust-item-trigger"
              aria-expanded={expanded}
              onClick={() =>
                setOpen((current) => (current === item.title ? null : item.title))
              }
            >
              <span className="trust-item-number">{item.number}</span>
              <div className="trust-item-copy">
                <h3>{item.title}</h3>
                <p className="visually-hidden">{item.display}</p>
                <p>{item.copy}</p>
              </div>
              <span className="trust-item-icon" aria-hidden="true">
                {expanded ? "−" : "+"}
              </span>
            </button>
            <ul
              className={`trust-item-detail${expanded ? " is-open" : ""}`}
              aria-hidden={!expanded}
            >
              {item.details.map((detail) => (
                <li key={detail}>{detail}</li>
              ))}
            </ul>
          </li>
        );
      })}
    </ol>
  );
}
