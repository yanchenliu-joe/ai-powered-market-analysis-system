"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ThemeToggle } from "@/components/ThemeToggle";
import { MOBILE_NAV_LINKS, NAV_LINKS } from "@/lib/nav";

const SECTION_IDS = ["product", "how-it-works", "methodology"] as const;

export function Navbar({
  onRunAnalysis,
}: {
  onRunAnalysis: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [activeHash, setActiveHash] = useState("");

  useEffect(() => {
    const sections = SECTION_IDS.map((id) => document.getElementById(id)).filter(
      (node): node is HTMLElement => Boolean(node),
    );
    if (sections.length === 0) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible?.target.id) {
          setActiveHash(`/#${visible.target.id}`);
        }
      },
      { rootMargin: "-35% 0px -50% 0px", threshold: [0.15, 0.4] },
    );
    for (const section of sections) {
      observer.observe(section);
    }
    return () => observer.disconnect();
  }, []);

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link className="navbar-brand" href="/">
          AI-Powered Market Analysis
        </Link>
        <nav className="navbar-links" aria-label="Primary navigation">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={activeHash === link.href ? "is-active" : undefined}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="navbar-actions">
          <ThemeToggle />
          <button type="button" className="btn btn-primary" onClick={onRunAnalysis}>
            Run Analysis
          </button>
          <button
            type="button"
            className="navbar-menu"
            aria-expanded={open}
            aria-controls="mobile-nav"
            onClick={() => setOpen((value) => !value)}
          >
            Menu
          </button>
        </div>
      </div>
      {open ? (
        <nav id="mobile-nav" className="navbar-mobile" aria-label="Mobile navigation">
          {MOBILE_NAV_LINKS.map((link) => (
            <Link key={link.href} href={link.href} onClick={() => setOpen(false)}>
              {link.label}
            </Link>
          ))}
          <button type="button" className="btn btn-primary" onClick={onRunAnalysis}>
            Run Analysis
          </button>
        </nav>
      ) : null}
    </header>
  );
}
