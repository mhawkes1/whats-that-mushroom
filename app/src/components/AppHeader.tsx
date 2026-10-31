import React from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';

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
 * The front page's masthead.
 *
 * **A photograph came back on 2026-10-31, and it is deliberately not of a
 * mushroom.** The one that was here until 2026-09-29 was the book cover: a
 * cep, filling the frame, lit like a portrait. That is the composition every
 * foraging app opens with, and on this app it is an implication -- a prize
 * edible presented as the first thing you see, by the one product whose
 * whole claim is that it will not tell you what is safe to eat. It makes no
 * claim and breaks no rule, and it says the wrong thing.
 *
 * This is a sphagnum bank from one of Martin's own frames, cropped from the
 * third of it with no fruiting body in it at all. Woodland is what the
 * screen should have been saying; the mushroom is the user's job, not the
 * masthead's.
 *
 * **The darkening is baked into the asset, not applied here.** The band
 * carries cream text, and a filter applied at render time is a second thing
 * that has to arrive. On a slow decode the photograph can paint before the
 * overlay does, and for that frame the title is cream on sunlit moss --
 * the one state this image must never be in. `scripts/build_masthead.py`
 * ships it dark, so the worst case is a dark band with no text yet.
 *
 * **The scrim is `photoScrim` and the text is `onAccent`, which is the
 * existing rule rather than a new one.** What sits under this scrim is a
 * photograph, so it is not themed and cannot be reasoned about from the
 * palette -- which is exactly why `theme.ts` says text on it is `onAccent`
 * and never `text`. Measured against this image at the token's own 0.62:
 * worst case 11.63:1 on the brightest moss a letter can land on, mean
 * 16.73:1. The first number is the one that matters; a single bright tuft
 * under the tagline is the failure, not the average.
 *
 * Those figures are why the asset is as dark as it is. At the brightness
 * the preview was judged on, the worst case fell to 4.10:1 -- legible for
 * the title, below AA for the tagline. Keeping more of the moss's colour
 * was measured and cost too much.
 *
 * **The mark is a PNG because the client has no SVG renderer**, and adding
 * one to draw two curves would be a dependency for a decoration. It is
 * generated from the same path data the launcher icons come from, so the
 * two cannot drift.
 *
 * **This lives on Home and not on the working screen.** Most apps do not
 * name themselves on the screen you use, because you tapped the icon four
 * seconds ago. The cost here was specific: "Funga" tells a beginner nothing
 * about mushrooms, and the tagline was written to carry exactly that. On
 * Home, "what is this app" is the question being asked, so the masthead
 * earns its space.
 *
 * **The emergency route is NOT here.** It was, from the book cover onwards,
 * because it is the one control that must never need a scroll. Martin
 * dropped it from the header on 2026-10-29: Home carries it as a plain
 * button and the capture screen's own is pinned outside its ScrollView, so
 * it is on screen whatever the user has scrolled to -- which it was not
 * before, on any real phone. Restoring a photograph to this component is
 * exactly the kind of change that cost the app its panic button last time.
 * It did not this time, and `emergencyRoute.test.ts` is what holds that
 * line rather than this comment.
 */
export function AppHeader() {
  return (
    <View style={styles.header}>
      <Image
        source={require('../../assets/masthead.jpg')}
        style={styles.photo}
        resizeMode="cover"
        // Decorative. The name is read out by the title below it, and a
        // screen reader announcing "photograph of moss" before the app's
        // own name is noise.
        accessible={false}
        accessibilityElementsHidden
        importantForAccessibility="no"
      />
      <View style={styles.scrim} />

      <View style={styles.block}>
        <Image
          source={require('../../assets/mark-cream.png')}
          style={styles.mark}
          resizeMode="contain"
          accessible={false}
          accessibilityElementsHidden
          importantForAccessibility="no"
        />
        <Text style={styles.title} allowFontScaling={false}>
          {APP_NAME}
        </Text>
        <View style={styles.rule} />
        <Text style={styles.tagline}>{TAGLINE}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  // Full bleed. HomeScreen insets its content by spacing(3) and the masthead
  // is the one block that should touch the edges, so it pulls back out by
  // exactly that much. A band with a margin reads as a card about the app
  // rather than as the top of it.
  header: {
    height: 150,
    marginHorizontal: -theme.spacing(3),
    marginTop: -theme.spacing(3),
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  photo: { ...StyleSheet.absoluteFillObject, width: undefined, height: undefined },
  // Not a new colour: the palette's own scrim for text over a photograph.
  scrim: { ...StyleSheet.absoluteFillObject, backgroundColor: theme.colour.photoScrim },

  block: { alignItems: 'center', paddingHorizontal: theme.spacing(2) },
  mark: { width: 44, height: 44 },
  title: {
    fontFamily: theme.cover.display,
    fontSize: 30,
    lineHeight: 36,
    marginTop: theme.spacing(0.5),
    // Over a photograph, never `text`. See the note on `photoScrim`.
    color: theme.colour.onAccent,
  },
  // What is left of the book's rule. It was the gold until the masthead went
  // over a photograph, where gold at 3.9:1 against the scrimmed moss was the
  // faintest thing on the screen. Cream is the same gesture and legible.
  rule: {
    height: 3,
    width: 44,
    backgroundColor: theme.colour.onAccent,
    opacity: 0.85,
    marginTop: theme.spacing(0.75),
    marginBottom: theme.spacing(0.75),
  },
  tagline: {
    fontSize: theme.font.small,
    color: theme.colour.onAccent,
    textAlign: 'center',
  },
});
