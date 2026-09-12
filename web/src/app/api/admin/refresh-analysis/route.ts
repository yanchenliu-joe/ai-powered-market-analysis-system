import { NextResponse } from "next/server";

import { authorizeOwner } from "@/lib/run-auth";
import { executeRunTrigger } from "@/lib/run-trigger";

export async function POST(request: Request) {
  let payload: { secret?: unknown } = {};
  try {
    payload = (await request.json()) as { secret?: unknown };
  } catch {
    payload = {};
  }
  if (!authorizeOwner(payload.secret, process.env.RUN_ANALYSIS_SECRET)) {
    return NextResponse.json(
      { phase: "failure", message: "Admin authorization was rejected." },
      { status: 401 },
    );
  }
  const result = await executeRunTrigger({
    forceRefresh: true,
  });
  return NextResponse.json(result.body, { status: result.status });
}
