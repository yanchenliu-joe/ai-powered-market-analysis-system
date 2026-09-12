const ICONS = {
  breadth: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect className="icon-fill" x="3" y="13" width="3.2" height="7" rx="0.6" />
      <rect className="icon-fill" x="8" y="8" width="3.2" height="12" rx="0.6" />
      <rect className="icon-fill" x="13" y="10" width="3.2" height="10" rx="0.6" />
      <rect className="icon-fill" x="18" y="5" width="3.2" height="15" rx="0.6" />
    </svg>
  ),
  trend: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 16.5 8.2 11l4.1 3.2L21 6.5" fill="none" />
      <path d="M15.2 6.5H21V12" fill="none" />
    </svg>
  ),
  rates: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 19V5" fill="none" />
      <path d="M4 19h16" fill="none" />
      <path d="M7 15.2 11.2 10l3.3 2.4L20 6.8" fill="none" />
      <circle className="icon-fill" cx="11.2" cy="10" r="1.1" />
      <circle className="icon-fill" cx="14.5" cy="12.4" r="1.1" />
    </svg>
  ),
  ai: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="5" y="4" width="14" height="16" rx="1.4" fill="none" />
      <path d="M8 9h8M8 12.2h8M8 15.4h5.2" fill="none" />
    </svg>
  ),
} as const;

export function HomeCapabilityIcon({
  name,
}: {
  name: keyof typeof ICONS;
}) {
  return <span className="capability-icon">{ICONS[name]}</span>;
}
