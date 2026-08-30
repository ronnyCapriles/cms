import { useEffect, useRef } from "react";

/**
 * The hero's ambient lineage field: nodes in stages, edges pointing downstream,
 * packets travelling along them.
 *
 * Colours are read from the `--flow-*` tokens as raw rgb triplets, so the canvas
 * repaints when the visitor switches mode. Directions B and C hide it in CSS.
 */
export default function FlowField() {
  const ref = useRef(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const ctx = canvas.getContext("2d");
    let width = 0, height = 0, nodes = [], edges = [], packets = [], raf = null;
    let palette = { edge: "90,200,232", node: "150,175,190", packet: "242,160,61", gain: 1 };

    function readPalette() {
      const s = getComputedStyle(document.documentElement);
      const rgb = (name) => s.getPropertyValue(name).trim().replace(/\s+/g, ",");
      palette = {
        edge: rgb("--flow-edge") || palette.edge,
        node: rgb("--flow-node") || palette.node,
        packet: rgb("--flow-packet") || palette.packet,
        gain: parseFloat(s.getPropertyValue("--flow-gain")) || 1,
      };
    }

    function build() {
      const dpr = Math.min(devicePixelRatio || 1, 2);
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const cols = width < 720 ? 4 : 6;
      const rows = width < 720 ? 4 : 5;
      nodes = [];
      for (let x = 0; x < cols; x++) {
        for (let y = 0; y < rows; y++) {
          if (Math.random() < 0.28) continue;
          nodes.push({
            x: (x + 0.5 + (Math.random() - 0.5) * 0.5) * (width / cols),
            y: (y + 0.5 + (Math.random() - 0.5) * 0.6) * (height / rows),
            col: x,
            r: 1.1 + Math.random() * 1.6,
            phase: Math.random() * Math.PI * 2,
          });
        }
      }

      edges = [];
      for (const a of nodes) {
        const downstream = nodes
          .filter((b) => b.col === a.col + 1)
          .sort((p, q) => Math.hypot(p.x - a.x, p.y - a.y) - Math.hypot(q.x - a.x, q.y - a.y));
        downstream.slice(0, 1 + (Math.random() < 0.35 ? 1 : 0)).forEach((b) => edges.push({ a, b }));
      }

      packets = edges
        .filter(() => Math.random() < 0.42)
        .map((e) => ({ e, t: Math.random(), speed: 0.0012 + Math.random() * 0.0022 }));
    }

    function draw(now) {
      ctx.clearRect(0, 0, width, height);
      const g = palette.gain;

      ctx.lineWidth = 1;
      for (const { a, b } of edges) {
        const grad = ctx.createLinearGradient(a.x, a.y, b.x, b.y);
        grad.addColorStop(0, `rgba(${palette.edge},${0.1 * g})`);
        grad.addColorStop(1, `rgba(${palette.edge},${0.02 * g})`);
        ctx.strokeStyle = grad;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.bezierCurveTo((a.x + b.x) / 2, a.y, (a.x + b.x) / 2, b.y, b.x, b.y);
        ctx.stroke();
      }

      for (const n of nodes) {
        const pulse = 0.5 + 0.5 * Math.sin(now / 1400 + n.phase);
        ctx.fillStyle = `rgba(${palette.node},${(0.1 + pulse * 0.16) * g})`;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fill();
      }

      for (const p of packets) {
        p.t += p.speed;
        if (p.t > 1) p.t = 0;
        const { a, b } = p.e;
        const t = p.t, mt = 1 - t, mid = (a.x + b.x) / 2;
        const x = mt ** 3 * a.x + 3 * mt ** 2 * t * mid + 3 * mt * t ** 2 * mid + t ** 3 * b.x;
        const y = mt ** 3 * a.y + 3 * mt ** 2 * t * a.y + 3 * mt * t ** 2 * b.y + t ** 3 * b.y;
        const fade = Math.sin(t * Math.PI);
        ctx.fillStyle = `rgba(${palette.packet},${0.55 * fade * g})`;
        ctx.beginPath(); ctx.arc(x, y, 1.8, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = `rgba(${palette.packet},${0.12 * fade * g})`;
        ctx.beginPath(); ctx.arc(x, y, 6, 0, Math.PI * 2); ctx.fill();
      }

      raf = requestAnimationFrame(draw);
    }

    readPalette();
    addEventListener("df:mode", readPalette);

    const ro = new ResizeObserver(build);
    ro.observe(canvas);
    build();
    raf = requestAnimationFrame(draw);

    /* Stop painting once off screen — the hero is a full viewport tall. */
    const vis = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { if (!raf) raf = requestAnimationFrame(draw); }
      else { cancelAnimationFrame(raf); raf = null; }
    }, { threshold: 0 });
    vis.observe(canvas);

    return () => {
      cancelAnimationFrame(raf);
      removeEventListener("df:mode", readPalette);
      ro.disconnect();
      vis.disconnect();
    };
  }, []);

  return <canvas className="field" ref={ref} aria-hidden="true" />;
}
