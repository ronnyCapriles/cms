import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { setApiLanguage } from "./api.js";
import { read, write } from "./prefs.js";

/**
 * Static chrome copy, EN / ES. Only the chrome lives here — project copy, the
 * bio, metrics and capability cards are CMS content, translated in Django.
 *
 * The `caps.*` and `cta.headline` keys are what a page falls back to while
 * those CMS fields are still blank, i.e. a fresh install.
 */
export const STRINGS = {
  en: {
    "nav.work": "Work", "nav.about": "About", "nav.elsewhere": "Elsewhere", "nav.contact": "Contact",
    "nav.cv": "CV",
    "nav.back": "All work", "nav.prev": "← Previous", "nav.next": "Next →",
    "a11y.theme.toLight": "Switch to light mode", "a11y.theme.toDark": "Switch to dark mode",
    "a11y.grid": "Grid view", "a11y.list": "List view", "a11y.lang": "Language / Idioma",
    "a11y.filter": "Filter projects", "a11y.view": "View",
    "hero.scroll": "Scroll",
    "about.title": "Upstream", "about.kicker": "01 / About",
    "portrait.node": "Node · Self", "portrait.status": "Status · Streaming",
    "stat.projects": "Projects shipped", "stat.years": "Years covered", "stat.tools": "Tools in anger",
    "work.title": "Selected work", "work.kicker": "02 / Projects", "work.shown": "shown",
    "work.search": "Filter stack…", "work.searchLabel": "Filter by stack or title",
    "work.empty": "Nothing matches that filter.", "work.clear": "Clear filters",
    "caps.title": "What I run", "caps.kicker": "03 / Capabilities",
    "social.title": "Elsewhere", "social.kicker": "04 / Profiles",
    "social.go": "Visit", "social.write": "Write", "social.email": "Email",
    "cta.headline": "Let's move\nsome *data*",
    "cta.button": "Start a conversation", "cta.cv": "Download CV",
    "card.read": "Read",
    "toc.title": "On this page",
    "meta.role": "Role", "meta.team": "Team", "meta.duration": "Duration",
    "meta.stack": "Stack", "meta.links": "Links",
    "meta.repo": "Repository", "meta.live": "Live site",
    "meta.repoHint": "Source on GitHub", "meta.liveHint": "Opens in a new tab",
    "meta.credits": "Credits",
    "detail.updated": "Updated", "detail.impact": "Measured impact",
    "detail.loading": "Loading…", "detail.missing": "Not found",
    "detail.missingBody": "That project isn't published.", "detail.backToWork": "Back to all work →",
    "404.label": "404", "404.title": "No node here",
    "404.body": "That path isn't in the graph.", "404.back": "Back to the start →",
    "filter.all": "All",
  },
  es: {
    "nav.work": "Proyectos", "nav.about": "Sobre mí", "nav.elsewhere": "En la red", "nav.contact": "Contacto",
    "nav.cv": "CV",
    "nav.back": "Proyectos", "nav.prev": "← Anterior", "nav.next": "Siguiente →",
    "a11y.theme.toLight": "Cambiar a modo claro", "a11y.theme.toDark": "Cambiar a modo oscuro",
    "a11y.grid": "Vista de cuadrícula", "a11y.list": "Vista de lista", "a11y.lang": "Language / Idioma",
    "a11y.filter": "Filtrar proyectos", "a11y.view": "Vista",
    "hero.scroll": "Desliza",
    "about.title": "Aguas arriba", "about.kicker": "01 / Sobre mí",
    "portrait.node": "Nodo · Yo", "portrait.status": "Estado · Transmitiendo",
    "stat.projects": "Proyectos entregados", "stat.years": "Años cubiertos", "stat.tools": "Herramientas en uso",
    "work.title": "Proyectos", "work.kicker": "02 / Proyectos", "work.shown": "visibles",
    "work.search": "Filtrar stack…", "work.searchLabel": "Filtrar por stack o título",
    "work.empty": "Nada coincide con ese filtro.", "work.clear": "Limpiar filtros",
    "caps.title": "Lo que opero", "caps.kicker": "03 / Capacidades",
    "social.title": "En la red", "social.kicker": "04 / Perfiles",
    "social.go": "Visitar", "social.write": "Escribir", "social.email": "Correo",
    "cta.headline": "Movamos\nalgunos *datos*",
    "cta.button": "Conversemos", "cta.cv": "Descargar CV",
    "card.read": "Leer",
    "toc.title": "En esta página",
    "meta.role": "Rol", "meta.team": "Equipo", "meta.duration": "Duración",
    "meta.stack": "Stack", "meta.links": "Enlaces",
    "meta.repo": "Repositorio", "meta.live": "Sitio en vivo",
    "meta.repoHint": "Código en GitHub", "meta.liveHint": "Se abre en otra pestaña",
    "meta.credits": "Créditos",
    "detail.updated": "Actualizado", "detail.impact": "Impacto medido",
    "detail.loading": "Cargando…", "detail.missing": "No encontrado",
    "detail.missingBody": "Ese proyecto no está publicado.", "detail.backToWork": "Volver a proyectos →",
    "404.label": "404", "404.title": "Aquí no hay nodo",
    "404.body": "Esa ruta no está en el grafo.", "404.back": "Volver al inicio →",
    "filter.all": "Todos",
  },
};

export const LANGS = Object.keys(STRINGS);

const I18nContext = createContext({ lang: "en", setLang: () => {}, t: (k) => k });

/** `es-419`, `ES` and `es` all mean `es`, if we ship `es`. */
function supported(tag) {
  const base = String(tag || "").split(/[-_]/)[0].toLowerCase();
  return STRINGS[base] ? base : null;
}

/**
 * The language to start in, most specific first: a stored choice, then
 * <html lang> (Django resolved it from Accept-Language), then the browser's
 * own list, then English. Only the toggle writes to storage.
 */
function initialLang() {
  return (
    supported(read("lang"))
    || supported(document.documentElement.lang)
    || (navigator.languages || [navigator.language]).map(supported).find(Boolean)
    || "en"
  );
}

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(initialLang);

  /* During render, not in an effect: the API must know the language before the
     first fetch leaves. */
  if (typeof setApiLanguage === "function") setApiLanguage(lang);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((next) => {
    const value = supported(next) || "en";
    document.documentElement.lang = value;
    setApiLanguage(value);
    // Only an explicit choice is remembered.
    write("lang", value);
    setLangState(value);
  }, []);

  /* Fall through to English rather than a raw key: a missing string should read
     as untranslated, not broken. */
  const t = useCallback((key) => STRINGS[lang]?.[key] ?? STRINGS.en[key] ?? key, [lang]);

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}
