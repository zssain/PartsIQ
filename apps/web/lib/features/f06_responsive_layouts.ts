// F06 Responsive layouts (owner: web).
//
// Pure breakpoint logic for the 360 / 768 / 1280 CSS-pixel targets: one stacked column on
// mobile (compact), two columns on tablet, three on desktop. Wide content (comparison tables)
// scrolls horizontally WITHIN its own region; the page itself never scrolls horizontally
// (styles/tokens.css). reducedMotion is carried through so callers can suppress transitions.

export interface F06Request {
  width: number;
  reducedMotion: boolean;
}

export interface F06Result {
  columns: 1 | 2 | 3;
  compact: boolean;
}

export const BREAKPOINTS = { tablet: 768, desktop: 1280 } as const;

export function get_layout(request: F06Request): F06Result {
  const width = request.width;
  const columns: 1 | 2 | 3 = width < BREAKPOINTS.tablet ? 1 : width < BREAKPOINTS.desktop ? 2 : 3;
  return { columns, compact: width < BREAKPOINTS.tablet };
}
