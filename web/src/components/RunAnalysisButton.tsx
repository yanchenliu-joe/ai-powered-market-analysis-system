"use client";

export function RunAnalysisButton({
  label = "Run Analysis",
}: {
  label?: string;
}) {
  return (
    <button
      type="button"
      className="btn btn-primary"
      onClick={() => window.dispatchEvent(new Event("open-run-analysis"))}
    >
      {label}
    </button>
  );
}
