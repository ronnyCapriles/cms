import { Link } from "react-router-dom";
import { useEffect, useState } from "react";

import Controls from "./Controls.jsx";
import { useI18n } from "../i18n.jsx";

export default function Nav({ profile }) {
  const { t } = useI18n();
  const [stuck, setStuck] = useState(false);

  useEffect(() => {
    const onScroll = () => setStuck(window.scrollY > 24);
    onScroll();
    addEventListener("scroll", onScroll, { passive: true });
    return () => removeEventListener("scroll", onScroll);
  }, []);

  return (
    <nav className="nav" data-stuck={stuck}>
      <Link className="brand" to="/">
        <span className="brand-node" />
        <span className="brand-name">{profile?.name || " "}</span>
      </Link>

      <div className="nav-links">
        <a href="/#work">{t("nav.work")}</a>
        <a href="/#about">{t("nav.about")}</a>
        <a href="/#elsewhere">{t("nav.elsewhere")}</a>
        <a href="/#contact">{t("nav.contact")}</a>
        {profile?.cv && (
          <a className="cv" href={profile.cv} download>{t("nav.cv")}</a>
        )}
      </div>

      <Controls />

      {profile?.availability && (
        <div className="status"><i />{profile.availability}</div>
      )}
    </nav>
  );
}
