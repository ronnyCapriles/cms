import Reveal from "./Reveal.jsx";
import { useI18n } from "../i18n.jsx";

const Arrow = () => (
  <svg width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden="true">
    <path d="M3 11L11 3M11 3H5M11 3v6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="square" />
  </svg>
);

/* Keyed by the lower-cased link name in the CMS. Anything not listed here
   still renders, with the generic mark. */
const MARKS = {
  github: <path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.61.07-.61 1 .07 1.53 1.03 1.53 1.03.9 1.53 2.34 1.09 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.56-1.11-4.56-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02a9.5 9.5 0 0 1 5 0c1.91-1.29 2.75-1.02 2.75-1.02.55 1.37.2 2.39.1 2.64.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.85v2.74c0 .27.18.58.69.48A10 10 0 0 0 12 2Z" />,
  linkedin: <path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5ZM3 9.5h4v11H3v-11Zm6.5 0h3.83v1.5h.05a4.2 4.2 0 0 1 3.78-2.08c4.04 0 4.79 2.66 4.79 6.12v5.46h-4v-4.84c0-1.16-.02-2.64-1.61-2.64-1.61 0-1.86 1.26-1.86 2.56v4.92h-4v-11Z" />,
  kaggle: <path d="M8.2 3v11.2l5.1-5.2h3.3l-5.3 5.3 5.5 6.7h-3.3l-4-5-1.3 1.3V21H5.6V3h2.6Z" />,
};

const GENERIC = <path d="M12 3.2a8.8 8.8 0 1 0 0 17.6 8.8 8.8 0 0 0 0-17.6Zm0 0c-2.4 2.1-3.6 5-3.6 8.8s1.2 6.7 3.6 8.8c2.4-2.1 3.6-5 3.6-8.8S14.4 5.3 12 3.2ZM3.6 12h16.8" />;

function Mark({ name }) {
  const glyph = MARKS[name.toLowerCase()];
  return (
    <span className="link-mark">
      <svg viewBox="0 0 24 24" fill={glyph ? "currentColor" : "none"}
        stroke={glyph ? "none" : "currentColor"} strokeWidth="1.6" aria-hidden="true">
        {glyph || GENERIC}
      </svg>
    </span>
  );
}

const EnvelopeMark = () => (
  <span className="link-mark">
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="2.6" y="4.8" width="18.8" height="14.4" rx="2" stroke="currentColor" strokeWidth="1.7" />
      <path d="m3.4 6.6 8.6 6 8.6-6" stroke="currentColor" strokeWidth="1.7" />
    </svg>
  </span>
);

/** Strip the scheme so the handle reads as a handle, not a URL. */
const handle = (url) => url.replace(/^https?:\/\//, "").replace(/\/$/, "");

/** Driven by the profile's `links` JSON plus its email, so adding a profile is
 *  an admin edit. */
export default function Elsewhere({ profile }) {
  const { t } = useI18n();
  const links = Object.entries(profile?.links || {}).filter(([, url]) => url);
  if (links.length === 0 && !profile?.email) return null;

  return (
    <section className="sec wrap" id="elsewhere">
      <Reveal className="sec-head">
        <h2>{t("social.title")}</h2>
        <span className="rule" />
        <span className="label">{t("social.kicker")}</span>
      </Reveal>

      <Reveal className="links">
        {links.map(([name, url]) => (
          <a className="link" href={url} key={name} rel="me noopener" target="_blank">
            <Mark name={name} />
            <span>
              <span className="link-name">{name}</span>
              <span className="link-handle">{handle(url)}</span>
            </span>
            <span className="link-go">{t("social.go")} <Arrow /></span>
          </a>
        ))}

        {profile?.email && (
          <a className="link" href={`mailto:${profile.email}`}>
            <EnvelopeMark />
            <span>
              <span className="link-name">{t("social.email")}</span>
              <span className="link-handle">{profile.email}</span>
            </span>
            <span className="link-go">{t("social.write")} <Arrow /></span>
          </a>
        )}
      </Reveal>
    </section>
  );
}
