import { useEffect, useRef, useState } from "react";

/** Fetch once, with loading and error state. */
export function useResource(fn, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true }));
    fn()
      .then((data) => live && setState({ data, loading: false, error: null }))
      .catch((error) => live && setState({ data: null, loading: false, error }));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

/**
 * Adds `.in` once the element scrolls into view. Honours reduced motion.
 *
 * `.rv` starts at opacity 0, so a reveal that never fires is invisible content.
 * Anything already on screen at mount is revealed synchronously rather than
 * waiting on the observer — which matters for elements that mount late.
 */
export function useReveal() {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.classList.add("in");
      return;
    }

    const box = el.getBoundingClientRect();
    if (box.top < innerHeight && box.bottom > 0) {
      el.classList.add("in");
      return;
    }

    const io = new IntersectionObserver(
      ([e]) => e.isIntersecting && (el.classList.add("in"), io.disconnect()),
      { threshold: 0.08, rootMargin: "0px 0px -6% 0px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return ref;
}
