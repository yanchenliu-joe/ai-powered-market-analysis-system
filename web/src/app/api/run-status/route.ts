import { NextResponse } from "next/server";

import { liveRunInfrastructureReady } from "@/lib/run-auth";

export async function GET() {
  const configured = liveRunInfrastructureReady();
  return NextResponse.json({
    configured,
    phase: configured ? "unknown" : "not_configured",
    message: configured
      ? "Use /api/runs/<token>/status for a specific live run."
      : "Live-run infrastructure is not configured.",
  });
}
