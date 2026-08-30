import { useI18n } from "../i18n.jsx";

const GridIcon = () => (
  <svg viewBox="0 0 14 14" fill="currentColor" aria-hidden="true">
    <rect x="0" y="0" width="6" height="6" rx="1" /><rect x="8" y="0" width="6" height="6" rx="1" />
    <rect x="0" y="8" width="6" height="6" rx="1" /><rect x="8" y="8" width="6" height="6" rx="1" />
  </svg>
);

const ListIcon = () => (
  <svg viewBox="0 0 14 14" fill="currentColor" aria-hidden="true">
    <rect x="0" y="1" width="14" height="2.4" rx="1" />
    <rect x="0" y="5.8" width="14" height="2.4" rx="1" />
    <rect x="0" y="10.6" width="14" height="2.4" rx="1" />
  </svg>
);

/** Domain chips, stack filter, result count and view switch. All the state
 *  lives in the page; this only reports changes. */
export default function Filters({
  domains, active, onChange, query, onQuery, count, total, view, onView,
}) {
  const { t } = useI18n();

  return (
    <div className="toolbar">
      <div className="filter-chips" role="group" aria-label={t("a11y.filter")}>
        <button className="chip" aria-pressed={active === "all"} onClick={() => onChange("all")}>
          {t("filter.all")}
        </button>
        {domains
          .filter((d) => d.count > 0)
          .map((d) => (
            <button
              key={d.value}
              className="chip"
              aria-pressed={active === d.value}
              onClick={() => onChange(d.value)}
            >
              {d.label}
            </button>
          ))}

        <label className="search">
          <span aria-hidden="true">⌕</span>
          <input
            type="search"
            value={query}
            placeholder={t("work.search")}
            aria-label={t("work.searchLabel")}
            onChange={(e) => onQuery(e.target.value)}
          />
        </label>
      </div>

      <div className="toolbar-end">
        <span className="filter-count">
          {String(count).padStart(2, "0")} / {String(total).padStart(2, "0")} {t("work.shown")}
        </span>

        <div className="viewswitch" role="group" aria-label={t("a11y.view")}>
          <button type="button" aria-pressed={view === "grid"} onClick={() => onView("grid")}>
            <span className="sr">{t("a11y.grid")}</span><GridIcon />
          </button>
          <button type="button" aria-pressed={view === "list"} onClick={() => onView("list")}>
            <span className="sr">{t("a11y.list")}</span><ListIcon />
          </button>
        </div>
      </div>
    </div>
  );
}
