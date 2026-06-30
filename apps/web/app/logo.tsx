// The brand mark, inline so it stays crisp at any size and shares the palette.
// Mirrors app/icon.svg (the favicon) — keep the two in sync if either changes.
export function Logo({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden>
      <rect width="48" height="48" rx="11" fill="#0B0B0D" />
      <path
        d="M16 9 H27 L34 16 V37 Q34 39 32 39 H16 Q14 39 14 37 V11 Q14 9 16 9 Z"
        fill="#E11428"
      />
      <path d="M27 9 L34 16 L27 16 Z" fill="#E8B339" />
      <rect x="19" y="21" width="11" height="2.4" rx="1.2" fill="#E8B339" />
      <rect x="19" y="27" width="11" height="2.4" rx="1.2" fill="#E8B339" />
      <rect x="19" y="33" width="6" height="2.4" rx="1.2" fill="#E8B339" />
    </svg>
  );
}
