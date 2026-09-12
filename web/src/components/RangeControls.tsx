"use client";

import type { ChartRange } from "@/lib/range";

const OPTIONS: ChartRange[] = ["1Y", "3Y", "5Y"];

export function RangeControls({
  value,
  onChange,
}: {
  value: ChartRange;
  onChange: (range: ChartRange) => void;
}) {
  return (
    <div className="range-toggle" role="group" aria-label="Chart date range">
      {OPTIONS.map((option) => (
        <button
          key={option}
          type="button"
          className={value === option ? "is-active" : ""}
          onClick={() => onChange(option)}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
