import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <div>
          <p className="site-footer-brand">AI-Powered Market Analysis</p>
          <p>Quantitative analytics + grounded AI research</p>
        </div>
        <nav aria-label="Footer">
          <Link href="/#methodology">Methodology</Link>
          <Link href="/#how-it-works">How It Works</Link>
        </nav>
      </div>
    </footer>
  );
}
