import { NextResponse } from "next/server";

import { createServerRunStore } from "@/lib/run-server-store";
import { readRunPdf } from "@/lib/run-status";

export async function GET(
  _request: Request,
  context: { params: Promise<{ token: string }> },
) {
  const { token } = await context.params;
  const store = await createServerRunStore();
  if (!store) {
    return NextResponse.json({ message: "Not found." }, { status: 404 });
  }
  const pdf = await readRunPdf(store, token);
  if (pdf === "missing" || pdf === "expired") {
    return NextResponse.json({ message: "Not found." }, { status: 404 });
  }
  return new NextResponse(Buffer.from(pdf), {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": 'attachment; filename="market_report.pdf"',
      "Cache-Control": "private, no-store",
    },
  });
}
