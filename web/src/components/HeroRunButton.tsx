"use client";

export function HeroRunButton() {
  return (
    <button
      type="button"
      className="btn btn-primary"
      onClick={() => window.dispatchEvent(new Event("open-run-analysis"))}
    >
      Run New Analysis
    </button>
  );
}
