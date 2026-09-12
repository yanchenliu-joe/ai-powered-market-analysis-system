"use client";

import { useEffect, useState, type ReactNode } from "react";

import { Navbar } from "@/components/Navbar";
import { RunAnalysisModal } from "@/components/RunAnalysisModal";

export function AppShell({ children }: { children: ReactNode }) {
  const [runOpen, setRunOpen] = useState(false);

  useEffect(() => {
    const open = () => setRunOpen(true);
    window.addEventListener("open-run-analysis", open);
    return () => window.removeEventListener("open-run-analysis", open);
  }, []);

  return (
    <>
      <Navbar onRunAnalysis={() => setRunOpen(true)} />
      {children}
      <RunAnalysisModal open={runOpen} onClose={() => setRunOpen(false)} />
    </>
  );
}
