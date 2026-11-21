import { readFileSync } from 'node:fs';
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
