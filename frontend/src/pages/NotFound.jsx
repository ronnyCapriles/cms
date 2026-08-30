import { Link } from "react-router-dom";

import ProjectNav from "../components/ProjectNav.jsx";
import { useI18n } from "../i18n.jsx";

export default function NotFound() {
  const { t } = useI18n();
  return (
    <>
      <ProjectNav />
      <main className="wrap sec">
        <span className="label">{t("404.label")}</span>
        <h1 className="notfound-title">{t("404.title")}</h1>
        <p className="notfound-body">
          {t("404.body")} <Link to="/">{t("404.back")}</Link>
        </p>
      </main>
    </>
  );
}
