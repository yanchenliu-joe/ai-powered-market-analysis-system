import { Dashboard } from "@/components/Dashboard";
import { ReportSubnav } from "@/components/ReportSubnav";
import { loadDashboardSnapshot } from "@/lib/data";

export default async function ReportPage() {
  const snapshot = await loadDashboardSnapshot();
  return (
    <>
      <ReportSubnav />
      <Dashboard snapshot={snapshot} sample />
    </>
  );
}
