import { readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

/**
 * The masthead, guarded at the source level.
 *
 * A photograph returned to the front page on 2026-10-31, eighteen months of
 * project-time after the book cover was taken off it. Three of the four
 * things that make it safe to have there are invisible to any renderer
 * vitest can drive, and the fourth fails only at build time on a real
 * device, so these read the source and the asset instead.
 *
 * The one that is not here is the emergency route, because removing the
 * cover is what nearly cost the app its panic button last time.
 * `emergencyRoute.test.ts` has held that line since and still does.
 */
const APP = resolve(__dirname, '..');
const read = (p: string) => readFileSync(resolve(APP, p), 'utf8');
const header = () => read('src/components/AppHeader.tsx');

describe('the masthead', () => {
  it('ships both assets, because a missing one stops an Expo build', () => {
    // Same reason icons.test.ts exists. `require` of a missing asset is a
    // bundler error, which surfaces long after anybody has stopped looking
    // at this component.
    for (const asset of ['assets/masthead.jpg', 'assets/mark-cream.png']) {
      const size = statSync(resolve(APP, asset)).size;
      expect(size, `${asset} is missing or empty`).toBeGreaterThan(1024);
    }
  });

  it('the asset is the shape of the container it goes into', () => {
    // These disagreed for several days and nothing said so. The band was
    // generated at 306/132 while `header` was 306x150, so `resizeMode
    // ="cover"` scaled to fill and threw roughly 12% off the sides: the
    // shipped masthead was more zoomed in than any version that had been
    // measured, and the crop that reached a phone was not the crop anybody
    // had looked at.
    //
    // Fixing that tied the two to EACH OTHER and left both wrong, because
    // 306 is the content width and the band is full-bleed. This test
    // therefore passed while `cover` ate 22% of the band's height. A test
    // that compares two numbers it also supplies is not a measurement --
    // the width here has to be the one the client reports.
    //
    // Reading the JPEG's own SOF0 marker rather than trusting a constant,
    // because the generator writing one number and the component using
    // another is the exact failure.
    const jpeg = readFileSync(resolve(APP, 'assets/masthead.jpg'));
    let i = 2;
    let dims: [number, number] | null = null;
    while (i < jpeg.length - 9) {
      if (jpeg[i] !== 0xff) { i += 1; continue; }
      const marker = jpeg[i + 1];
      // SOF0/1/2 carry the frame size; everything else is skipped by length.
      if (marker >= 0xc0 && marker <= 0xc2) {
        dims = [jpeg.readUInt16BE(i + 7), jpeg.readUInt16BE(i + 5)];
        break;
      }
      i += 2 + jpeg.readUInt16BE(i + 2);
    }
    expect(dims, 'could not read masthead.jpg dimensions').not.toBeNull();

    const header = /height:\s*(\d+)/.exec(
      read('src/components/AppHeader.tsx').split('header: {')[1],
    );
    expect(header, 'AppHeader has no explicit header height').not.toBeNull();
    // 390, not the content width. The band is full-bleed -- it pulls back
    // out through HomeScreen's gutters with a negative margin -- so it
    // spans the screen. This read 306 until 2026-11-08 and the generator
    // agreed with it, so the pair was self-consistent and wrong, and the
    // shipped band was losing 22% of its height to `cover` on every phone.
    // Measured in the running client, not reasoned about.
    const want = 390 / Number(header![1]);
    const got = dims![0] / dims![1];
    expect(
      Math.abs(got - want),
      `asset is ${got.toFixed(3)}:1 and the container is ${want.toFixed(3)}:1`,
    ).toBeLessThan(0.02);
  });

  it('lets the photograph fill the band', () => {
    // `{...absoluteFillObject, width: undefined, height: undefined}` is the
    // native idiom for stopping an <Image> sizing itself to its source. On
    // React Native Web it does the opposite: measured in the running client
    // on 2026-11-08, the element kept the asset's intrinsic **1200x406**
    // inside a 390x132 header, so `overflow: hidden` showed a corner of the
    // photograph at about 3x and `resizeMode="cover"` never applied.
    //
    // Nothing else can see this. The asset is the right shape, the test
    // above proves it, the component references it correctly, and the band
    // renders -- it just renders the wrong part of the picture. Three
    // rounds of re-cropping were spent on the symptom.
    // Read the declaration, not the file: the note above this style in
    // the component spells out the old idiom, and a scan of the whole
    // source matches that prose instead of the code.
    const decl = /^\s*photo: \{[^}]*\},$/m.exec(header());
    expect(decl, 'no photo style found in AppHeader').not.toBeNull();
    expect(decl![0]).not.toMatch(/undefined/);
    expect(decl![0]).toMatch(/width: '100%'/);
    expect(decl![0]).toMatch(/height: '100%'/);
  });

  it('puts its text on a scrim token, never a literal', () => {
    // What is underneath is a photograph. It is not themed and cannot be
    // reasoned about from the palette, which is why `theme.ts` names a
    // scrim for exactly this and why `theme.test.ts` bans colour literals
    // outside that file. A hardcoded rgba() here is how SporePrintScreen
    // ended up with near-black ink on a near-black scrim.
    expect(header()).toMatch(/theme\.colour\.mastheadScrim/);
    expect(header()).not.toMatch(/rgba\(/);
    expect(header()).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it('did not take the spore print screen down with it', () => {
    // `mastheadScrim` is 0.30 against `photoScrim`'s 0.62, and the whole
    // justification for the lighter one is that THIS photograph is a
    // committed file that has been measured. The spore print screen's is
    // the user's, could be a white card in sunlight, and carries the labels
    // saying which box holds the deposit -- on the flow that asks somebody
    // for twelve hours. Splitting a token is how a value quietly spreads,
    // so this pins which screen got which.
    expect(read('src/screens/SporePrintScreen.tsx')).toMatch(/theme\.colour\.photoScrim/);
    expect(read('src/screens/SporePrintScreen.tsx')).not.toMatch(/mastheadScrim/);
    expect(read('src/lib/theme.ts')).toMatch(/photoScrim: 'rgba\(0, 0, 0, 0\.62\)'/);
  });

  it('haloes the lettering, because the scrim alone no longer carries it', () => {
    // At 0.30 the worst case is 2.7:1 -- under AA and under the 3:1 large
    // text gets. That was Martin's call with the number in front of him,
    // and `textHalo` is what stops the tagline disappearing into a bright
    // tuft. A contrast ratio cannot score an edged letter, so nothing else
    // in the suite would notice this being dropped.
    const src = header();
    expect(src).toMatch(/textShadowColor:\s*theme\.colour\.textHalo/);
    expect(src).toMatch(/textShadowRadius/);
    // On both pieces of type. The title is 30px and still misses 3:1.
    expect(src.match(/\.\.\.halo/g) ?? []).toHaveLength(2);
  });

  it('uses onAccent for every word over the photograph', () => {
    // The rule `theme.ts` states in both directions: text on photoScrim is
    // onAccent and never `text`. On paper `text` is near-black ink, which
    // over a dark scrim is invisible -- and invisible is what the title,
    // the rule and the tagline would all be.
    const src = header();
    const colours = [...src.matchAll(/color:\s*theme\.colour\.(\w+)/g)].map((m) => m[1]);
    expect(colours.length).toBeGreaterThan(0);
    for (const c of colours) expect(c).toBe('onAccent');
    // And the rule under the title, which is a background rather than a
    // colour and so would slip past the check above.
    expect(src).toMatch(/backgroundColor:\s*theme\.colour\.onAccent/);
  });

  it('does not reintroduce the cover', () => {
    // Not a naming quibble. `CoverHeader` was a full reproduction of the
    // book jacket -- a cep filling the frame, lit as a portrait. That
    // composition is the thing this photograph was chosen to avoid, so a
    // file reappearing under that name is the regression, not the string.
    expect(header()).not.toContain('CoverHeader');
    expect(header()).not.toContain('cover.jpg');
  });

  it('keeps the tagline, which is what the name cannot say', () => {
    // "Funga" tells a beginner nothing about mushrooms. That was the
    // accepted cost of the name, and this sentence is what pays it.
    expect(header()).toMatch(/I'll tell you when I can't tell/);
  });

  it('hides the decorative images from screen readers', () => {
    // Two images, neither carrying information the title does not. A
    // reader announcing them before the app's own name is noise, and
    // noise at the top of the first screen is where people stop
    // listening.
    const src = header();
    expect(src.match(/accessibilityElementsHidden/g) ?? []).toHaveLength(2);
    expect(src.match(/importantForAccessibility="no"/g) ?? []).toHaveLength(2);
  });
});
