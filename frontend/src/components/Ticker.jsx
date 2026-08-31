/**
 * The stack marquee under the hero, fed by the real tag vocabulary of the
 * published work. The track is duplicated because the loop translates by -50%.
 *
 * That loop only reads as endless while one copy overruns the viewport, so a
 * thin vocabulary — a fresh install with one project — gets repeated up to a
 * floor first. Without it four tags leave most of the band empty and park the
 * wrap seam in plain sight.
 */
const MIN_ITEMS = 24;

export default function Ticker({ items = [] }) {
  if (items.length === 0) return null;

  const reps = Math.ceil(MIN_ITEMS / items.length);
  const cycle = Array.from({ length: reps }, () => items).flat();

  return (
    <div className="ticker" aria-hidden="true">
      {/* One cycle is what -50% travels, so its length is what sets the pace. */}
      <div className="ticker-track" style={{ "--ticker-span": String(cycle.length) }}>
        {[...cycle, ...cycle].map((item, i) => (
          <span className="ticker-item" key={`${item}-${i}`}>{item}</span>
        ))}
      </div>
    </div>
  );
}
