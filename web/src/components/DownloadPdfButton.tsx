import { MARKET_REPORT_PDF_FILENAME, MARKET_REPORT_PDF_HREF } from "@/lib/pdf";

export function DownloadPdfButton({
  href = MARKET_REPORT_PDF_HREF,
  prominent = false,
}: {
  href?: string;
  prominent?: boolean;
}) {
  return (
    <a
      className={prominent ? "btn btn-primary btn-download" : "btn btn-secondary"}
      href={href}
      download={MARKET_REPORT_PDF_FILENAME}
    >
      Download PDF
    </a>
  );
}
