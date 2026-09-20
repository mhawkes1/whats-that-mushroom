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
  spacing: (n: number) => n * 8,
  radius: { sm: 8, md: 14, lg: 22 },
  font: { title: 26, heading: 20, body: 16, small: 14, tiny: 12 },
} as const;
