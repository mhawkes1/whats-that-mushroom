import React from 'react';
import {
  ImageBackground,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';

import { LinearGradient } from 'expo-linear-gradient';

import { theme } from '../lib/theme';

/**
 * The book's front cover, as the app's front page.
 *
 * Martin Hawkes's cover for *What's That Mushroom? — A first timer's guide to
 * identifying UK mushrooms*, reproduced from the companion ebook: the same
 * photograph, the same Fraunces setting, the same gold rule under it.
 *
 * Three things are different here, and each is a deliberate departure rather
 * than an approximation.
 *
 * **It is not full-screen.** On the cover of a book it is, and it should be.
 * On the first screen of an app a full-height cover is a wall: the thing the
 * user came to do is below the fold and they have to scroll past the title to
 * reach it. This takes about two thirds of the viewport, so the cover reads as
 * a cover and the first photo slot shows beneath it, inviting the scroll.
 *
 * **The emergency route is pinned to the top corner.** It is the one thing on
 * this screen that must never need a scroll, and someone opening the app
 * because a child has eaten something is not going to read a title first. It
 * is small and quiet until it is needed, which is the most it can be without
 * fighting the cover.
 *
 * **The edition flag is gone.** The book's cover carries "1st Edition · 25
 * most common species". The app's label space is 79, so on this screen that
 * line would simply be wrong.
 */
export function CoverHeader({ onEmergency }: { onEmergency: () => void }) {
  const { height } = useWindowDimensions();
  // Bounded rather than proportional alone: on a short phone two thirds is
  // not enough to hold the title block, and on a tall one it is more cover
  // than anybody needs.
  const coverHeight = Math.min(Math.max(height * 0.66, 420), 620);

  return (
    <ImageBackground
      source={require('../../assets/cover.jpg')}
      style={[styles.cover, { height: coverHeight }]}
      imageStyle={styles.image}
      accessible
      accessibilityLabel="A penny bun on the woodland floor"
    >
      <Pressable
        onPress={onEmergency}
        style={styles.sos}
        hitSlop={12}
        accessibilityRole="button"
        accessibilityLabel="Someone has eaten a wild mushroom. What to do."
      >
        <Text style={styles.sosGlyph}>✚</Text>
      </Pressable>

      {/* The scrim exists so the type stays legible over the leaf litter.
          A real gradient rather than stacked translucent views: flat bands
          leave visible edges across the photograph, which is the one thing
          a cover cannot have. The stops are the book's own. */}
      <LinearGradient
        colors={[
          'rgba(10,14,8,0)',
          'rgba(10,14,8,0.28)',
          'rgba(10,14,8,0.62)',
          'rgba(10,14,8,0.88)',
        ]}
        locations={[0, 0.45, 0.74, 1]}
        style={styles.scrim}
        pointerEvents="none"
      />

      <View style={styles.inner}>
        <Text style={styles.title} allowFontScaling={false}>
          What's That{'\n'}Mushroom<Text style={styles.question}>?</Text>
        </Text>
        <Text style={styles.subtitle}>
          A first timer's guide to identifying UK mushrooms
        </Text>
        <View style={styles.rule} />
        <Text style={styles.by}>MARTIN HAWKES</Text>
        <Text style={styles.byline}>The Shropshire Forager</Text>
      </View>
    </ImageBackground>
  );
}

const { cover: coverTheme } = theme;

const styles = StyleSheet.create({
  cover: {
    marginHorizontal: -theme.spacing(3),
    marginTop: -theme.spacing(3),
    justifyContent: 'flex-end',
    backgroundColor: coverTheme.ground,
    borderBottomWidth: 5,
    borderBottomColor: coverTheme.gold,
  },
  // The photograph is composed for its top: the cap is what a cover wants,
  // and centring it would crop the head off on a tall phone.
  image: { resizeMode: 'cover', alignSelf: 'flex-start' },

  sos: {
    position: 'absolute',
    top: theme.spacing(2),
    right: theme.spacing(2),
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(10,14,8,0.55)',
    borderWidth: 1,
    borderColor: theme.colour.danger,
  },
  sosGlyph: { color: theme.colour.danger, fontSize: 17, fontWeight: '900', lineHeight: 20 },

  scrim: { position: 'absolute', left: 0, right: 0, bottom: 0, height: '52%' },

  inner: { paddingHorizontal: theme.spacing(3.5), paddingBottom: theme.spacing(3.5) },
  title: {
    fontFamily: coverTheme.display,
    fontSize: 38,
    lineHeight: 40,
    color: '#ffffff',
    textAlign: 'center',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    textShadowColor: 'rgba(0,0,0,0.75)',
    textShadowOffset: { width: 0, height: 3 },
    textShadowRadius: 18,
  },
  question: { color: coverTheme.gold },
  subtitle: {
    fontFamily: coverTheme.displayItalic,
    fontStyle: Platform.OS === 'ios' ? 'normal' : 'italic',
    fontSize: 14,
    lineHeight: 18,
    color: coverTheme.subtitle,
    textAlign: 'center',
    marginTop: 11,
    textShadowColor: 'rgba(0,0,0,0.8)',
    textShadowOffset: { width: 0, height: 2 },
    textShadowRadius: 12,
  },
  rule: {
    width: 40,
    height: 1,
    backgroundColor: 'rgba(255,255,255,0.45)',
    alignSelf: 'center',
    marginTop: 14,
    marginBottom: 12,
  },
  by: {
    fontFamily: Platform.select({ ios: 'Menlo', default: 'monospace' }),
    fontSize: 11.5,
    letterSpacing: 2.4,
    color: '#ffffff',
    textAlign: 'center',
    textShadowColor: 'rgba(0,0,0,0.85)',
    textShadowOffset: { width: 0, height: 2 },
    textShadowRadius: 12,
  },
  byline: {
    fontFamily: coverTheme.displayItalic,
    fontStyle: Platform.OS === 'ios' ? 'normal' : 'italic',
    fontSize: 13,
    color: coverTheme.byline,
    textAlign: 'center',
    marginTop: 5,
    textShadowColor: 'rgba(0,0,0,0.85)',
    textShadowOffset: { width: 0, height: 2 },
    textShadowRadius: 12,
  },
});
