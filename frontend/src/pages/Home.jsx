import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

import { getFilters, getProfile, getProjects } from "../api.js";
import { useResource } from "../hooks.js";
import { read, write } from "../prefs.js";
import { useI18n } from "../i18n.jsx";
import Nav from "../components/Nav.jsx";
import Hero from "../components/Hero.jsx";
import Ticker from "../components/Ticker.jsx";
import Filters from "../components/Filters.jsx";
import ProjectItem from "../components/ProjectItem.jsx";
import Capabilities from "../components/Capabilities.jsx";
import Headline from "../components/Headline.jsx";
import Elsewhere from "../components/Elsewhere.jsx";
import Reveal from "../components/Reveal.jsx";

export default function Home() {
  const { t, lang } = useI18n();
  // The API answers in one language, so every resource re-fetches when the
  // toggle moves. Chrome strings switch on their own.
  const { data: profile } = useResource(() => getProfile(lang), [lang]);
  const { data: facets } = useResource(() => getFilters(lang), [lang]);

  const { hash } = useLocation();
  useEffect(() => {
    if (!hash) return;
    document.getElementById(hash.slice(1))?.scrollIntoView();
  }, [hash, profile]);

  const [domain, setDomain] = useState("all");
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [view, setView] = useState(() => (read("view") === "list" ? "list" : "grid"));

  useEffect(() => {
    const id = setTimeout(() => setDebounced(query), 180);
    return () => clearTimeout(id);
  }, [query]);

  const { data: projects, loading } = useResource(
    () => getProjects({ domain, q: debounced, lang }),
    [domain, debounced, lang]
  );

  const { data: allProjects } = useResource(() => getProjects({ lang }), [lang]);
  const total = allProjects?.count ?? 0;
  const results = projects?.results ?? [];

  /* Swapping view neither re-fetches nor re-renders, but it should not snap
     either — the items get a staggered beat on the way in. */
  const workRef = useRef(null);
  const [animating, setAnimating] = useState(false);

  function changeView(next) {
    if (next === view) return;
    setView(next);
    write("view", next);
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    setAnimating(true);
  }

  useEffect(() => {
    if (!animating) return;
    const id = setTimeout(() => setAnimating(false), 900);
    return () => clearTimeout(id);
  }, [animating]);

  const stats = useMemo(() => {
    if (!allProjects) return [];
    const years = allProjects.results.map((p) => p.year).filter(Boolean);
    return [
      { value: String(allProjects.count), label: t("stat.projects") },
      {
        value: years.length ? String(Math.max(...years) - Math.min(...years) + 1) : "0",
        label: t("stat.years"),
      },
      {
        value: String(new Set(allProjects.results.flatMap((p) => p.tags)).size),
        label: t("stat.tools"),
      },
    ];
  }, [allProjects, t]);

  /* The eyebrow's third slot: the years the work actually covers. */
  const span = useMemo(() => {
    const years = allProjects?.results.map((p) => p.year).filter(Boolean) ?? [];
    if (years.length === 0) return "";
    const lo = Math.min(...years), hi = Math.max(...years);
    return lo === hi ? String(lo) : `${lo} — ${hi}`;
  }, [allProjects]);

  const stack = useMemo(
    () => [...new Set(allProjects?.results.flatMap((p) => p.tags) ?? [])],
    [allProjects]
  );

  return (
    <>
      <Nav profile={profile} />
      <main id="top">
        <Hero profile={profile} stats={stats} span={span} />

        <Ticker items={stack} />

        {profile?.bio_html && (
          <section className="sec wrap" id="about">
            <Reveal className="sec-head">
              <h2>{t("about.title")}</h2>
              <span className="rule" />
              <span className="label">{t("about.kicker")}</span>
            </Reveal>
            <div className="about">
              <Reveal className="prose" dangerouslySetInnerHTML={{ __html: profile.bio_html }} />
              <Reveal as="figure" delay={2} className="portrait">
                {profile.portrait
                  ? <img src={profile.portrait} alt={profile.name} />
                  : <div className="slot">[ PORTRAIT · 4:5 ]<br />your-photo.jpg</div>}
                <figcaption className="meta">
                  <span>{t("portrait.node")}</span><span>{t("portrait.status")}</span>
                </figcaption>
              </Reveal>
            </div>
          </section>
        )}

        <section className="sec wrap" id="work">
          <Reveal className="sec-head">
            <h2>{t("work.title")}</h2>
            <span className="rule" />
            <span className="label">{t("work.kicker")}</span>
          </Reveal>

          {facets && (
            <Filters
              domains={facets.domains}
              active={domain}
              onChange={setDomain}
              query={query}
              onQuery={setQuery}
              count={results.length}
              total={total}
              view={view}
              onView={changeView}
            />
          )}

          <div
            className={`work view-${view}`}
            ref={workRef}
            data-animating={animating}
            aria-busy={loading}
          >
            {results.map((p, i) => (
              <ProjectItem
                key={p.slug}
                project={p}
                index={i}
                view={view}
                style={animating ? { animationDelay: `${i * 45}ms` } : undefined}
              />
            ))}
          </div>

          {!loading && results.length === 0 && (
            <p className="empty">
              {t("work.empty")}{" "}
              <button className="linkish" onClick={() => { setDomain("all"); setQuery(""); }}>
                {t("work.clear")}
              </button>
            </p>
          )}
        </section>

        <Capabilities profile={profile} />

        <Elsewhere profile={profile} />

        <section className="sec wrap contact" id="contact">
          <Reveal as="h2">
            <Headline text={profile?.cta_headline || t("cta.headline")} />
          </Reveal>
          <Reveal className="contact-row" delay={2}>
            {profile?.email && (
              <a className="btn" href={`mailto:${profile.email}`}>{t("cta.button")}</a>
            )}
            {profile?.cv && <a className="btn btn--ghost" href={profile.cv}>{t("cta.cv")}</a>}
            {profile?.email && <span className="label">{profile.email}</span>}
          </Reveal>
        </section>

        <footer className="wrap">
          <span className="label">{profile?.name}</span>
        </footer>
      </main>
    </>
  );
}
