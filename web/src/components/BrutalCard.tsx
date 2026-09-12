import type { ReactNode } from "react";

export type BrutalTone = "blue" | "green" | "violet" | "orange" | "yellow" | "neutral";
export type BrutalShadow = "sm" | "md" | "lg";

export function BrutalCard({
  tone = "neutral",
  title,
  shadow = "md",
  children,
  className = "",
  interactive = false,
}: {
  tone?: BrutalTone;
  title?: string;
  shadow?: BrutalShadow;
  children: ReactNode;
  className?: string;
  interactive?: boolean;
}) {
  return (
    <article
      className={`brutal-card tone-${tone} shadow-${shadow}${interactive ? " is-interactive" : ""}${className ? ` ${className}` : ""}`}
    >
      {title ? <header className="brutal-card-head">{title}</header> : null}
      <div className="brutal-card-body">{children}</div>
    </article>
  );
}
