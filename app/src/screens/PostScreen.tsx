import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { postBySlug, type Block } from '../content/posts';
import { theme } from '../lib/theme';

/**
 * One Learn post.
 *
 * The blocks are a small typed union rather than markdown, so there is no
 * parser and no renderer that can be handed something it cannot draw. It
 * also means the content is a TypeScript module the test suite reads
 * directly -- `content.test.ts` runs rule 1 over every string in it.
 */
function Rendered({ block }: { block: Block }) {
  switch (block.kind) {
    case 'heading':
      return <Text style={styles.heading}>{block.text}</Text>;
    case 'bullet':
      return (
        <View style={styles.bulletRow}>
          <Text style={styles.bulletMark}>•</Text>
          <Text style={styles.bulletText}>{block.text}</Text>
        </View>
      );
    case 'aside':
      return (
        <View style={styles.aside}>
          <Text style={styles.asideText}>{block.text}</Text>
        </View>
      );
    default:
      return <Text style={styles.paragraph}>{block.text}</Text>;
  }
}

export function PostScreen({ route }: { route: any }) {
  const post = postBySlug(route?.params?.slug);

  if (!post) {
    return (
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        <Text style={styles.paragraph}>That page is no longer here.</Text>
      </ScrollView>
    );
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{post.title}</Text>
      <Text style={styles.standfirst}>{post.standfirst}</Text>
      {post.blocks.map((block, i) => (
        <Rendered key={i} block={block} />
      ))}
      <Text style={styles.footnote}>
        Never eat a wild mushroom identified only by an app.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.colour.background },
  content: { padding: theme.spacing(3), gap: theme.spacing(1.5) },

  title: {
    fontSize: theme.font.title,
    lineHeight: 32,
    fontWeight: '700',
    color: theme.colour.text,
  },
  standfirst: {
    fontSize: theme.font.body,
    lineHeight: 24,
    color: theme.colour.textMuted,
    marginBottom: theme.spacing(1),
  },
  heading: {
    fontSize: theme.font.heading,
    fontWeight: '700',
    color: theme.colour.text,
    marginTop: theme.spacing(1.5),
  },
  paragraph: {
    fontSize: theme.font.body,
    lineHeight: 25,
    color: theme.colour.text,
  },
  bulletRow: { flexDirection: 'row', gap: theme.spacing(1) },
  bulletMark: { fontSize: theme.font.body, color: theme.colour.accent },
  bulletText: {
    flex: 1,
    fontSize: theme.font.body,
    lineHeight: 25,
    color: theme.colour.text,
  },
  aside: {
    backgroundColor: theme.colour.surfaceRaised,
    borderLeftWidth: 4,
    borderLeftColor: theme.colour.accent,
    borderRadius: theme.radius.sm,
    padding: theme.spacing(1.75),
    marginVertical: theme.spacing(0.5),
  },
  asideText: {
    fontSize: theme.font.small,
    lineHeight: 21,
    color: theme.colour.textMuted,
  },
  footnote: {
    fontSize: theme.font.small,
    color: theme.colour.textMuted,
    textAlign: 'center',
    marginTop: theme.spacing(2),
  },
});
