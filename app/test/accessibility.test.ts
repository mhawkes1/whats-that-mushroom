import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

/**
 * Every `Pressable` must declare an `accessibilityRole`.
 *
 * Without one, React Native hands a screen reader a view containing text:
 * the control is readable but not announced as something that can be
 * activated, and it is skipped by element-type navigation. Eleven of the
 * thirty-six were missing it on 2026-10-19, including the primary action on
 * the field-notes screen and every control on the spore print screen —
 * the one flow in the app that takes a user twelve hours.
 *
 * A source-level test, like `emergencyRoute.test.ts`, because vitest cannot
 * drive the RN renderer. It is a weaker check than rendering would be and it
 * is the one available; the alternative is no check, and the first audit
 * found the gap only because someone went looking.
 *
 * This counts tags, not behaviour, so it cannot tell a *correct* role from a
 * present one. What it does guarantee is that adding a control makes you
 * decide.
 */

const SRC = join(__dirname, '..', 'src');

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) return sources(path);
    return path.endsWith('.tsx') ? [path] : [];
  });
}

/**
 * The opening tags of every `<Pressable …>` in a file.
 *
 * Scanning to the first `>` is wrong and was wrong when this was first
 * audited: `onPress={() => navigate()}` contains one, so a naive regex
 * reports controls that do declare a role and inflates the count — it
 * claimed 31 missing when the real number was 11. Brace depth is tracked so
 * the `>` inside an arrow function is not mistaken for the end of the tag.
 */
function pressableTags(source: string): { line: number; attrs: string }[] {
  const tags: { line: number; attrs: string }[] = [];
  const opener = /<Pressable\b/g;
  let match: RegExpExecArray | null;

  while ((match = opener.exec(source)) !== null) {
    let depth = 0;
    for (let i = match.index + match[0].length; i < source.length; i += 1) {
      const c = source[i];
      if (c === '{') depth += 1;
      else if (c === '}') depth -= 1;
      else if (c === '>' && depth === 0) {
        tags.push({
          line: source.slice(0, match.index).split('\n').length,
          attrs: source.slice(match.index + match[0].length, i),
        });
        break;
      }
    }
  }
  return tags;
}

describe('every Pressable is announced as a control', () => {
  const files = sources(SRC);

  it('finds the components to check', () => {
    expect(files.length).toBeGreaterThan(5);
    const all = files.flatMap((f) => pressableTags(readFileSync(f, 'utf8')));
    expect(all.length).toBeGreaterThan(20);
  });

  it.each(sources(SRC).map((f) => [f.slice(f.indexOf('src')), f]))(
    '%s',
    (_label, path) => {
      const source = readFileSync(path, 'utf8');
      const missing = pressableTags(source)
        .filter((tag) => !tag.attrs.includes('accessibilityRole'))
        .map((tag) => tag.line);

      expect(missing, `Pressable without accessibilityRole at line(s) ${missing}`)
        .toEqual([]);
    },
  );

  it('the tag parser is not fooled by a > inside an arrow function', () => {
    const tricky = `
      <Pressable onPress={() => navigation.navigate('Report')} accessibilityRole="button">
        <Text>Go</Text>
      </Pressable>`;
    const [tag] = pressableTags(tricky);
    expect(tag.attrs).toContain('accessibilityRole');

    const naive = tricky.slice(0, tricky.indexOf('>') + 1);
    expect(naive).not.toContain('accessibilityRole');
  });
});
