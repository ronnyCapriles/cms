import { Link } from "react-router-dom";

import Controls from "./Controls.jsx";
import { useI18n } from "../i18n.jsx";

/** The case study's own bar. It sticks rather than floats: on a long read the
 *  crumb is what is worth keeping on screen. */
export default function ProjectNav({ project }) {
  const { t } = useI18n();
  return (
    <nav className="nav nav--project">
      <Link className="back" to="/">← <span>{t("nav.back")}</span></Link>
      {project && (
        <span className="crumb">
          {t("nav.work")} / {project.domain_label} / <span className="crumb-here">{project.title}</span>
        </span>
      )}
      <Controls />
    </nav>
  );
}
