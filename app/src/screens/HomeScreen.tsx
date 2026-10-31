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
 * **The counts are deliberately not flattering.** `tally` counts a species
 * only where the app was willing to NAME one, and shows the number of times
 * it declined beside it. An app whose claim is that it admits when it does
 * not know should keep score of the admissions; a tally that quietly
 * promoted every `dangerous_group` into a find would be the same flattery as
 * a history row that names a species it refused to choose between.
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

      <View style={styles.counts}>
        {/* Filled, where its neighbour is not. Martin's call, 2026-10-31:
            green marks the observations the app could put a name to. The
            line that comes with it is in `theme.ts` -- moss may mark
            confidence in an identification and never the standing of a
            species, which is why a hazard chip sits beside the name in the
            log rather than taking its colour from this. */}
        <Pressable
          style={[styles.count, styles.countNamed]}
          onPress={() => navigation.navigate('Me')}
          accessibilityRole="button"
          accessibilityLabel={`${counts?.species ?? 0} species named. Opens your observations.`}
        >
          <Text style={[styles.countNumber, styles.countOn]}>{counts?.species ?? 0}</Text>
          <Text style={[styles.countLabel, styles.countOn]}>
            species{'\n'}named
          </Text>
        </Pressable>

        {/* Shown beside the find count rather than buried, because in this
            app a refusal is the product working.

            It opens the log too. It was a plain View until Martin tapped it
            on 2026-10-31 and nothing happened -- which made the refusals
            look like a score rather than a list of observations worth
            going back to, and that is the opposite of why the tile is
            here. The two tiles count the same log and must behave the
            same way; a tile that reads as tappable beside one that is
            teaches that neither is. */}
        <Pressable
          style={styles.count}
          onPress={() => navigation.navigate('Me')}
          accessibilityRole="button"
          accessibilityLabel={`${counts?.declined ?? 0} times I wouldn't say. Opens your observations.`}
        >
          <Text style={styles.countNumber}>{counts?.declined ?? 0}</Text>
          <Text style={styles.countLabel}>
            times I{'\n'}wouldn't say
          </Text>
        </Pressable>
      </View>

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

      <Text style={styles.footnote}>
        Never eat a wild mushroom identified only by an app.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.colour.background },
  content: { padding: theme.spacing(3), gap: theme.spacing(2.5) },

  counts: { flexDirection: 'row', gap: theme.spacing(2) },
  count: {
    flex: 1,
    backgroundColor: theme.colour.surface,
    borderWidth: 1,
    borderColor: theme.colour.border,
    borderRadius: theme.radius.md,
    padding: theme.spacing(2),
    gap: theme.spacing(0.5),
  },
  countNumber: {
    fontSize: 34,
    lineHeight: 38,
    fontWeight: '700',
    color: theme.colour.text,
  },
  countLabel: { fontSize: theme.font.small, color: theme.colour.textMuted },
  countNamed: { backgroundColor: theme.colour.accent, borderColor: theme.colour.accent },
  countOn: { color: theme.colour.onAccent },

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
