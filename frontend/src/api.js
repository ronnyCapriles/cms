/**
 * Every call the front end makes to Django. Same-origin in production; in dev
 * Vite is on :5173 and Django on :8000, hence the explicit base.
 *
 * Language goes out twice on purpose: `?lang=` makes it part of the cache key,
 * `X-Language` covers clients that cannot rewrite URLs. With neither, the
 * server falls back to Accept-Language.
 */
const BASE = import.meta.env.DEV ? "http://localhost:8000" : "";

let current = null;

/** Set by the i18n provider whenever the visitor's language settles. */
export function setApiLanguage(lang) {
  current = lang || null;
}

export function apiLanguage() {
  return current;
}

async function get(path, { lang = current } = {}) {
  const url = new URL(`${BASE}/api${path}`, window.location.origin);
  if (lang) url.searchParams.set("lang", lang);

  const headers = { Accept: "application/json" };
  if (lang) headers["X-Language"] = lang;

  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return res.json();
}

export const getProfile = (lang) => get("/profile/", { lang });
export const getFilters = (lang) => get("/filters/", { lang });
export const getLanguages = () => get("/languages/");
export const getProject = (slug, lang) => get(`/projects/${slug}/`, { lang });

export function getProjects({ domain, tag, year, q, lang } = {}) {
  const params = new URLSearchParams();
  if (domain && domain !== "all") params.set("domain", domain);
  if (tag) params.set("tag", tag);
  if (year) params.set("year", year);
  if (q) params.set("q", q);
  const qs = params.toString();
  return get(`/projects/${qs ? `?${qs}` : ""}`, { lang });
}
