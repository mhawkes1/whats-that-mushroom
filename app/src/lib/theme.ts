/**
 * Visual language.
 *
 * Verdict colours are load-bearing rather than decorative: `danger` marks a
 * potentially lethal ambiguity and is used for nothing else. There is no
 * green-for-go anywhere in the palette, because the app never gives the user
 * a go.
 */
export const theme = {
  colour: {
    background: '#14100d',
    surface: '#201a15',
    surfaceRaised: '#2b231c',
    border: '#3a3026',

    text: '#f2ece4',
    textMuted: '#b3a696',
    textFaint: '#7d7267',

    // Reserved for "a species that can kill is in play".
    danger: '#e5484d',
    dangerSurface: '#3d1518',
    caution: '#e5a23d',
    cautionSurface: '#3a2a12',
    // Means "reasonably confident in the identification". Never "safe".
    confident: '#7cc6b0',

    accent: '#c98b4b',
  },
  /**
   * What survives of the book's cover.
   *
   * The cover was the front page until 2026-09-29, when the photograph and
   * the byline were dropped at Martin's request. `gold` and `display` are
   * still used, by `AppHeader`: the rule under the title and the serif the
   * title is set in are the only visual thread left back to the printed
   * guide, and they are kept beside the app palette so the two cannot drift.
   *
   * `display` names a font loaded asynchronously at launch. If it has not
   * arrived, or fails, React Native falls back to the platform serif rather
   * than to nothing -- a title in Georgia is worse than one in Fraunces, and
   * a front page that will not render is worse than either.
   *
   * `ground`, `subtitle`, `byline` and `displayItalic` are unused now the
   * photograph has gone. Left in place because the ebook generator shares
   * these values and a future cover screen would want them back.
   */
  cover: {
    ground: '#0a0e08',
    gold: '#c9a227',
    subtitle: '#e8c15a',
    byline: '#c6ceb4',
    display: 'Fraunces_600SemiBold',
    displayItalic: 'Fraunces_300Light_Italic',
    displayFallback: 'serif',
  },

  spacing: (n: number) => n * 8,
  radius: { sm: 8, md: 14, lg: 22 },
  font: { title: 26, heading: 20, body: 16, small: 14, tiny: 12 },
} as const;
