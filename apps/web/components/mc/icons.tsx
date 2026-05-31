// Icônes stroke (portées depuis le design Claude — mc-icons.jsx).
import type { ReactNode, SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { sw?: number };

const _i =
  (paths: ReactNode) =>
  (p: IconProps = {}) => {
    const { sw, ...rest } = p;
    return (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={sw ?? 1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
        {...rest}
      >
        {paths}
      </svg>
    );
  };

export const Icon = {
  grid: _i(<><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>),
  pulse: _i(<path d="M3 12h4l2-7 4 14 2-7h6" />),
  check: _i(<path d="M20 6 9 17l-5-5" />),
  alert: _i(<path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />),
  clock: _i(<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>),
  coin: _i(<><circle cx="12" cy="12" r="9" /><path d="M14.5 9.5c-.6-.7-1.6-1-2.5-1-1.7 0-3 .9-3 2.2 0 1.2 1 1.8 3 2.3 2 .5 3 1.1 3 2.3 0 1.3-1.3 2.2-3 2.2-1 0-2-.4-2.6-1.1M12 7v10" /></>),
  bolt: _i(<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />),
  play: _i(<path d="M6 4.5v15l13-7.5-13-7.5Z" />),
  pause: _i(<><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></>),
  stop: _i(<rect x="6" y="6" width="12" height="12" rx="2" />),
  back: _i(<path d="M19 12H5M12 19l-7-7 7-7" />),
  chevron: _i(<path d="m9 6 6 6-6 6" />),
  plus: _i(<path d="M12 5v14M5 12h14" />),
  search: _i(<><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></>),
  terminal: _i(<><rect x="3" y="4" width="18" height="16" rx="2" /><path d="m7 9 3 3-3 3M13 15h4" /></>),
  gauge: _i(<><path d="M12 14a2 2 0 1 0 2-2" /><path d="M3.4 18a9 9 0 1 1 17.2 0" /><path d="m14 12 3-3" /></>),
  trash: _i(<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />),
  x: _i(<path d="M18 6 6 18M6 6l12 12" />),
  pr: _i(<><circle cx="6" cy="6" r="2.5" /><circle cx="6" cy="18" r="2.5" /><circle cx="18" cy="18" r="2.5" /><path d="M6 8.5v7M18 15.5V11a4 4 0 0 0-4-4h-3l2.5-2.5M11 7l2.5 2.5" /></>),
  folder: _i(<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.7-.9L9.6 3.9A2 2 0 0 0 7.9 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />),
  layers: _i(<path d="m12 2 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 17l9 5 9-5" />),
  sun: _i(<><circle cx="12" cy="12" r="4.2" /><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" /></>),
  moon: _i(<path d="M21 12.8A8.5 8.5 0 1 1 11.2 3a6.6 6.6 0 0 0 9.8 9.8Z" />),
  logout: _i(<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />),
  spark: _i(<path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8" />),
  sliders: _i(<><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6" /></>),
} as const;
