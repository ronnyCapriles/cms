import { useEffect, useRef } from "react";

import FlowField from "./FlowField.jsx";
import Reveal from "./Reveal.jsx";
import { useI18n } from "../i18n.jsx";

/** Counts a number up once it scrolls into view. */
function Counter({ value }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const target = parseFloat(value);
    if (Number.isNaN(target) || matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.textContent = value;
      return;
    }
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      const decimals = target % 1 !== 0 ? 1 : 0;
      const start = performance.now();
      const step = (now) => {
        const p = Math.min(1, (now - start) / 1100);
        el.textContent = (target * (1 - (1 - p) ** 3)).toFixed(decimals);
        if (p < 1) requestAnimationFrame(step);
        else el.textContent = value;
      };
      requestAnimationFrame(step);
    }, { threshold: 0.6 });
    io.observe(el);
    return () => io.disconnect();
  }, [value]);
  return <b className="num" ref={ref}>0</b>;
}

export default function Hero({ profile, stats, span }) {
  const { t } = useI18n();

  return (
    <header className="hero">
      <FlowField />
      <div className="wrap">
        <Reveal className="hero-eyebrow">
          <span className="label">{profile?.role}</span>
          <span className="rule" />
          <span className="label">{profile?.location}</span>
          <span className="rule" />
          <span className="label num">{span || profile?.availability}</span>
        </Reveal>

        <Reveal as="blockquote" className="quote" delay={1}>
          <span className="mark">“</span>
          {profile?.hero_quote}
          <span className="mark">”</span>
          <span className="caret" />
        </Reveal>

        {profile?.hero_quote_attribution && (
          <Reveal className="attrib" delay={2}>{profile.hero_quote_attribution}</Reveal>
        )}

        <div className="hero-foot">
          <Reveal className="whoami" delay={3}>
            <div className="name">{profile?.name}</div>
            <p className="role">{profile?.intro}</p>
          </Reveal>

          {stats?.length > 0 && (
            <Reveal className="stats" delay={4}>
              {stats.map((s) => (
                <div className="stat" key={s.label}>
                  <Counter value={s.value} />
                  <span>{s.label}</span>
                </div>
              ))}
            </Reveal>
          )}
        </div>
      </div>
      <div className="scrollcue">{t("hero.scroll")}</div>
    </header>
  );
}
