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
 * **The emergency route is NOT here any more.** It was, from the cover
 * onwards, because it is the one control that must never need a scroll.
 * Martin dropped it from the header on 2026-10-29, having seen that the
 * capture screen already carries a full-width emergency button and
 * wanting this corner for starting another mushroom.
 *
 * The no-scroll guarantee did not go with it. That button is now PINNED
 * outside the capture screen's ScrollView, so it is on screen whatever
 * the user has scrolled to -- which it was not before, on any real phone.
 * Dropping the header control therefore made the route more reliable
 * rather than less, but only because the pinning came with it. If a
 * future change unpins it, the guarantee is gone and nothing in this
 * component will say so; `emergencyRoute.test.ts` is what holds the line.
 *
 * The brief history, because it keeps mattering: the cover pinned it to
 * its top corner; removing the cover nearly cost the app its panic
 * button; drawing it as a plus sign in the add-a-new-one corner made
 * users reach for it to add a mushroom, which is what this corner now
 * actually does.
 *
 * **A little of the book's identity.** The gold rule and the serif title
 * remain. They used to be reinforcement for a shared name; since the rename
 * they are the *only* thread back to the printed guide, which makes them
 * more load-bearing than they were, not less. The typeface is still loaded
 * and still never awaited: if Fraunces has not arrived, the title renders in
 * the platform serif rather than not at all.
 */
export function AppHeader({
  onNewObservation,
  canStartAnother,
}: {
  /** Clear the current photographs and begin a different mushroom. */
  onNewObservation?: () => void;
  /** Whether there is anything to clear. Hidden rather than disabled: a
   *  dead control in the corner people already read as "add" is worse
   *  than no control. */
  canStartAnother?: boolean;
}) {
  return (
    <View style={styles.header}>
      <View style={styles.titleBlock}>
        <Text style={styles.title} allowFontScaling={false}>
          {APP_NAME}
        </Text>
        <View style={styles.rule} />
        <Text style={styles.tagline}>{TAGLINE}</Text>
      </View>

      {onNewObservation && canStartAnother ? (
        <Pressable
          onPress={onNewObservation}
          style={styles.newObservation}
          hitSlop={12}
          accessibilityRole="button"
          accessibilityLabel="Clear these photographs and start a different mushroom"
        >
          <Text style={styles.newObservationLabel} allowFontScaling={false}>
            NEW{'\n'}MUSHROOM
          </Text>
        </Pressable>
      ) : null}
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
  // The corner people were already reading as "add another one", now
  // doing that. Words rather than a plus for the same reason the
  // emergency control took words: this sits next to nothing that explains
  // it, and two short words cannot be misread.
  //
  // Deliberately NOT red. Red is the emergency route's colour everywhere
  // in this app, and a red button in the corner that used to hold the
  // emergency route would be the old confusion with the arguments
  // reversed.
  newObservation: {
    minWidth: 64,
    minHeight: 44,
    borderRadius: theme.radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: theme.spacing(1),
    backgroundColor: theme.colour.accent,
  },
  newObservationLabel: {
    color: theme.colour.onAccent,
    fontSize: 11,
    lineHeight: 13,
    fontWeight: '700',
    textAlign: 'center',
    letterSpacing: 0.3,
  },
});
