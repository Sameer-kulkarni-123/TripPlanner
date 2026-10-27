// A day's stops drawn to scale from their real coordinates (no map tiles, no third-party SDK).
// Straight segments show visiting order only; travel times come from the itinerary agent.

export interface MapStop {
  id: string;
  lat: number;
  lon: number;
  label: string;
  kind: "hotel" | "stop";
  n?: number;
}

const W = 640, H = 230, PAD = 34;
const NICE_KM = [0.2, 0.5, 1, 2, 5, 10, 20, 50];

export function RouteMap({ stops, active, onHover }: {
  stops: MapStop[];
  active?: string | null;
  onHover?: (id: string | null) => void;
}) {
  if (stops.length === 0) return null;
  const lat0 = stops.reduce((s, p) => s + p.lat, 0) / stops.length;
  const k = Math.cos((lat0 * Math.PI) / 180);
  const pts = stops.map((s) => ({ ...s, x: s.lon * k, y: -s.lat }));
  const minX = Math.min(...pts.map((p) => p.x)), maxX = Math.max(...pts.map((p) => p.x));
  const minY = Math.min(...pts.map((p) => p.y)), maxY = Math.max(...pts.map((p) => p.y));
  const spanX = Math.max(maxX - minX, 0.004), spanY = Math.max(maxY - minY, 0.004);
  const scale = Math.min((W - PAD * 2) / spanX, (H - PAD * 2) / spanY);
  const offX = (W - spanX * scale) / 2, offY = (H - spanY * scale) / 2;
  const P = pts.map((p) => ({ ...p, px: offX + (p.x - minX) * scale, py: offY + (p.y - minY) * scale }));

  const pxPerKm = scale / 111.32;
  const barKm = [...NICE_KM].reverse().find((km) => km * pxPerKm <= W * 0.22) ?? NICE_KM[0];
  const barPx = barKm * pxPerKm;

  const path = P.map((p, i) => `${i ? "L" : "M"}${p.px.toFixed(1)} ${p.py.toFixed(1)}`).join(" ");

  return (
    <figure className="routemap">
      <svg viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label={`Map of ${stops.filter((s) => s.kind === "stop").length} stops, to scale`}>
        <defs>
          <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M32 0H0V32" fill="none" className="routemap__grid" />
          </pattern>
        </defs>
        <rect width={W} height={H} fill="url(#grid)" />
        {P.length > 1 && <path d={path} className="routemap__path" />}
        {P.map((p) => {
          const on = active === p.id;
          return (
            <g key={p.id} transform={`translate(${p.px.toFixed(1)} ${p.py.toFixed(1)})`}
              className={`routemap__pt routemap__pt--${p.kind} ${on ? "is-active" : ""}`}
              onMouseEnter={() => onHover?.(p.id)} onMouseLeave={() => onHover?.(null)}>
              <title>{p.label}</title>
              {p.kind === "hotel" ? (
                <>
                  <rect x={-9} y={-9} width={18} height={18} rx={3} />
                  <text y={4}>H</text>
                </>
              ) : (
                <>
                  <circle r={on ? 13 : 11} />
                  <text y={4}>{p.n}</text>
                </>
              )}
            </g>
          );
        })}
        <g transform={`translate(${W - PAD - barPx} ${H - 14})`} className="routemap__scale">
          <path d={`M0 -4V0H${barPx.toFixed(1)}V-4`} />
          <text x={barPx / 2} y={-8}>{barKm < 1 ? `${barKm * 1000} m` : `${barKm} km`}</text>
        </g>
      </svg>
    </figure>
  );
}
