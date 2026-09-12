import { notFound } from "next/navigation";

import { Dashboard } from "@/components/Dashboard";
import { ReportSubnav } from "@/components/ReportSubnav";
import { loadLiveRunSnapshot } from "@/lib/live-run-data";
import { createServerRunStore } from "@/lib/run-server-store";

function UnavailableReport({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <article className="report-page">
      <header className="report-header">
        <p className="kicker">Live run</p>
        <h1>{title}</h1>
        <p className="lede-secondary">{detail}</p>
      </header>
    </article>
  );
}

export default async function LiveReportPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const store = await createServerRunStore();
  if (!store) {
    notFound();
  }
  const result = await loadLiveRunSnapshot(store, token);
  if (result.kind === "expired") {
    return (
      <UnavailableReport
        title="This report has expired"
        detail="Live run artifacts are retained for 7 days. Download the PDF during that window if you need a durable copy."
      />
    );
  }
  if (result.kind === "missing") {
    notFound();
  }
  const pdfHref = `/api/runs/${token}/pdf`;
  return (
    <>
      <ReportSubnav basePath={`/r/${token}`} />
      <Dashboard snapshot={result.snapshot} pdfHref={pdfHref} />
    </>
  );
}
