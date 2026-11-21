import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { POSTS, postBySlug, type Post } from '../src/content/posts';

/**
 * Rule 1 over the Learn posts and the screens that render them.
 *
 * `test_no_user_facing_path_makes_an_inedibility_claim` on the Python side
 * scans what `assess` returns. It has twice been found covering one surface
 * and missing another: it never read `disclaimer.py`, where "the risk has
 * not been assessed" survived the September purge in the most-read text in
 * the app, and it never read `scripts/try_it.py`. Long-form prose about
 * mushrooms is the surface most likely to slide into "delicious when young"
 * by reflex, so it is covered from its first day and before anyone has
 * written a second batch.
 *
 * It scans whole files, COMMENTS INCLUDED, and that is deliberate even
 * though a comment is not user-facing. It caught the note in LearnScreen
 * explaining which photographs were ruled out, which had to use the word
 * to say it -- the same shape as the masthead test matching its own
 * explanatory prose. Rewording the comment is cheap; a scanner that
 * skips comments has to parse TSX to find out what is one, and would
 * then be a scanner that can be fooled by where a string sits.
 */

const ROOT = resolve(__dirname, '..');

const SCANNED = [
  'src/content/posts.ts',
  'src/screens/LearnScreen.tsx',
  'src/screens/PostScreen.tsx',
  // Not new, and never scanned by anything until now.
  'src/screens/HomeScreen.tsx',
];

/** Both directions. An "inedible" is as much a ruling on a meal as an
 *  "edible", and it is the half this project purged late. */
const CLAIMS: RegExp[] = [
  /\bedible\b/,
  /\binedible\b/,
  /\bsafe to eat\b/,
  /\bgood to eat\b/,
  /\bworth eating\b/,
  /\bworth collecting\b/,
  /\bdelicious\b/,
  /\btasty\b/,
  /\bunpalatable\b/,
  /\bchoice\b/,
  /\bnot assessed as safe\b/,
  /\bno_recorded_toxicity\b/,
];

/**
 * The only sentences allowed to contain a banned phrase, because in each
 * one the app is refusing to make the claim rather than making it. Named
 * in a list rather than weakened out of the patterns, and the test below
 * fails if one of them stops appearing -- an allowlist that has outlived
 * its entries is a hole, not a pass.
 */
const REFUSALS = [
  'it will never tell you a mushroom is safe to eat',
  'none of them tells you whether anything is safe to eat',
];

const flatten = (file: string) =>
  readFileSync(resolve(ROOT, file), 'utf8').replace(/\s+/g, ' ').toLowerCase();

describe('rule 1 over everything a Learn reader sees', () => {
  it.each(SCANNED)('%s makes no edibility claim in either direction', (file) => {
    let text = flatten(file);
    for (const refusal of REFUSALS) text = text.split(refusal).join(' ');

    for (const claim of CLAIMS) {
      const hit = claim.exec(text);
      expect(
        hit,
        `${file}: ${claim} matched ${JSON.stringify(
          text.slice(Math.max(0, (hit?.index ?? 0) - 90), (hit?.index ?? 0) + 90),
        )}`,
      ).toBeNull();
    }
  });

  it('every allowed refusal is still somewhere in the app', () => {
    // Without this the allowlist silently becomes a list of phrases that
    // are merely permitted, and the next one added is never questioned.
    const all = SCANNED.map(flatten).join(' ');
    for (const refusal of REFUSALS) expect(all).toContain(refusal);
  });

  it('the refusals are only ever the app declining, never a verdict', () => {
    // Each one has to read as "this app will not say", not as "this
    // mushroom is". Pinned by requiring the subject to be the app.
    for (const refusal of REFUSALS) {
      expect(refusal).toMatch(/\b(it will never|none of them tells you)\b/);
    }
  });
});

describe('the posts themselves', () => {
  const slugs = POSTS.map((p) => p.slug);

  it('ships the four that need no mycologist', () => {
    expect(slugs).toEqual([
      'why-i-refuse',
      'photographing-a-mushroom',
      'spore-prints',
      'answers-that-mislead-me',
    ]);
  });

  it('gives every post a unique slug that resolves', () => {
    expect(new Set(slugs).size).toBe(slugs.length);
    for (const slug of slugs) expect(postBySlug(slug)?.slug).toBe(slug);
  });

  it('returns nothing rather than throwing on a slug it does not have', () => {
    expect(postBySlug('no-such-post')).toBeUndefined();
  });

  it('gives every post a title, a standfirst and something to read', () => {
    for (const post of POSTS as Post[]) {
      expect(post.title.length).toBeGreaterThan(0);
      expect(post.standfirst.length).toBeGreaterThan(0);
      expect(post.blocks.length).toBeGreaterThan(2);
      for (const block of post.blocks) expect(block.text.trim().length).toBeGreaterThan(0);
    }
  });

  it('never leaves a heading as the last thing on the page', () => {
    // A heading with nothing under it reads as content that failed to load.
    for (const post of POSTS as Post[]) {
      expect(post.blocks[post.blocks.length - 1].kind).not.toBe('heading');
    }
  });
});


describe('the card photographs', () => {
  const learn = readFileSync(resolve(ROOT, 'src/screens/LearnScreen.tsx'), 'utf8');

  it('gives every post an image that exists on disk', () => {
    // A missing asset stops an Expo build, which is late. Same reason
    // icons.test.ts checks the icon set rather than trusting the build.
    for (const post of POSTS) {
      expect(learn, `no image mapped for ${post.slug}`).toContain(`'${post.slug}': require(`);
      expect(
        existsSync(resolve(ROOT, `assets/learn/${post.slug}.jpg`)),
        `assets/learn/${post.slug}.jpg is missing — run scripts/build_learn_images.py`,
      ).toBe(true);
    }
    expect(existsSync(resolve(ROOT, 'assets/learn/home.jpg'))).toBe(true);
  });

  it('maps no slug that is not a post', () => {
    const mapped = [...learn.matchAll(/'([a-z-]+)': require\('\.\.\/\.\.\/assets\/learn\//g)]
      .map((m) => m[1]);
    expect(mapped.sort()).toEqual(POSTS.map((p) => p.slug).sort());
  });

  it('ships no EXIF on any of them', () => {
    // These are photographs off a phone and a camera, and a photograph is
    // the one asset in this app that can publish where somebody was
    // standing. The build writes every card through a fresh image, so
    // there is no APP1 segment at all — not merely no GPS.
    for (const slug of [...POSTS.map((p) => p.slug), 'home']) {
      const bytes = readFileSync(resolve(ROOT, `assets/learn/${slug}.jpg`));
      expect(
        bytes.indexOf(Buffer.from('Exif\0\0', 'latin1')),
        `${slug}.jpg carries an EXIF block`,
      ).toBe(-1);
    }
  });

  it('keeps each card small enough to bundle', () => {
    for (const slug of [...POSTS.map((p) => p.slug), 'home']) {
      const kb = readFileSync(resolve(ROOT, `assets/learn/${slug}.jpg`)).length / 1024;
      expect(kb, `${slug}.jpg is ${Math.round(kb)} KB`).toBeLessThan(200);
    }
  });
});

describe('the home screen keeps its statement', () => {
  const home = readFileSync(resolve(ROOT, 'src/screens/HomeScreen.tsx'), 'utf8')
    .replace(/\s+/g, ' ');

  it('still makes all three claims after the panel was compressed', () => {
    // The explanations moved to `why-i-refuse` on 2026-11-21. The claims
    // did not, and the first of them is the product. A later tidy that
    // takes the panel down to a link must fail here.
    for (const claim of [
      'It will never tell you a mushroom is safe to eat.',
      'It will refuse rather than guess.',
      'It cannot see what you did not photograph.',
    ]) {
      expect(home).toContain(claim);
    }
  });

  it('puts the Learn card below the emergency route, never above it', () => {
    // Content must not push the one control that must never need a
    // scroll any further down the page.
    expect(home.indexOf("navigate('Emergency')")).toBeLessThan(
      home.indexOf("navigate('Learn')"),
    );
  });
});
