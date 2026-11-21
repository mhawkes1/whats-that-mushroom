import React, { useCallback, useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
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

      {/* The one block of solid colour in the app, and since 2026-11-21
          three lines rather than three paragraphs.

          Each claim used to carry a sentence of explanation -- about 200
          words, the tallest thing on the page. Those explanations are now
          `why-i-refuse`, at greater length than they ever had here, so
          keeping both was the duplication this screen created the day the
          Learn posts landed. What stays is the standing statement: the
          consent gate states the terms once, with a tick, and never again.

          Deleting it outright was the alternative and would have left the
          home screen explaining nothing, which is the gap this tab was
          added to fill. */}
      <View style={[styles.panel, styles.panelThesis]}>
        <Text style={[styles.panelHeading, styles.panelHeadingOn]}>
          What this app will not do
        </Text>
        <Text style={[styles.claim, styles.panelItemOn]}>
          It will never tell you a mushroom is safe to eat.
        </Text>
        <Text style={[styles.claim, styles.panelItemOn]}>
          It will refuse rather than guess.
        </Text>
        <Text style={[styles.claim, styles.panelItemOn]}>
          It cannot see what you did not photograph.
        </Text>
        <Pressable
          onPress={() => navigation.navigate('Post', { slug: 'why-i-refuse' })}
          accessibilityRole="button"
          accessibilityLabel="Why I refuse to answer. Opens the article."
        >
          <Text style={styles.panelLink}>Why I refuse →</Text>
        </Pressable>
      </View>

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
        {/* `width: '100%'` with a real height -- see `learnPhoto` for
            why neither the absoluteFill-with-undefined idiom nor
            `aspectRatio` works on React Native Web. */}
        <Image
          source={require('../../assets/learn/home.jpg')}
          style={styles.learnPhoto}
          resizeMode="cover"
          accessible={false}
        />
        <View style={styles.learnText}>
          <Text style={styles.learnHeading}>Before you start</Text>
          <Text style={styles.learnBody}>
            Why I refuse to answer sometimes, how to photograph a mushroom
            so I can do better, taking a spore print, and the three
            questions people answer wrongly.
          </Text>
          <Text style={styles.learnMore}>Four short pieces →</Text>
        </View>
      </Pressable>

      {/* Below the Learn card since 2026-11-21, and it used to be above
          it with a comment saying content must never push this control
          down the page. Martin reversed that: *"I want this at the bottom
          to scroll to. As not on the main screen when first upload."*

          It is the same judgement he made on 2026-10-29 when it came off
          the capture screen -- "I don't want the app to seem alarming
          from the off" -- carried one step further, and `docs/SAFETY.md`
          carries the full argument on both sides.

          What it costs, stated rather than glossed: this is the only
          route into the emergency screen a user meets in ordinary use.
          The consent screen's fires once, before first use, and the
          report flow's is several taps into a form. So the control for
          "a child has eaten something" now needs one flick of a scroll.
          What is NOT given up is anything SAFETY.md required: the screen
          stays hardcoded, offline, above the consent gate, and reachable
          by more than one route. */}
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
  claim: { fontSize: theme.font.body, lineHeight: 24, fontWeight: '600' },
  panelLink: {
    fontSize: theme.font.small,
    fontWeight: '700',
    color: theme.colour.lichen,
    marginTop: theme.spacing(0.5),
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
    borderRadius: theme.radius.md,
    overflow: 'hidden',
  },
  // An explicit HEIGHT, matching 4:3 at the 390pt reference width, and
  // never `aspectRatio`. Measured in the running client: with
  // `{width: '100%', aspectRatio: 4/3}` the element came back
  // **340x585** -- ratio 0.58, portrait -- because React Native Web
  // ignored the ratio and took the asset's INTRINSIC PIXEL HEIGHT as its
  // CSS height. That is the masthead fault a third time: on this
  // platform an <Image> will size itself from its source unless a real
  // dimension stops it.
  //
  // 342pt of card at 4:3 is 256. A 360pt phone's card is 312 and a 430's
  // is 382, so `cover` trims about 8% of width at the small end and 11%
  // of height at the large one -- the masthead's own note already says
  // there is no single correct aspect, and 390 is this project's
  // reference width.
  learnPhoto: { width: '100%', height: 256 },
  learnText: { padding: theme.spacing(2), gap: theme.spacing(0.75) },
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
