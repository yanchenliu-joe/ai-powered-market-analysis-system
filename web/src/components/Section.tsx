import type { ReactNode } from "react";

export function Section({
  id,
  index,
  kicker,
  title,
  children,
  variant = "default",
}: {
  id?: string;
  index?: string;
  kicker: string;
  title: string;
  children: ReactNode;
  variant?: "default" | "quant" | "ai";
}) {
  return (
    <section
      id={id}
      className={`home-section report-section report-section-${variant}`}
    >
      <header className="report-section-head">
        <p className="kicker brutal-label">{index ?? kicker}</p>
        <p className="visually-hidden">{kicker}</p>
        <h2>{title}</h2>
      </header>
      {children}
    </section>
  );
}
