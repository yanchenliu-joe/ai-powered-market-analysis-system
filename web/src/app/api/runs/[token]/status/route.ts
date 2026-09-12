import { NextResponse } from "next/server";

import { createServerRunStore } from "@/lib/run-server-store";
import { readRunManifest, toPublicStatus } from "@/lib/run-status";

export async function GET(
  _request: Request,
  context: { params: Promise<{ token: string }> },
) {
  const { token } = await context.params;
  const store = await createServerRunStore();
  if (!store) {
    return NextResponse.json({ message: "Not found." }, { status: 404 });
  }
  const manifest = await readRunManifest(store, token);
  if (manifest === "invalid" || manifest === "missing" || manifest === "expired") {
    return NextResponse.json({ message: "Not found." }, { status: 404 });
  }
  return NextResponse.json(toPublicStatus(token, manifest));
}
