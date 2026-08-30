import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getProject } from "../api.js";
import { useResource } from "../hooks.js";
import { useI18n } from "../i18n.jsx";
import ProjectNav from "../components/ProjectNav.jsx";
import { ExternalIcon, GitHubIcon, GlobeIcon } from "../components/Icons.jsx";

/** Highlights the contents entry for the heading currently on screen. */
function useScrollSpy(ids, ready) {
  const [active, setActive] = useState(null);
  useEffect(() => {
    if (!ready || ids.length === 0) return;
    const heads = ids.map((id) => document.getElementById(id)).filter(Boolean);
    if (heads.length === 0) return;
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && setActive(e.target.id)),
      { rootMargin: "-96px 0px -68% 0px" }
    );
    heads.forEach((h) => io.observe(h));
    return () => io.disconnect();
  }, [ids.join("|"), ready]);
  return active;
}

/** The run's completion, read off the scroll position. */
function ReadingProgress() {
  const [pct, setPct] = useState(0);
  useEffect(() => {
    const onScroll = () => {
      const h = document.documentElement;
      setPct((h.scrollTop / (h.scrollHeight - h.clientHeight || 1)) * 100);
    };
    addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => removeEventListener("scroll", onScroll);
  }, []);
  return <div className="prog" style={{ width: `${pct}%` }} />;
}

/** One outbound link. A repository and a running deployment are different
 *  promises, so each carries its own label and mark. */
function OutboundLink({ href, icon, title, hint }) {
  return (
    <a className="linkbtn" href={href} target="_blank" rel="noopener noreferrer">
      <span className="linkbtn-mark">{icon}</span>
      <span className="linkbtn-text">
        <b>{title}</b>
        <small>{hint}</small>
      </span>
      <ExternalIcon className="linkbtn-out" />
    </a>
  );
}

export default function ProjectDetail() {
  const { slug } = useParams();
  const { t, lang } = useI18n();
  // `lang` is a dependency: switching language refetches the whole case study
  // rather than translating half a page in place.
  const { data: p, loading, error } = useResource(() => getProject(slug, lang), [slug, lang]);

  useEffect(() => { window.scrollTo(0, 0); }, [slug]);

  const active = useScrollSpy(p?.toc?.map((x) => x.id) ?? [], Boolean(p));

  if (loading) {
    return (
      <>
        <ProjectNav />
        <main className="wrap sec"><span className="label">{t("detail.loading")}</span></main>
      </>
    );
  }

  if (error) {
    return (
      <>
        <ProjectNav />
        <main className="wrap sec">
          <span className="label">{t("detail.missing")}</span>
          <p>{t("detail.missingBody")} <Link to="/">{t("detail.backToWork")}</Link></p>
        </main>
      </>
    );
  }

  const facts = p.metrics?.facts ?? [];
  const updated = new Date(p.updated_at);
  const updatedLabel = updated.toLocaleDateString(lang, {
    year: "numeric", month: "short", day: "numeric",
  });

  return (
    <>
      <ReadingProgress />
      <ProjectNav project={p} />

      <article>
        <header className="head wrap">
          <div className="kicker">
            <span className="pill">{p.domain_label}</span>
            <span className="pill">{p.year}</span>
            {p.client && <span className="pill">{p.client}</span>}
            {p.status === "live" && <span className="pill pill--live"><i />{p.status_label}</span>}
          </div>

          <h1>{p.title}</h1>
          {p.standfirst && <p className="standfirst">{p.standfirst}</p>}

          {/* The date belongs here, under the title — not after the last
              paragraph, where checking it costs a scroll. */}
          <p className="byline">
            <span className="byline-updated">
              {t("detail.updated")}{" "}
              <time dateTime={p.updated_at}>{updatedLabel}</time>
            </span>
          </p>

          {facts.length > 0 && (
            <div className="factbar">
              {facts.map((m) => (
                <div className="fact" key={m.ref || m.label}>
                  <b className="num">{m.value}</b><span>{m.label}</span>
                </div>
              ))}
            </div>
          )}

          <div className="cover">
            {p.cover
              ? <img src={p.cover} alt={p.cover_alt || ""} />
              : <div className="slot">[ HERO IMAGE · 21:9 ]<br />{p.slug}-cover.png</div>}
          </div>
        </header>

        <div className="wrap layout">
          {/* One HTML document from Django: markdown, the embeds the body
              placed by ref, then whatever it never referenced. */}
          <div className="md" dangerouslySetInnerHTML={{ __html: p.body_html }} />

          <aside className="toc">
            {p.toc?.length > 0 && (
              <>
                <span className="label">{t("toc.title")}</span>
                <nav>
                  {p.toc.map((x) => (
                    <a key={x.id} href={`#${x.id}`} aria-current={active === x.id ? "true" : undefined}>
                      {x.title}
                    </a>
                  ))}
                </nav>
              </>
            )}

            {(p.repo_url || p.live_url) && (
              <div className="side-links">
                <span className="label">{t("meta.links")}</span>
                {p.repo_url && (
                  <OutboundLink
                    href={p.repo_url}
                    icon={<GitHubIcon />}
                    title={t("meta.repo")}
                    hint={t("meta.repoHint")}
                  />
                )}
                {p.live_url && (
                  <OutboundLink
                    href={p.live_url}
                    icon={<GlobeIcon />}
                    title={t("meta.live")}
                    hint={t("meta.liveHint")}
                  />
                )}
              </div>
            )}

            {(p.role || p.team || p.duration || p.tags?.length > 0) && (
              <>
                <span className="label side-heading">{t("meta.credits")}</span>
                <dl className="side">
                  {p.role && <><dt>{t("meta.role")}</dt><dd>{p.role}</dd></>}
                  {p.team && <><dt>{t("meta.team")}</dt><dd>{p.team}</dd></>}
                  {p.duration && <><dt>{t("meta.duration")}</dt><dd>{p.duration}</dd></>}
                  {p.tags?.length > 0 && <><dt>{t("meta.stack")}</dt><dd>{p.tags.join(" · ")}</dd></>}
                </dl>
              </>
            )}
          </aside>
        </div>

        <section className="next wrap">
          <div className="next-row">
            {p.prev
              ? <Link className="next-card" to={`/work/${p.prev.slug}`}>
                  <span className="label">{t("nav.prev")}</span><h3>{p.prev.title}</h3>
                </Link>
              : <span />}
            {p.next
              ? <Link className="next-card" to={`/work/${p.next.slug}`}>
                  <span className="label">{t("nav.next")}</span><h3>{p.next.title}</h3>
                </Link>
              : <span />}
          </div>
        </section>

        <footer className="wrap">
          <Link className="label" to="/">← {t("nav.back")}</Link>
        </footer>
      </article>
    </>
  );
}
