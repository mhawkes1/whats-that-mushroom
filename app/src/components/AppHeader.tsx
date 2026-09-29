import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { theme } from '../lib/theme';

/**
 * The name, in one place, because it is not settled yet.
 *
 * Working title. Change this string and the tagline below and the app is
 * renamed; nothing else reads either of them.
 */
export const APP_NAME = "What's That Mushroom?";
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
 * **A little of the book's identity.** The gold rule and the serif title
 * remain, because an app that shares a name with a printed guide should not
 * look unrelated to it. The typeface is still loaded and still never
 * awaited: if Fraunces has not arrived, the title renders in the platform
 * serif rather than not at all.
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
        <Text style={styles.sosGlyph}>✚</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: theme.spacing(2),
    paddingBottom: theme.spacing(2),
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
  sos: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.colour.danger,
  },
  sosGlyph: { color: '#fff', fontSize: 24, fontWeight: '700', lineHeight: 26 },
});
