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

  it('ships the ones that need no mycologist, in reading order', () => {
    // Order is pedagogical and not alphabetical: what I will say, then what
    // the numbers beside it mean, then three ways to give me more to go on.
    expect(slugs).toEqual([
      'why-i-refuse',
      'what-the-percentages-mean',
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
  const mapped = [...learn.matchAll(/'([a-z-]+)': require\('\.\.\/\.\.\/assets\/learn\//g)]
    .map((m) => m[1]);

  it('backs every mapped slug with a file that exists on disk', () => {
    // A missing asset stops an Expo build, which is late. Same reason
    // icons.test.ts checks the icon set rather than trusting the build.
    //
    // A post is allowed to have NO entry: the index was text-led before it
    // had photographs at all, and a post written after the frames were
    // allocated waits for one rather than borrowing another post's. What is
    // forbidden is a mapping with nothing behind it.
    for (const slug of mapped) {
      expect(
        existsSync(resolve(ROOT, `assets/learn/${slug}.jpg`)),
        `assets/learn/${slug}.jpg is missing — run scripts/build_learn_images.py`,
      ).toBe(true);
    }
    expect(existsSync(resolve(ROOT, 'assets/learn/home.jpg'))).toBe(true);
  });

  it('renders no photograph box for a post that has none', () => {
    // Without the guard an unmapped slug leaves a 256pt hole in the card,
    // which reads as an image that failed to load rather than as a post
    // without one. Pinned at the source, because vitest cannot drive the
    // RN renderer and this is exactly the class of fault that let three
    // client bugs sit behind a green suite for months.
    expect(learn).toContain('{IMAGES[post.slug] ? (');
  });

  it('leaves at most one post waiting for a frame', () => {
    // Not a rule, a prompt: two text-led cards among photographs stops
    // looking like one post that arrived early and starts looking like
    // the index losing its photographs.
    const unmapped = POSTS.filter((p) => !mapped.includes(p.slug));
    expect(unmapped.map((p) => p.slug).join(', ')).not.toMatch(/,/);
  });

  it('maps no slug that is not a post', () => {
    for (const slug of mapped) {
      expect(POSTS.map((p) => p.slug), `${slug} is mapped but is not a post`).toContain(slug);
    }
  });

  it('ships no EXIF on any of them', () => {
    // These are photographs off a phone and a camera, and a photograph is
    // the one asset in this app that can publish where somebody was
    // standing. The build writes every card through a fresh image, so
    // there is no APP1 segment at all — not merely no GPS.
    for (const slug of [...mapped, 'home']) {
      const bytes = readFileSync(resolve(ROOT, `assets/learn/${slug}.jpg`));
      expect(
        bytes.indexOf(Buffer.from('Exif\0\0', 'latin1')),
        `${slug}.jpg carries an EXIF block`,
      ).toBe(-1);
    }
  });

  it('keeps each card small enough to bundle', () => {
    for (const slug of [...mapped, 'home']) {
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

  it('puts the emergency route last, below the Learn card', () => {
    // This asserted the OPPOSITE for one day, with a comment saying
    // content must never push the one control that must never need a
    // scroll. Martin reversed it on 2026-11-21: "I want this at the
    // bottom to scroll to. As not on the main screen when first upload."
    //
    // Same judgement as taking it off the capture screen on 2026-10-29,
    // one step further; docs/SAFETY.md carries both sides. Kept as a
    // test rather than deleted so the order stays a decision: putting it
    // back above Learn means coming here and reading why it moved.
    expect(home.indexOf("navigate('Learn')")).toBeLessThan(
      home.indexOf("navigate('Emergency')"),
    );
  });

  it('still leaves the emergency route on the home screen at all', () => {
    // The thing that would actually be a loss. Moving it down the page
    // is Martin's call; losing it is how an app silently drops its
    // panic button, which this project has a note about.
    expect(home).toContain("navigate('Emergency')");
    expect(home).toContain('Someone has eaten a wild mushroom');
  });
});
