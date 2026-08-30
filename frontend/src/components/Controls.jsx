import { useState } from "react";

import { applyMode, currentMode } from "../prefs.js";
import { LANGS, useI18n } from "../i18n.jsx";

const Moon = () => (
  <svg className="icon-moon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z"
      stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
  </svg>
);

const Sun = () => (
  <svg className="icon-sun" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <circle cx="12" cy="12" r="4.2" stroke="currentColor" strokeWidth="1.7" />
    <path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.2 5.2l1.6 1.6M17.2 17.2l1.6 1.6M18.8 5.2l-1.6 1.6M6.8 17.2l-1.6 1.6"
      stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
  </svg>
);

/** Language control and mode toggle. Shared by both navs. */
export default function Controls() {
  const { lang, setLang, t } = useI18n();
  const [mode, setMode] = useState(currentMode);

  const isLight = mode === "light";

  return (
    <div className="controls">
      <div className="seg" role="group" aria-label={t("a11y.lang")}>
        {LANGS.map((code) => (
          <button
            key={code}
            type="button"
            aria-pressed={lang === code}
            onClick={() => setLang(code)}
          >
            {code.toUpperCase()}
          </button>
        ))}
      </div>

      <button
        type="button"
        className="icon-btn"
        aria-pressed={isLight}
        onClick={() => setMode(applyMode(isLight ? "dark" : "light"))}
      >
        <span className="sr">{t(isLight ? "a11y.theme.toDark" : "a11y.theme.toLight")}</span>
        <Moon />
        <Sun />
      </button>
    </div>
  );
}
