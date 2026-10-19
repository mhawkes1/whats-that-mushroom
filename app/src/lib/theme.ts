/**
 * Visual language.
 *
 * A field guide printed on good paper: warm bone grounds, ink text, and the
 * greens and barks of woodland for structure. Light rather than dark, at
 * Martin's request, 2026-10-19.
 *
 * Two rules constrain the palette, and they are the reason it is worth
 * reading this comment before changing a value.
 *
 * **Green is chrome, never a verdict.** `POSITIONING.md` excluded green from
 * the palette entirely, because green is the colour of permission and this
 * app never gives the user a go. That argument is about green *attached to
 * something* -- a verdict, a candidate row, a confidence marker, a button
 * that advances an identification. A green header rule or a moss-tinted
 * divider is woodland, not consent. So `canopy` and `lichen` exist, and they
 * appear only in structural chrome: rules, dividers, the header ground.
 * Nothing that names a species or states an outcome may use them.
 *
 * **Hazard colours are load-bearing rather than decorative.** `danger` marks
 * a potentially lethal ambiguity and is used for nothing else. On a light
 * ground they have to be *darker* than their dark-theme equivalents to stay
 * legible, not lighter -- a warning nobody can read is a warning that does
 * not work, which is why `test/theme.test.ts` pins their contrast ratios.
 */
export const theme = {
  colour: {
    // Paper. Warm rather than blue-white, so photographs of brown mushrooms
    // sit on it without looking jaundiced.
    background: '#f6f3ea',
    surface: '#fffdf7',
    surfaceRaised: '#efeade',
    border: '#d9d2c0',

    text: '#231e17',
    textMuted: '#5c5447',
    textFaint: '#8a8173',

    // Reserved for "a species that can kill is in play". Deep enough to
    // carry 7:1 against its own surface; the dark theme's #e5484d drops to
    // about 3:1 on paper and fails the one job it has.
    danger: '#941613',
    dangerSurface: '#fbe9e7',
    caution: '#7d5206',
    cautionSurface: '#fbf0d8',
    // Means "reasonably confident in the identification". Never "safe".
    // Was a teal-green, which on a white-and-green palette is precisely the
    // misread the whole product exists to avoid. Slate blue reads as
    // information rather than permission.
    confident: '#2f5a78',

    // The book's gold, which is also the app's accent.
    accent: '#9a6a24',

    // Text and glyphs sitting ON a filled control -- accent, danger, canopy.
    // Screens used to write `color: theme.colour.background` for this, which
    // was only ever correct because the background happened to be near-black.
    // Inverting the palette turned every primary button's label cream on
    // cream. Naming the role rather than borrowing a colour means the next
    // palette change cannot repeat it.
    onAccent: '#fffdf7',
    // And the label on a control that is present but not yet usable.
    onDisabled: '#8a8173',

    // Woodland chrome. Structural only -- see the note above.
    canopy: '#3f5d37',
    lichen: '#8fa07a',
    canopySurface: '#eaefe2',
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
   * `gold` is darkened from the printed cover's #c9a227 for the same reason
   * the hazard colours are: it sat on a near-black ground and now sits on
   * paper.
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
    ground: '#f2eee3',
    gold: '#9a7612',
    subtitle: '#6b5a16',
    byline: '#4a5340',
    display: 'Fraunces_600SemiBold',
    displayItalic: 'Fraunces_300Light_Italic',
    displayFallback: 'serif',
  },

  spacing: (n: number) => n * 8,
  radius: { sm: 8, md: 14, lg: 22 },
  font: { title: 26, heading: 20, body: 16, small: 14, tiny: 12 },
} as const;
