import { Fragment } from "react";

/**
 * A CMS headline with exactly two bits of markup: a line break is a line break,
 * and *asterisks* outline a word. Split into segments rather than parsed as
 * markdown or injected as HTML, so a text field can never inject a script tag.
 */
export default function Headline({ text = "" }) {
  return text.split("\n").map((line, l) => (
    <Fragment key={l}>
      {l > 0 && <br />}
      {/* A capturing split alternates plain / marked, so odd indices are ems. */}
      {line.split(/\*([^*]+)\*/).map((part, i) =>
        i % 2 ? <em key={i}>{part}</em> : <Fragment key={i}>{part}</Fragment>
      )}
    </Fragment>
  ));
}
