/**
 * Visual language.
 *
 * White paper and woodland moss. Martin's call, 2026-10-31, after seeing the
 * app beside the three mushroom apps on his phone and finding it flat. It
 * replaced a warm bone palette, and `docs/design/moss-on-white.md` holds the
 * whole specification and the measurements behind it.
 *
 * Three rules constrain this file, and they are the reason it is worth
 * reading before changing a value.
 *
 * **Green is the brand now, and still never a verdict.** That is a real
 * change and it is narrower than it looks. `POSITIONING.md` excluded green
 * because green is the colour of permission and this app never gives the
 * user a go -- an argument about green *attached to something*: a verdict, a
 * hazard line, a confidence marker. Moss on a masthead, a tab glyph, a count
 * tile or the button that opens the camera states no outcome. So `accent` is
 * moss, and the line holds where it always did: **moss may mark confidence
 * in an identification, never the standing of a species.** It must not
 * appear on or beside a hazard line, in the verdict text on the result
 * screen, or anywhere a user could read it as the app's opinion of a meal.
 * The log's first row is the test case -- a moss edge where the app named a
 * species, with the TOXIC chip beside it doing the other job.
 *
 * **Structure comes from borders, not from fills.** On the old paper palette
 * every surface sat at 1.09:1 against its background: a card was not
 * visually an object, and the whole screen read as text on one flat field.
 * That is what "it looks basic" was. On white it is 1.00:1, which is less
 * than invisible, so `border` and the two filled elements -- the accent
 * control and the ink panel -- carry all of it. Do not reach for a tinted
 * card to fix a hierarchy problem; it will not fix it.
 *
 * **Hazard colours are load-bearing rather than decorative.** `danger` marks
 * a potentially lethal ambiguity and is used for nothing else. On a light
 * ground they have to be *darker* than their dark-theme equivalents to stay
 * legible, not lighter -- a warning nobody can read is a warning that does
 * not work, which is why `test/theme.test.ts` pins their contrast ratios and
 * the order of their emphasis.
 */
export const theme = {
  colour: {
    // White. It was a warm bone until 2026-10-31; Martin asked for white and
    // it is cleaner beside the moss. The one thing it costs is the reason
    // the cream was chosen -- photographs of brown mushrooms sat on it
    // without looking jaundiced, and on white they read slightly cooler.
    // Worth watching on the result screen, which is mostly photographs.
    background: '#ffffff',
    // The same white. A card is an object because of its border and its
    // spacing, not because of a fill; see the note above.
    surface: '#ffffff',
    // The one raised ground, used for a control that is present but not yet
    // usable. Faintly moss so it belongs to the family.
    surfaceRaised: '#f2f5ef',
    // Which makes this the hardest-working colour in the file.
    border: '#dde3d6',

    text: '#1b1f17',
    textMuted: '#4a5544',
    textFaint: '#646b5a',

    // Reserved for "a species that can kill is in play". Deep enough to
    // carry AAA against white, its own surface and a card; the dark theme's
    // #e5484d drops to about 3:1 here and fails the one job it has.
    danger: '#941613',
    dangerSurface: '#fdf0ee',
    caution: '#7a5106',
    cautionSurface: '#fdf4de',
    // Means "reasonably confident in the identification". Never "safe".
    // Deliberately not green even now that the brand is: this one is
    // attached to a species, which is exactly the line moss does not cross.
    confident: '#2f5a78',

    // The brand. Was the book's gold until 2026-10-31, when the identity
    // went moss and a gold appearing on exactly one control became an
    // orphan rather than a system.
    accent: '#4e6e3f',

    // Text and glyphs sitting ON a filled control -- accent, danger, canopy.
    // Screens used to write `color: theme.colour.background` for this, which
    // was only ever correct because the background happened to be near-black.
    // Inverting the palette turned every primary button's label cream on
    // cream. Naming the role rather than borrowing a colour means the next
    // palette change cannot repeat it.
    onAccent: '#fffdf7',
    // And the label on a control that is present but not yet usable.
    onDisabled: '#7b8273',

    // A dim laid over a *photograph*, so a label can be read against
    // whatever the user happened to photograph. It stays dark in any
    // palette -- the thing underneath is not themed -- which is why text on
    // it must be `onAccent` and never `text`. The masthead is measured
    // against this exact value.
    photoScrim: 'rgba(0, 0, 0, 0.62)',

    // Woodland chrome, now a shade family with `accent` rather than a
    // separate green. `canopy` is the deeper moss: eyebrows, active tabs,
    // rules. `canopySurface` is the tint under an advisory panel.
    canopy: '#3a5230',
    lichen: '#8fa77a',
    canopySurface: '#eef4e8',
    // The darkest thing on a screen, and the only element that is a block of
    // colour rather than a tint: the panel carrying what the app will not
    // do. That paragraph is the product's whole argument, and on the old
    // palette it was a cream card on a cream field -- the same weight as
    // everything around it. Here it is the thing you see first, which is
    // accurate.
    //
    // It is a near-black green, so the hue test in `theme.test.ts` does NOT
    // flag it: channel gaps shrink with luminance and this reads g-r=12,
    // one short of the threshold. That blind spot is known and written up in
    // CLAUDE.md. It is listed as green-by-design there anyway, because the
    // list is a statement of intent and not a record of what a regex caught.
    canopyInk: '#1f2b1a',
    // Body text on that panel. `onAccent` is right for the bold leads and
    // too loud for three paragraphs of it.
    onCanopyInk: '#c2cfb6',
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
