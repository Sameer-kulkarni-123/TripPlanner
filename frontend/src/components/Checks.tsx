import type { ItineraryRequest, ItineraryResult, Severity } from "../api/types";
import { Icon } from "./ui";

const SEV_ORDER: Severity[] = ["error", "warning", "info"];
const SEV_LABEL: Record<Severity, string> = { error: "Must fix", warning: "Worth checking", info: "Good to know" };

export function Checks({ itin, request, extraLimits }: {
  itin: ItineraryResult; request: ItineraryRequest; extraLimits: string[];
}) {
  const errors = itin.validation_issues.filter((i) => i.severity === "error").length;
  const demo = itin.activities.some((a) => a.is_demo_data);
  const ai = itin.activities.some((a) => a.is_ai_suggested);
  // Mirrors the rule in services/planner.py for status "validated".
  const gates = [
    { ok: request.transport.is_confirmed, label: "Outbound and return flights chosen" },
    { ok: request.hotel.is_confirmed, label: "Stay chosen" },
    { ok: errors === 0, label: errors ? `${errors} schedule errors` : "No schedule errors" },
    { ok: !demo && !ai, label: demo ? "Activities are offline demo data" : ai ? "Activities are AI suggestions (estimates)" : "Activities from live inventory" },
  ];
  const limits = [...new Set([...itin.limitations, ...extraLimits])];

  return (
    <div className="panel checks">
      <section className={`verdict is-${itin.plan_status}`}>
        <p className="verdict__label">Plan status</p>
        <h3>{itin.plan_status === "validated" ? "Validated" : itin.plan_status === "failed" ? "Couldn't plan" : "Provisional"}</h3>
        <p>
          {itin.plan_status === "validated"
            ? "Every check passed against confirmed flights and a confirmed stay."
            : "A plan is only marked validated when all four of these hold."}
        </p>
        <ul className="gates">
          {gates.map((g) => (
            <li key={g.label} className={g.ok ? "is-ok" : ""}>
              <span className="gates__mark" aria-hidden="true">{g.ok ? <Icon name="check" size={14} /> : null}</span>
              {g.label}
            </li>
          ))}
        </ul>
      </section>

      {SEV_ORDER.map((sev) => {
        const items = itin.validation_issues.filter((i) => i.severity === sev);
        if (!items.length) return null;
        const list = (
          <ul>
            {items.map((i, k) => (
              <li key={k} className={`sev sev--${sev}`}>
                {i.day_number ? <span className="num">D{i.day_number}</span> : <span className="num">All</span>}
                <span>{i.message}</span>
              </li>
            ))}
          </ul>
        );
        if (sev === "info") {
          return (
            <details key={sev} className="issues">
              <summary><h4>{SEV_LABEL[sev]} <small aria-hidden="true" /><span className="num">{items.length}</span></h4></summary>
              {list}
            </details>
          );
        }
        return (
          <section key={sev} className="issues">
            <h4>{SEV_LABEL[sev]} <span className="num">{items.length}</span></h4>
            {list}
          </section>
        );
      })}

      {itin.assumptions.length > 0 && (
        <section className="issues">
          <h4>Assumptions <span className="num">{itin.assumptions.length}</span></h4>
          <ul className="plain">{itin.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
        </section>
      )}
      {limits.length > 0 && (
        <section className="issues">
          <h4>Limitations <span className="num">{limits.length}</span></h4>
          <ul className="plain">{limits.map((a) => <li key={a}>{a}</li>)}</ul>
        </section>
      )}
      <p className="limit">{itin.cost_summary.basis_note}</p>
    </div>
  );
}
