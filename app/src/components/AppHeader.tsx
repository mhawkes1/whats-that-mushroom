import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { theme } from '../lib/theme';

/**
 * The name, in one place.
 *
 * Was "What's That Mushroom?", the book's title, until 2026-10-27. Martin's
 * call: the book keeps that name and the app takes its own.
 *
 * *Funga* is the fungal counterpart to flora and fauna -- the fungal
 * community of a place. It was proposed in the mycological literature around
 * 2018 and there has been an active campaign since, the IUCN among its
 * backers, to make "fauna, flora and funga" standard in conservation
 * writing. Two things recommended it over the alternatives. It fits under an
 * icon: five characters against twenty, where a home screen truncates at
 * about twelve. And it promises nothing -- every other candidate on the list
 * (FungID, MycoID, Fungi Finder) said "we will tell you what this is", which
 * is the one thing this app refuses to do, so the name would have needed
 * walking back on the first screen it appeared on.
 *
 * What it does not do is tell a beginner what the app is for, which is what
 * the tagline and the store subtitle are now carrying. Change this string
 * and the tagline below and the app is renamed; nothing else in the client
 * reads either of them, though `app.json` carries the home screen label
 * separately and has to be changed with it.
 */
export const APP_NAME = 'Funga';
const TAGLINE = "I'll tell you when I can't tell.";

/**
 * The front page's header.
 *
 * This replaced a full reproduction of Martin Hawkes's book cover --
 * photograph, Fraunces setting, gold rule, byline -- at his request on
 * 2026-09-29. The photograph is gone; two things it carried had to survive
 * it, and one of them is the reason this component exists rather than the
 * header being inlined:
 *
 * **The emergency route.** The cover pinned it to its top corner because it
 * is the one control that must never need a scroll: somebody whose child
 * has eaten something is not going to hunt for it. It is still pinned, still
 * above the fold, still the same target size and label, and it still sits
 * above the consent gate. Removing the cover must not quietly cost the app
 * the only screen that has to work when everything else has failed.
 *
 * **It reads as a word, not a cross, and that was a real defect.** It was
 * drawn as a heavy greek cross glyph, which is a plus sign, in the top
 * right corner, which is where every app in the world puts "add a new
 * one". Martin read it as exactly that on 2026-10-29 -- not in a usability
 * study, in ordinary use -- and the failure compounds: a user taps it
 * expecting to add a mushroom, gets the emergency screen, learns the
 * button is wrong, and has been trained to avoid the one control that has
 * to work when it matters. The accessibility label was always correct, so
 * this was invisible to `accessibility.test.ts` and to every screen
 * reader; it was only ever wrong for people looking at it.
 *
 * The deeper cause was that the app had **no** way to start a new
 * observation, so the nearest plus-shaped thing became the affordance for
 * it. That is fixed on the capture screen; this only has to stop
 * impersonating it.
 *
 * **A little of the book's identity.** The gold rule and the serif title
 * remain. They used to be reinforcement for a shared name; since the rename
 * they are the *only* thread back to the printed guide, which makes them
 * more load-bearing than they were, not less. The typeface is still loaded
 * and still never awaited: if Fraunces has not arrived, the title renders in
 * the platform serif rather than not at all.
 */
export function AppHeader({ onEmergency }: { onEmergency: () => void }) {
  return (
    <View style={styles.header}>
      <View style={styles.titleBlock}>
        <Text style={styles.title} allowFontScaling={false}>
          {APP_NAME}
        </Text>
        <View style={styles.rule} />
        <Text style={styles.tagline}>{TAGLINE}</Text>
      </View>

      <Pressable
        onPress={onEmergency}
        style={styles.sos}
        hitSlop={12}
        accessibilityRole="button"
        accessibilityLabel="Someone has eaten a wild mushroom. What to do."
      >
        <Text style={styles.sosLabel} allowFontScaling={false}>
          EATEN{'\n'}ONE?
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  // The woodland ground. Green is allowed here and nowhere that states an
  // outcome: this band names the app, not a mushroom, so it cannot be read
  // as permission. See the note at the top of `theme.ts`.
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: theme.spacing(2),
    backgroundColor: theme.colour.canopySurface,
    borderBottomWidth: 1,
    borderBottomColor: theme.colour.lichen,
    borderRadius: theme.radius.md,
    paddingHorizontal: theme.spacing(2),
    paddingTop: theme.spacing(2),
    paddingBottom: theme.spacing(2),
    marginBottom: theme.spacing(1),
  },
  titleBlock: { flex: 1 },
  title: {
    fontFamily: theme.cover.display,
    fontSize: 30,
    lineHeight: 36,
    color: theme.colour.text,
  },
  // The book's gold, kept deliberately: it is the one visual thread back to
  // the printed guide now the photograph has gone.
  rule: {
    height: 2,
    width: 56,
    backgroundColor: theme.cover.gold,
    marginTop: theme.spacing(1),
    marginBottom: theme.spacing(1),
  },
  tagline: {
    fontSize: theme.font.small,
    color: theme.colour.textMuted,
  },
  // Still 44x44 minimum -- the platform touch target -- but a rounded
  // rectangle rather than a circle, because a red circle with a symbol in
  // it is the shape of a badge and a rounded rectangle with a word in it
  // is the shape of a button.
  sos: {
    minWidth: 64,
    minHeight: 44,
    borderRadius: theme.radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: theme.spacing(1),
    backgroundColor: theme.colour.danger,
  },
  // Two short words beat any glyph here. A symbol has to be learned, and
  // the one moment this control is used is the moment nobody is learning
  // anything.
  sosLabel: {
    color: theme.colour.onAccent,
    fontSize: 11,
    lineHeight: 13,
    fontWeight: '700',
    textAlign: 'center',
    letterSpacing: 0.3,
  },
});
