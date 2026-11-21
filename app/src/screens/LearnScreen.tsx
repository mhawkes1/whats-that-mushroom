import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

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
          <Text style={styles.cardTitle}>{post.title}</Text>
          <Text style={styles.cardStandfirst}>{post.standfirst}</Text>
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
    borderLeftWidth: 4,
    borderLeftColor: theme.colour.accent,
    borderRadius: theme.radius.md,
    padding: theme.spacing(2),
    gap: theme.spacing(0.75),
  },
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
