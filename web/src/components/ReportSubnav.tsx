import Link from "next/link";

import { REPORT_NAV_LINKS } from "@/lib/nav";

export function ReportSubnav({ basePath = "/report" }: { basePath?: string }) {
  return (
    <nav className="report-subnav" aria-label="Report sections">
      <div className="report-subnav-inner">
        {REPORT_NAV_LINKS.map((link) => (
          <Link
            key={link.href}
            href={`${basePath}${link.href.slice(link.href.indexOf("#"))}`}
          >
            {link.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
