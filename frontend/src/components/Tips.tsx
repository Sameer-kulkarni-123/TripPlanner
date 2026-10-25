import type { LocalTip, LocalTips } from "../api/types";
import type { Settled } from "../lib/trip";
import { Empty } from "./ui";

const ORDER: LocalTip["category"][] = ["scams", "getting_around", "money", "safety", "culture", "food", "timing"];

function Sources({ list }: { list: { title: string; url: string; domain: string }[] }) {
  return (
    <p className="tip__src">
      {list.map((s, i) => (
        <span key={s.url}>
          {i > 0 && ", "}
          <a href={s.url} target="_blank" rel="noreferrer" title={s.title}>{s.domain}</a>
        </span>
      ))}
    </p>
  );
}

export function Tips({ res, city }: { res: Settled<LocalTips>; city: string }) {
  if (!res.ok) {
    return (
      <div className="panel">
        <Empty title="Local tips aren't available.">
          <p>{res.error}</p>
        </Empty>
      </div>
    );
  }
  const d = res.data;
  const groups = ORDER.map((c) => ({ c, items: d.tips.filter((t) => t.category === c) })).filter((g) => g.items.length);

  return (
    <div className="panel tips">
      <header className="tips__head">
        <h2>What travellers say about {city}</h2>
        {d.summary && <p>{d.summary}</p>}
      </header>

      {groups.map((g) => (
        <section key={g.c} className={`tips__group tips__group--${g.c}`}>
          <h3>{g.items[0].category_label}</h3>
          <ul>
            {g.items.map((t) => (
              <li key={t.title} className="tip">
                <p className="tip__title">{t.title}</p>
                <p className="tip__advice">{t.advice}</p>
                <Sources list={t.sources} />
              </li>
            ))}
          </ul>
        </section>
      ))}

      {!d.tips.length && d.sources.length > 0 && (
        <section className="tips__group">
          <h3>Pages found</h3>
          <ul>
            {d.sources.map((s) => (
              <li key={s.url} className="tip">
                <a className="tip__title" href={s.url} target="_blank" rel="noreferrer">{s.title}</a>
                <p className="tip__advice">{s.snippet}</p>
                <p className="tip__src">{s.domain}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!d.tips.length && !d.sources.length && <Empty title={`Nothing useful came up for ${city}.`} />}

      {d.limitations.map((l) => <p key={l} className="limit">{l}</p>)}
      {d.tips.length > 0 && d.sources.length > 0 && (
        <details className="tips__all">
          <summary>All {d.sources.length} pages used</summary>
          <ul>
            {d.sources.map((s) => (
              <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{s.title}</a> <span>{s.domain}</span></li>
            ))}
          </ul>
        </details>
      )}
      <p className="limit">
        Found with Tavily web search{d.tips.length ? " and summarised by Gemini" : ""}. These are other travellers'
        experiences, not checked facts. Each tip links to where it came from.
      </p>
    </div>
  );
}
