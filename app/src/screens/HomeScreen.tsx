import React, { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';

import { AppHeader } from '../components/AppHeader';
import { readLog, tally, type Tally } from '../lib/observationLog';
import { theme } from '../lib/theme';

/**
 * The tab that says what the app is for.
 *
 * Added 2026-10-29 with the tab bar. Martin had been looking at other
 * mushroom apps' home screens and wanted the same shape -- Home, Observe,
 * Me -- which solved a problem the capture screen had been carrying on its
 * own: there was nowhere in the app that explained what it does, so the
 * explaining had to happen in the corners of the screen people use to work.
 *
 * **Why the name and tagline live here and not on Observe.** Most apps do
 * not put their name on their working screen, because you tapped the icon
 * four seconds ago and know where you are. That is right, and it had a cost
 * specific to this app: "Funga" tells a beginner nothing about mushrooms --
 * the accepted trade when it was chosen -- and the TAGLINE was written to
 * carry the work the name could not. Dropping the header from Observe would
 * have taken the best six words in the product with it. Here, "what is this
 * app" is the actual question being asked, so the masthead earns its space
 * instead of costing it.
 *
 * **The counts are deliberately not flattering.** The two tiles split every
 * observation into the ones the app put a name to and the ones it would not,
 * and they show the refusals at the same size as the finds. An app whose
 * claim is that it admits when it does not know should keep score of the
 * admissions; a tally that quietly promoted every `dangerous_group` into a
 * find would be the same flattery as a history row that names a species it
 * refused to choose between.
 */
export function HomeScreen({ navigation }: { navigation: any }) {
  const [counts, setCounts] = useState<Tally | null>(null);

  useFocusEffect(
    useCallback(() => {
      readLog().then((entries) => setCounts(tally(entries)));
    }, []),
  );

  const started = (counts?.observations ?? 0) > 0;

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <AppHeader />

      {/* ONE number, and it is the user's own.
          Two tiles stood here until 2026-11-21: a green "named" count
          beside an "unnamed" one. Martin's objection retired them, and it
          is the argument this file had already made about a competitor's
          "Confirmed" tile, carried one step further. That tile was wrong
          because it claims a confirmer. "Named" claims a NAMER -- and
          there is no namer. There is a classifier with an unreviewed
          label space, `taxonomy_reviewed: false`, and nobody at all who
          has looked at the mushroom. A big filled number labelled "named"
          reads as a score of correct identifications, whatever the word
          literally means.

          So the tile counts the one thing that is beyond dispute: how
          many times the user pointed the camera. It cannot flatter, cannot
          mislead and needs nobody's confirmation.

          **The refusals stay, as a sentence rather than a score.** Losing
          them would cost the home screen its whole statement -- an app
          whose claim is that it admits when it does not know should keep
          score of the admissions. But a number in a box is a leaderboard,
          and the same fact in the app's own voice is a disclosure: it says
          what I DID, which is a fact about this app, rather than implying
          something was established. The number of finds is deliberately
          not stated at all, because that is the one that would read as
          "700 correct".

          The green went with the tile, which restores something the
          thesis panel's own comment already claimed: it is now genuinely
          the one block of solid colour in the app. */}
      <Pressable
        style={styles.observations}
        onPress={() => navigation.navigate('Me')}
        accessibilityRole="button"
        accessibilityLabel={
          started
            ? `${counts?.observations ?? 0} observations. I would not name a species on ${counts?.declined ?? 0} of them. Opens your observations.`
            : 'No observations yet. Opens your observations.'
        }
      >
        <Text style={styles.countNumber}>{counts?.observations ?? 0}</Text>
        <Text style={styles.countLabel}>observations</Text>
        {started ? (
          <Text style={styles.countAside}>
            {(counts?.declined ?? 0) > 0
              ? `On ${counts?.declined} of these I would not name a species.`
              : 'I have put a name to every one of them so far.'}
          </Text>
        ) : null}
      </Pressable>

      {!started ? (
        <Pressable
          style={styles.primary}
          onPress={() => navigation.navigate('Observe')}
          accessibilityRole="button"
        >
          <Text style={styles.primaryText}>Photograph a mushroom</Text>
        </Pressable>
      ) : null}

      {/* The one block of solid colour in the app. This paragraph is the
          product's whole argument and it used to be a cream card on a cream
          field -- the same weight as the photography tips below it. */}
      <View style={[styles.panel, styles.panelThesis]}>
        <Text style={[styles.panelHeading, styles.panelHeadingOn]}>
          What this app will not do
        </Text>
        <Text style={[styles.panelItem, styles.panelItemOn]}>
          <Text style={[styles.lead, styles.leadOn]}>It will never tell you a mushroom is safe
          to eat.</Text> There is no such category in it. It names what it can
          and warns about recorded hazards; where there is no hazard on record
          it says nothing at all, because silence is the honest answer and
          cannot be misread as permission.
        </Text>
        <Text style={[styles.panelItem, styles.panelItemOn]}>
          <Text style={[styles.lead, styles.leadOn]}>It will refuse rather than guess.</Text> If
          two species that look alike from a photograph are in play and one of
          them can kill, it names neither. That is the app working, not
          failing — and it is the whole difference between this and the apps
          that answer every time.
        </Text>
        <Text style={[styles.panelItem, styles.panelItemOn]}>
          <Text style={[styles.lead, styles.leadOn]}>It cannot see what you did not
          photograph.</Text> The base of the stem and the underside of the cap
          are where most answers are, and they are the parts almost everyone
          leaves in the ground.
        </Text>
      </View>

      <View style={styles.panel}>
        <Text style={styles.panelHeading}>Getting a useful answer</Text>
        <Text style={styles.tip}>
          • Lever the whole mushroom out rather than cutting it. The base
          matters and it is easy to lose.
        </Text>
        <Text style={styles.tip}>
          • Photograph the cap, the side and the underside. Each one rules
          things out that the others cannot.
        </Text>
        <Text style={styles.tip}>
          • Daylight beats indoor light for colour, and colour separates
          species that otherwise look identical.
        </Text>
      </View>

      {/* Here rather than on the working screen. Martin, 2026-10-29: on the
          capture screen this read as "something has gone wrong" to somebody
          who had just opened the app. It is still one tap from a tab that is
          always on screen, and the screen behind it is hardcoded and works
          with no signal. */}
      <Pressable
        style={styles.safety}
        onPress={() => navigation.navigate('Emergency')}
        accessibilityRole="button"
        accessibilityLabel="Someone has eaten a wild mushroom. What to do."
      >
        <Text style={styles.safetyText}>
          Someone has eaten a wild mushroom — what to do
        </Text>
      </Pressable>

      {/* Below the emergency route, never above it. Content must not push
          the one control that must never need a scroll any further down
          the page; that is the rule to hold whatever this section grows
          into. The photography tips above were this feature's stub, and
          the first post is their long form. */}
      <Pressable
        style={styles.learn}
        onPress={() => navigation.navigate('Learn')}
        accessibilityRole="button"
        accessibilityLabel="Before you start. Four short pieces on photographing and reading mushrooms."
      >
        <Text style={styles.learnHeading}>Before you start</Text>
        <Text style={styles.learnBody}>
          Why I refuse to answer sometimes, how to photograph a mushroom so
          I can do better, taking a spore print, and the three questions
          people answer wrongly.
        </Text>
        <Text style={styles.learnMore}>Four short pieces →</Text>
      </Pressable>

      <Text style={styles.footnote}>
        Never eat a wild mushroom identified only by an app.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.colour.background },
  content: { padding: theme.spacing(3), gap: theme.spacing(2.5) },

  observations: {
    backgroundColor: theme.colour.surface,
    borderWidth: 1,
    borderColor: theme.colour.border,
    borderRadius: theme.radius.md,
    padding: theme.spacing(2),
    gap: theme.spacing(0.5),
  },
  countAside: {
    fontSize: theme.font.small,
    lineHeight: 20,
    color: theme.colour.textMuted,
    marginTop: theme.spacing(1),
  },
  learn: {
    backgroundColor: theme.colour.surface,
    borderWidth: 1,
    borderColor: theme.colour.border,
    borderLeftWidth: 4,
    borderLeftColor: theme.colour.accent,
    borderRadius: theme.radius.md,
    padding: theme.spacing(2),
    gap: theme.spacing(0.75),
  },
  learnHeading: {
    fontSize: theme.font.heading,
    fontWeight: '700',
    color: theme.colour.text,
  },
  learnBody: {
    fontSize: theme.font.small,
    lineHeight: 20,
    color: theme.colour.textMuted,
  },
  learnMore: {
    fontSize: theme.font.small,
    fontWeight: '600',
    color: theme.colour.accent,
  },
  countNumber: {
    fontSize: 34,
    lineHeight: 38,
    fontWeight: '700',
    color: theme.colour.text,
  },
  countLabel: { fontSize: theme.font.small, color: theme.colour.textMuted },
  primary: {
    backgroundColor: theme.colour.accent,
    borderRadius: theme.radius.md,
    paddingVertical: theme.spacing(2),
    alignItems: 'center',
  },
  primaryText: {
    color: theme.colour.onAccent,
    fontSize: theme.font.body,
    fontWeight: '700',
  },

  panel: {
    backgroundColor: theme.colour.canopySurface,
    borderWidth: 1,
    borderColor: theme.colour.border,
    borderRadius: theme.radius.md,
    padding: theme.spacing(2.5),
    gap: theme.spacing(1.5),
  },
  panelThesis: {
    backgroundColor: theme.colour.canopyInk,
    borderColor: theme.colour.canopyInk,
  },
  panelHeadingOn: { color: theme.colour.lichen },
  panelItemOn: { color: theme.colour.onCanopyInk },
  leadOn: { color: theme.colour.onAccent },
  panelHeading: {
    fontSize: theme.font.small,
    fontWeight: '700',
    letterSpacing: 0.4,
    textTransform: 'uppercase',
    color: theme.colour.canopy,
  },
  panelItem: {
    fontSize: theme.font.body,
    lineHeight: 22,
    color: theme.colour.text,
  },
  lead: { fontWeight: '700' },
  tip: { fontSize: theme.font.body, lineHeight: 22, color: theme.colour.text },

  safety: {
    backgroundColor: theme.colour.dangerSurface,
    borderWidth: 1,
    borderColor: theme.colour.danger,
    borderRadius: theme.radius.md,
    paddingVertical: theme.spacing(2),
    paddingHorizontal: theme.spacing(2),
    alignItems: 'center',
  },
  safetyText: {
    color: theme.colour.danger,
    fontSize: theme.font.body,
    fontWeight: '700',
    textAlign: 'center',
  },
  footnote: {
    fontSize: theme.font.small,
    color: theme.colour.textMuted,
    textAlign: 'center',
  },
});
