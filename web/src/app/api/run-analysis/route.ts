import { NextResponse } from "next/server";

import { clientIdentifierFromHeaders, hashClientIdentifier } from "@/lib/run-client";
import { executeRunTrigger } from "@/lib/run-trigger";

export async function POST(request: Request) {
  const clientHash = hashClientIdentifier(clientIdentifierFromHeaders(request.headers));
  const result = await executeRunTrigger({
    clientHash,
  });
  return NextResponse.json(result.body, { status: result.status });
}
