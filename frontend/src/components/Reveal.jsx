import { useReveal } from "../hooks.js";

/** Wraps children in a scroll-reveal container without an extra layout box. */
export default function Reveal({ as: Tag = "div", delay = 0, className = "", ...rest }) {
  const ref = useReveal();
  return <Tag ref={ref} className={`rv ${className}`} data-d={delay || undefined} {...rest} />;
}
