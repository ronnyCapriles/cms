import Reveal from "./Reveal.jsx";
import { useI18n } from "../i18n.jsx";

/**
 * "What I run" — Capability rows from the CMS. Numbering follows the list, not
 * the data, so reordering in the admin renumbers the cards. No cards, no
 * section; a blank heading falls back to the chrome string.
 */
export default function Capabilities({ profile }) {
  const { t } = useI18n();
  const items = profile?.capabilities ?? [];
  if (items.length === 0) return null;

  return (
    <section className="sec wrap" id="capabilities">
      <Reveal className="sec-head">
        <h2>{profile.capabilities_title || t("caps.title")}</h2>
        <span className="rule" />
        <span className="label">{profile.capabilities_kicker || t("caps.kicker")}</span>
      </Reveal>
      <Reveal className="caps">
        {items.map((cap, i) => (
          <article className="cap" key={`${cap.title}-${i}`}>
            <div className="idx">EDGE {String(i + 1).padStart(2, "0")}</div>
            <h3>{cap.title}</h3>
            <p>{cap.body}</p>
            {cap.tools?.length > 0 && (
              <ul>{cap.tools.map((tool) => <li key={tool}>{tool}</li>)}</ul>
            )}
          </article>
        ))}
      </Reveal>
    </section>
  );
}
