import { useEffect, useId, useRef, type ReactNode } from "react";

// ------------------------------------------------------------------ icons (stroke, 24 grid)
const paths: Record<string, ReactNode> = {
  swap: <path d="M7 4v14m0 0-3-3m3 3 3-3M17 20V6m0 0-3 3m3-3 3 3" />,
  back: <path d="M15 5l-7 7 7 7" />,
  close: <path d="M6 6l12 12M18 6 6 18" />,
  search: <><circle cx="11" cy="11" r="6.5" /><path d="m20 20-4.2-4.2" /></>,
  plan: <><path d="M4 6h16M4 12h10M4 18h7" /></>,
  plane: <path d="M10.5 13.5 4 12l1-2 7 .5L16.5 5c.8-.8 2.2-.8 2.5 0 .3.6 0 1.4-.6 2l-4.4 4.6.5 7-2 1-1.5-6.5-3 3v2.4L7 20l-1-3-3-1 1.4-1H7l3.5-1.5Z" />,
  bed: <><path d="M3 18V6m0 8h18v4M21 14v-2a3 3 0 0 0-3-3h-7v5" /><circle cx="7" cy="11" r="1.6" /></>,
  check: <path d="m5 12.5 4.2 4L19 7" />,
  shield: <path d="M12 3 5 6v5c0 4.4 3 8.3 7 10 4-1.7 7-5.6 7-10V6l-7-3Z" />,
  arrow: <path d="M5 12h14m0 0-5-5m5 5-5 5" />,
  minus: <path d="M6 12h12" />,
  plus: <path d="M12 6v12M6 12h12" />,
  chevron: <path d="m9 6 6 6-6 6" />,
  refresh: <path d="M19 8a7.5 7.5 0 1 0 1 6M19 4v4h-4" />,
  chat: <path d="M5 5h14v10H10l-4 4v-4H5z" />,
  spark: <path d="M12 3c.6 4.6 3.4 7.4 8 8-4.6.6-7.4 3.4-8 8-.6-4.6-3.4-7.4-8-8 4.6-.6 7.4-3.4 8-8Z" />,
  calendar: <><rect x="4" y="5.5" width="16" height="14" rx="2.5" /><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4" /></>,
  users: <><circle cx="9" cy="8.5" r="3" /><path d="M3.5 19c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5" /><path d="M15.5 5.8a3 3 0 0 1 0 5.4M17.5 14.4c1.6.7 2.6 2.3 3 4.6" /></>,
  pin: <><path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11Z" /><circle cx="12" cy="10" r="2.3" /></>,
  route: <><circle cx="6" cy="18" r="2" /><circle cx="18" cy="6" r="2" /><path d="M8 18h7a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h7" /></>,
  bulb: <><path d="M9 17.5h6M10 21h4" /><path d="M12 3a6 6 0 0 0-3.6 10.8c.7.6 1.1 1.4 1.1 2.2h5c0-.8.4-1.6 1.1-2.2A6 6 0 0 0 12 3Z" /></>,
  github: <path d="M9 19c-4.3 1.4-4.3-2.5-6-3m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1.1-.3-3.5 1.3a12.3 12.3 0 0 0-6.2 0C6.5 2.8 5.4 3.1 5.4 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21" />,
};

export function Icon({ name, size = 20, className }: { name: keyof typeof paths; size?: number; className?: string }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

// ------------------------------------------------------------------ controls
export function Stepper({ label, value, min, max, onChange, hint }: {
  label: string; value: number; min: number; max: number; onChange: (v: number) => void; hint?: string;
}) {
  return (
    <div className="stepper">
      <div className="stepper__label">
        <span>{label}</span>
        {hint && <small>{hint}</small>}
      </div>
      <div className="stepper__ctrl">
        <button type="button" aria-label={`Fewer ${label.toLowerCase()}`} disabled={value <= min} onClick={() => onChange(value - 1)}>
          <Icon name="minus" size={16} />
        </button>
        <output aria-live="polite">{value}</output>
        <button type="button" aria-label={`More ${label.toLowerCase()}`} disabled={value >= max} onClick={() => onChange(value + 1)}>
          <Icon name="plus" size={16} />
        </button>
      </div>
    </div>
  );
}

export function Segmented<T extends string>({ value, options, onChange, label, size = "md" }: {
  value: T;
  options: { value: T; label: string; sub?: string }[];
  onChange: (v: T) => void;
  label: string;
  size?: "md" | "sm";
}) {
  return (
    <div className={`seg seg--${size}`} role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={value === o.value}
          className={value === o.value ? "is-on" : ""} onClick={() => onChange(o.value)}>
          <span>{o.label}</span>
          {o.sub && <small>{o.sub}</small>}
        </button>
      ))}
    </div>
  );
}

export function Chip({ on, children, onClick, tone }: { on: boolean; children: ReactNode; onClick: () => void; tone?: "avoid" }) {
  return (
    <button type="button" aria-pressed={on} className={`chip ${on ? "is-on" : ""} ${tone ? `chip--${tone}` : ""}`} onClick={onClick}>
      {children}
    </button>
  );
}

export function Toggle({ on, onChange, label, hint }: { on: boolean; onChange: (v: boolean) => void; label: string; hint?: string }) {
  return (
    <label className="toggle">
      <span className="toggle__text">
        <span>{label}</span>
        {hint && <small>{hint}</small>}
      </span>
      <input type="checkbox" checked={on} onChange={(e) => onChange(e.target.checked)} />
      <span className="toggle__track" aria-hidden="true"><span /></span>
    </label>
  );
}

/** Bottom sheet on phones, centred dialog on larger screens. */
export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    (ref.current?.querySelector<HTMLElement>("input") ?? ref.current?.querySelector<HTMLElement>("button"))?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="sheet" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet__panel" role="dialog" aria-modal="true" aria-label={title} ref={ref}>
        <div className="sheet__grip" aria-hidden="true" />
        <header className="sheet__head">
          <h2>{title}</h2>
          <button type="button" className="icon-btn" aria-label="Close" onClick={onClose}><Icon name="close" /></button>
        </header>
        {children}
      </div>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <p className="empty__title">{title}</p>
      {children && <div className="empty__body">{children}</div>}
    </div>
  );
}

/** The Planless mark: a map pin with a flight path, filled with the brand gradient. */
export function Mark({ size = 26, className }: { size?: number; className?: string; inverse?: boolean }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <defs>
        <linearGradient id={`pl${id}`} x1="10" y1="54" x2="54" y2="10" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#4F8CFF" />
          <stop offset="0.5" stopColor="#9B72FF" />
          <stop offset="1" stopColor="#FF7A8A" />
        </linearGradient>
      </defs>
      <rect x="1.5" y="1.5" width="61" height="61" rx="17" fill="#17171A" stroke={`url(#pl${id})`} strokeWidth="2" />
      <path d="M32 12c-8.8 0-15.5 6.6-15.5 15.1C16.5 38.6 32 52 32 52s15.5-13.4 15.5-24.9C47.5 18.6 40.8 12 32 12Z" fill={`url(#pl${id})`} />
      <path d="M24.5 33.5 39.5 21" stroke="#17171A" strokeWidth="3.2" strokeLinecap="round" />
      <path d="M33.6 21.4 39.5 21l-.4 5.9" fill="none" stroke="#17171A" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
