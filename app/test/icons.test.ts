import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

/**
 * The icon set, guarded.
 *
 * Every failure these catch is a *late* failure otherwise: a missing asset
 * stops an Expo build, and an alpha channel on the iOS icon is rejected by
 * App Store Connect at upload, after a build has been made and paid for.
 * Both are cheap to assert here and expensive to discover there.
 *
 * Regenerate the set with `python scripts/build_icons.py`; it derives every
 * size from `docs/logo/round5/m4-outline.svg`, which is the mark Martin
 * chose on 2026-10-27.
 */

const APP = resolve(__dirname, '..');
const config = JSON.parse(readFileSync(join(APP, 'app.json'), 'utf8')).expo;

/** Every `./assets/...` string anywhere in the Expo config. */
function assetPaths(node: unknown, found: string[] = []): string[] {
  if (typeof node === 'string') {
    if (node.startsWith('./assets/')) found.push(node);
  } else if (Array.isArray(node)) {
    node.forEach((n) => assetPaths(n, found));
  } else if (node && typeof node === 'object') {
    Object.values(node).forEach((n) => assetPaths(n, found));
  }
  return found;
}

/**
 * A PNG's colour type, from the IHDR chunk.
 *
 * Byte 25 of the file: 2 is truecolour, 6 is truecolour with alpha. Reading
 * the header beats adding an image library for one byte.
 */
function pngColourType(file: string): number {
  const buf = readFileSync(file);
  expect(buf.subarray(1, 4).toString('ascii')).toBe('PNG');
  return buf[25];
}

/** Width and height, also from IHDR. */
function pngSize(file: string): [number, number] {
  const buf = readFileSync(file);
  return [buf.readUInt32BE(16), buf.readUInt32BE(20)];
}

describe('the icon set', () => {
  it('references assets that exist', () => {
    const paths = assetPaths(config);
    expect(paths.length).toBeGreaterThan(0);
    for (const p of paths) {
      expect(existsSync(join(APP, p)), `missing asset: ${p}`).toBe(true);
    }
  });

  it('names an icon, an adaptive icon, a splash image and a favicon', () => {
    expect(config.icon).toBe('./assets/icon.png');
    expect(config.android.adaptiveIcon.foregroundImage).toBe(
      './assets/adaptive-icon.png',
    );
    expect(config.splash.image).toBe('./assets/splash-icon.png');
    expect(config.web.favicon).toBe('./assets/favicon.png');
  });

  it('gives the iOS icon no alpha channel', () => {
    // App Store Connect rejects an icon with transparency, and it rejects it
    // at upload rather than at build. Colour type 6 is RGBA; 2 is RGB.
    expect(pngColourType(join(APP, 'assets/icon.png'))).toBe(2);
  });

  it('keeps alpha on the Android foreground, which needs it', () => {
    // The launcher composites this over `adaptiveIcon.backgroundColor`, so a
    // flattened foreground would paint its own square over the mask.
    expect(pngColourType(join(APP, 'assets/adaptive-icon.png'))).toBe(6);
  });

  it('ships the icons at the sizes the stores ask for', () => {
    expect(pngSize(join(APP, 'assets/icon.png'))).toEqual([1024, 1024]);
    expect(pngSize(join(APP, 'assets/adaptive-icon.png'))).toEqual([1024, 1024]);
  });

  it('leaves the stem open, so nothing is drawn across it', () => {
    // Martin spotted this in the rendered icons: a *closed* stem path draws
    // its own top edge as a straight line across the stem, hidden under the
    // cap. Reclosing it would silently put that line back, and it is only
    // visible once the mark is large.
    const svg = readFileSync(
      resolve(APP, '../docs/logo/funga-mark.svg'),
      'utf8',
    );
    const paths = [...svg.matchAll(/d="([^"]+)"/g)].map((m) => m[1]);
    expect(paths.length).toBeGreaterThanOrEqual(2);

    const cap = paths[0];
    const stem = paths[1];
    expect(cap.trim().endsWith('Z'), 'the cap must stay closed').toBe(true);
    expect(stem.includes('Z'), 'the stem must stay open').toBe(false);

    // And its ends are butt-capped, or round caps bulge below the cap as a
    // nub on each side.
    expect(svg).toMatch(/stroke-linecap="butt"/);
  });

  it('sets the adaptive background to the app paper, not white', () => {
    // The mark is drawn on moss as of 2026-10-31. A ground that disagrees
    // with the one `build_icons.py` composites onto shows as a ring of the
    // wrong colour the moment a launcher masks the icon to a circle -- which
    // is what every launcher on Martin's phone does. It was #f6f3ea, and the
    // same failure applied then; only the colour has changed.
    expect(config.android.adaptiveIcon.backgroundColor).toBe('#4e6e3f');
    expect(config.splash.backgroundColor).toBe('#4e6e3f');
  });
});
