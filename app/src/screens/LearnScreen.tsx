import React from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { POSTS } from '../content/posts';
import { theme } from '../lib/theme';

/**
 * The index of the Learn posts.
 *
 * Text-led rather than photograph-led, which is the opposite of how every
 * other app does this and is a deliberate trade: the cards are legible
 * with no network, because the posts are bundled and a wood is where the
 * network is not. Photographs can be added later without changing
 * anything structural -- they would be bundled assets too, never remote.
 *
 * It is a stack screen rather than a fourth tab. The content does not yet
 * justify permanent space in the tab bar, and the home screen already had
 * the stub of this feature in its photography tips.
 */
/**
 * Martin's own photographs, one per post, derived by
 * `scripts/build_learn_images.py` from `docs/design/learn/`.
 *
 * The map lives here rather than in `posts.ts` on purpose: `require` of a
 * .jpg is a Metro thing, and `content.test.ts` imports `posts.ts` under
 * vitest, which cannot load an image. Keeping the data module free of
 * assets keeps the rule 1 scanner able to read it. A test asserts every
 * slug below has a post and every file exists -- a missing asset stops an
 * Expo build, which is the icons.test.ts lesson in a new place.
 *
 * What rules a frame out is not the species but the composition: no
 * mushroom held in a hand, which is a picking gesture, and nothing lit
 * as a portrait of produce. These four are all in situ where they grew.
 */
const IMAGES: Record<string, number> = {
  'why-i-refuse': require('../../assets/learn/why-i-refuse.jpg'),
  'photographing-a-mushroom': require('../../assets/learn/photographing-a-mushroom.jpg'),
  'spore-prints': require('../../assets/learn/spore-prints.jpg'),
  'answers-that-mislead-me': require('../../assets/learn/answers-that-mislead-me.jpg'),
};

export function LearnScreen({ navigation }: { navigation: any }) {
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.intro}>
        Four things worth knowing before you point a camera at a mushroom.
        None of them tells you whether anything is safe to eat; this app
        has no such category in it.
      </Text>

      {POSTS.map((post) => (
        <Pressable
          key={post.slug}
          style={styles.card}
          onPress={() => navigation.navigate('Post', { slug: post.slug })}
          accessibilityRole="button"
          accessibilityLabel={`${post.title}. ${post.standfirst}`}
        >
          <Image
            source={IMAGES[post.slug]}
            style={styles.cardPhoto}
            resizeMode="cover"
            accessible={false}
          />
          <View style={styles.cardText}>
            <Text style={styles.cardTitle}>{post.title}</Text>
            <Text style={styles.cardStandfirst}>{post.standfirst}</Text>
          </View>
        </Pressable>
      ))}

      <View style={styles.note}>
        <Text style={styles.noteText}>
          There is nothing here yet about telling one species from another in
          the field. That needs a qualified mycologist to have read it, and
          none has read this app&apos;s species data either — which is why
          every screen that names something says so.
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.colour.background },
  content: { padding: theme.spacing(3), gap: theme.spacing(2) },

  intro: {
    fontSize: theme.font.body,
    lineHeight: 24,
    color: theme.colour.textMuted,
  },

  card: {
    backgroundColor: theme.colour.surface,
    borderWidth: 1,
    borderColor: theme.colour.border,
    borderRadius: theme.radius.md,
    overflow: 'hidden',
  },
  // 4:3 at the 390pt reference width. A real height, not `aspectRatio`:
  // React Native Web ignores the ratio and sizes the element from the
  // asset's own pixels. See the note on `learnPhoto` in HomeScreen.
  cardPhoto: { width: '100%', height: 256 },
  cardText: { padding: theme.spacing(2), gap: theme.spacing(0.75) },
  cardTitle: {
    fontSize: theme.font.heading,
    fontWeight: '700',
    color: theme.colour.text,
  },
  cardStandfirst: {
    fontSize: theme.font.small,
    lineHeight: 20,
    color: theme.colour.textMuted,
  },

  note: {
    backgroundColor: theme.colour.surfaceRaised,
    borderRadius: theme.radius.md,
    padding: theme.spacing(2),
  },
  noteText: {
    fontSize: theme.font.small,
    lineHeight: 20,
    color: theme.colour.textMuted,
  },
});
