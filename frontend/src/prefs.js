/**
 * Visitor preferences: mode, language, work view. Stored under the `df-` prefix,
 * with every access wrapped — some privacy modes throw instead of returning null.
 *
 * Two axes ride on <html>: data-theme (a|b|c) is the design direction Django
 * stamps; data-mode (dark|light) is the visitor's, persisted here.
 */
export function read(key, fallback = null) {
  try {
    return localStorage.getItem(`df-${key}`) ?? fallback;
  } catch {
    return fallback;
  }
}

export function write(key, value) {
  try {
    localStorage.setItem(`df-${key}`, value);
  } catch {
    /* storage disabled — the preference just does not persist */
  }
}

/** The mode the document is currently in, without consulting storage. */
export function currentMode() {
  return document.documentElement.dataset.mode === "light" ? "light" : "dark";
}

/** Apply a mode and remember it. Fires `df:mode` so the canvas hero, which
 *  paints outside React, can re-read its colours. */
export function applyMode(mode) {
  const next = mode === "light" ? "light" : "dark";
  document.documentElement.dataset.mode = next;
  write("mode", next);
  dispatchEvent(new CustomEvent("df:mode", { detail: next }));
  return next;
}

/** The mode at boot: stored choice first, then the OS preference. */
export function initialMode() {
  const saved = read("mode");
  if (saved === "light" || saved === "dark") return saved;
  return matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}
