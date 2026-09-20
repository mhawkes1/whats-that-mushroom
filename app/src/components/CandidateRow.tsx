import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Candidate, TOXICITY_LABEL } from '../lib/api';
import { theme } from '../lib/theme';

const TOXICITY_COLOUR: Record<string, string> = {
  DEADLY: theme.colour.danger,
  SERIOUS: theme.colour.danger,
  TOXIC: theme.colour.caution,
  INEDIBLE: theme.colour.textMuted,
  UNKNOWN: theme.colour.textMuted,
};

/**
 * One candidate species.
 *
 * The toxicity chip is always rendered, including for the leading candidate,
 * and a deadly candidate gets a full-width bar rather than a subtle tint. A
 * user scrolling quickly must not be able to miss it.
 */
export function CandidateRow({
  candidate,
  showConfidence = true,
}: {
  candidate: Candidate;
  showConfidence?: boolean;
}) {
  const colour = TOXICITY_COLOUR[candidate.toxicity] ?? theme.colour.textMuted;
  const isDeadly = candidate.toxicity === 'DEADLY';

  return (
    <View
      style={[styles.row, isDeadly && styles.deadlyRow]}
      accessibilityLabel={`${candidate.scientific_name}. ${
        TOXICITY_LABEL[candidate.toxicity]
      }`}
    >
      <View style={[styles.stripe, { backgroundColor: colour }]} />

      <View style={styles.body}>
        <Text style={styles.scientific}>{candidate.scientific_name}</Text>

        {candidate.common_names.length > 0 ? (
          <Text style={styles.common}>{candidate.common_names.join(' · ')}</Text>
        ) : null}

        <Text style={[styles.toxicity, { color: colour }]}>
          {TOXICITY_LABEL[candidate.toxicity]}
        </Text>
      </View>

      {showConfidence ? (
        <Text style={styles.confidence}>
          {Math.round(candidate.confidence * 100)}%
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colour.surface,
    borderRadius: theme.radius.md,
    overflow: 'hidden',
    gap: theme.spacing(1.5),
  },
  deadlyRow: {
    borderWidth: 1,
    borderColor: theme.colour.danger,
  },
  stripe: { width: 5, alignSelf: 'stretch' },
  body: { flex: 1, paddingVertical: theme.spacing(1.5), gap: 2 },
  scientific: {
    fontSize: theme.font.body,
    fontStyle: 'italic',
    color: theme.colour.text,
    fontWeight: '600',
  },
  common: { fontSize: theme.font.small, color: theme.colour.textMuted },
  toxicity: { fontSize: theme.font.tiny, fontWeight: '700', marginTop: 2 },
  confidence: {
    fontSize: theme.font.body,
    color: theme.colour.textFaint,
    fontVariant: ['tabular-nums'],
    paddingRight: theme.spacing(2),
  },
});
