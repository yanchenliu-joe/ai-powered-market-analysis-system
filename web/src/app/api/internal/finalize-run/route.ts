import { NextResponse } from "next/server";

import { finalizeLiveRun, type FinalizeRunInput } from "@/lib/run-finalize";
import { createServerRunStore } from "@/lib/run-server-store";

export async function POST(request: Request) {
  const store = await createServerRunStore();
  if (!store) {
    return NextResponse.json(
      { ok: false, message: "Blob store is not configured." },
      { status: 503 },
    );
  }
  let body: FinalizeRunInput;
  try {
    body = (await request.json()) as FinalizeRunInput;
  } catch {
    return NextResponse.json({ ok: false, message: "Invalid JSON." }, { status: 400 });
  }
  if (!body?.run_id || !body.finalize_nonce) {
    return NextResponse.json(
      { ok: false, message: "run_id and finalize_nonce are required." },
      { status: 400 },
    );
  }
  const result = await finalizeLiveRun(store, body);
  if (!result.ok) {
    return NextResponse.json({ ok: false, message: result.message }, { status: result.status });
  }
  return NextResponse.json({ ok: true });
}
