/**
 * The stack marquee under the hero, fed by the real tag vocabulary of the
 * published work. The track is duplicated because the loop translates by -50%.
 */
export default function Ticker({ items = [] }) {
  if (items.length === 0) return null;
  return (
    <div className="ticker" aria-hidden="true">
      <div className="ticker-track">
        {[...items, ...items].map((item, i) => (
          <span className="ticker-item" key={`${item}-${i}`}>{item}</span>
        ))}
      </div>
    </div>
  );
}
