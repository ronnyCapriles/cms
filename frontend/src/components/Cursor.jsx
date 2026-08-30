import { useEffect } from "react";

/**
 * A blend-mode dot with a ring that lags behind it; the ring grows over anything
 * clickable. Off for touch and for reduced motion.
 */
export default function Cursor() {
  useEffect(() => {
    if (matchMedia("(pointer: coarse)").matches) return;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const dot = document.getElementById("cursor");
    const ring = document.getElementById("cursor-ring");
    if (!dot || !ring) return;

    let mx = -50, my = -50, rx = -50, ry = -50, running = false, raf = null;

    function loop() {
      rx += (mx - rx) * 0.18;
      ry += (my - ry) * 0.18;
      const r = ring.offsetWidth / 2;
      ring.style.transform = `translate3d(${rx - r}px,${ry - r}px,0)`;
      if (Math.abs(mx - rx) > 0.1 || Math.abs(my - ry) > 0.1) raf = requestAnimationFrame(loop);
      else running = false;
    }

    const onMove = (e) => {
      mx = e.clientX;
      my = e.clientY;
      dot.style.transform = `translate3d(${mx - 4.5}px,${my - 4.5}px,0)`;
      if (!running) { running = true; raf = requestAnimationFrame(loop); }
    };
    const onOver = (e) => {
      const hit = e.target instanceof Element && e.target.closest("a,button,input,[role='button']");
      document.body.dataset.cursor = hit ? "link" : "";
    };
    const onLeave = () => {
      dot.style.transform = ring.style.transform = "translate3d(-80px,-80px,0)";
    };

    addEventListener("mousemove", onMove, { passive: true });
    document.addEventListener("mouseover", onOver);
    document.addEventListener("mouseleave", onLeave);

    return () => {
      cancelAnimationFrame(raf);
      removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseover", onOver);
      document.removeEventListener("mouseleave", onLeave);
      delete document.body.dataset.cursor;
    };
  }, []);

  return (
    <>
      <div id="cursor-ring" aria-hidden="true" />
      <div id="cursor" aria-hidden="true" />
    </>
  );
}
