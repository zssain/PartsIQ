import type { JSX } from "react";

// FixtureBanner — an honest mode label shown in demo/fixture contexts. It states plainly that the
// data is synthetic and no live providers are involved, so a reader never mistakes a walkthrough
// result for a live one. Presentational only; it uses the existing disclosure token.
export function FixtureBanner(): JSX.Element {
  return (
    <p role="note" data-testid="fixture-banner" className="pq-disclosure">
      Fixture demo — synthetic data, no live providers.
    </p>
  );
}
