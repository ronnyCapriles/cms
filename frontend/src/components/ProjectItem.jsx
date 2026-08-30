import { Link } from "react-router-dom";

import Reveal from "./Reveal.jsx";
import { useI18n } from "../i18n.jsx";

const Arrow = () => (
  <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
    <path d="M3 11L11 3M11 3H5M11 3v6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="square" />
  </svg>
);

/**
 * One project, one markup, two layouts. Grid and list render the same elements;
 * `.work` carries the view class and CSS re-areas them, so switching view never
 * re-fetches or re-renders. JS only decides the order inside the metric.
 */
export default function ProjectItem({ project, index, view, ...rest }) {
  const { t } = useI18n();
  const { slug, title, summary, cover, cover_alt, domain_label, tags, metric } = project;
  const value = metric?.value ? <b key="v">{metric.value}</b> : null;
  const label = metric?.label ? <span className="m-label" key="l">{metric.label}</span> : null;

  return (
    <Reveal
      as={Link}
      to={`/work/${slug}`}
      className="item"
      delay={(index % 3) + 1}
      data-kind={domain_label}
      {...rest}
    >
      <span className="item-idx">{String(index + 1).padStart(2, "0")}</span>

      <span className="item-media">
        <span className="kind">{domain_label}</span>
        {cover
          ? <img src={cover} alt={cover_alt || ""} loading="lazy" />
          : <span className="slot">[ COVER · 16:10 ]<br />{slug}.png</span>}
      </span>

      <span className="item-body">
        <span className="item-title">{title}</span>
        <span className="item-desc">{summary}</span>
        {tags?.length > 0 && (
          <span className="tags">
            {tags.map((tag) => <span className="tag" key={tag}>{tag}</span>)}
          </span>
        )}
      </span>

      <span className="item-stack">{tags?.join(" · ")}</span>

      <span className="item-metric">
        {view === "list" ? [value, label] : [label, value]}
      </span>

      <span className="item-go">
        <span className="go-label">{t("card.read")}</span> <Arrow />
      </span>
    </Reveal>
  );
}
