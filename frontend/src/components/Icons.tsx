interface IconProps {
  size?: number;
  className?: string;
}

const base = (size: number, className?: string) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.9,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  className,
});

export function LearnIcon({ size = 22, className }: IconProps) {
  return (
    <svg {...base(size, className)}>
      <path d="M12 3 2 8l10 5 10-5-10-5Z" />
      <path d="M6 10v5c0 1.7 2.7 3 6 3s6-1.3 6-3v-5" />
    </svg>
  );
}

export function MapIcon({ size = 22, className }: IconProps) {
  return (
    <svg {...base(size, className)}>
      <circle cx="6" cy="6" r="2.4" />
      <circle cx="18" cy="7" r="2.4" />
      <circle cx="9" cy="18" r="2.4" />
      <path d="M8 7.2 15.6 6.6M7.4 15.9 8.2 8.3M11 17l5.4-8" />
    </svg>
  );
}

export function SunIcon({ size = 20, className }: IconProps) {
  return (
    <svg {...base(size, className)}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );
}

export function MoonIcon({ size = 20, className }: IconProps) {
  return (
    <svg {...base(size, className)}>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
    </svg>
  );
}

export function SparkleIcon({ size = 18, className }: IconProps) {
  return (
    <svg {...base(size, className)}>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6.3 6.3l2.1 2.1M15.6 15.6l2.1 2.1M17.7 6.3l-2.1 2.1M8.4 15.6l-2.1 2.1" />
    </svg>
  );
}

export function CameraIcon({ size = 18, className }: IconProps) {
  return (
    <svg {...base(size, className)}>
      <path d="M4 8.5A2 2 0 0 1 6 6.5h1.2l.9-1.4A1 1 0 0 1 9 4.6h6a1 1 0 0 1 .9.5l.9 1.4H18a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" />
      <circle cx="12" cy="12.5" r="3" />
    </svg>
  );
}

export function CheckIcon({ size = 16, className }: IconProps) {
  return (
    <svg {...base(size, className)}>
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

export function StarIcon({ size = 15, className }: IconProps) {
  return (
    <svg {...base(size, className)} fill="currentColor" stroke="none">
      <path d="M12 2.5l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 20.9l1.1-6.5L2.6 9.3l6.5-.9L12 2.5Z" />
    </svg>
  );
}

export function ArrowIcon({ size = 18, className }: IconProps) {
  return (
    <svg {...base(size, className)}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

export function CloseIcon({ size = 20, className }: IconProps) {
  return (
    <svg {...base(size, className)}>
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

export function PlayIcon({ size = 16, className }: IconProps) {
  return (
    <svg {...base(size, className)} fill="currentColor" stroke="none">
      <path d="M7 4.5v15l12-7.5-12-7.5Z" />
    </svg>
  );
}

export function SearchIcon({ size = 18, className }: IconProps) {
  return (
    <svg {...base(size, className)}>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4.5 4.5" />
    </svg>
  );
}

export function AlertIcon({ size = 18, className }: IconProps) {
  return (
    <svg {...base(size, className)}>
      <path d="M12 4.2 2.8 19.5h18.4L12 4.2Z" />
      <path d="M12 10v4M12 17h.01" />
    </svg>
  );
}

export function InfoIcon({ size = 16, className }: IconProps) {
  return (
    <svg {...base(size, className)}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </svg>
  );
}

export function ChatIcon({ size = 22, className }: IconProps) {
  return (
    <svg {...base(size, className)}>
      <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8A2.5 2.5 0 0 1 17.5 16H10l-4.5 4v-4H6.5A2.5 2.5 0 0 1 4 13.5Z" />
      <path d="M8 8.5h8M8 11.5h5" />
    </svg>
  );
}
