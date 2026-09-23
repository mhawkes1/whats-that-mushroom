import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Candidate, hazardLabel } from '../lib/api';
import { theme } from '../lib/theme';

const TOXICITY_COLOUR: Record<string, string> = {
  DEADLY: theme.colour.danger,
  SERIOUS: theme.colour.danger,
  TOXIC: theme.colour.caution,
  UNKNOWN: theme.colour.textMuted,
};

/**
 * One candidate species.
 *
 * A hazard chip is rendered wherever there is a hazard to report, including
 * on the leading candidate, and a deadly candidate gets a full-width bar
 * rather than a subtle tint: a user scrolling quickly must not be able to
 * miss it. Where the app has no hazard to report it says nothing rather
 * than filling the slot, because this identifies mushrooms and does not
 * rule on eating them.
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
  const hazard = hazardLabel(candidate.toxicity);

  return (
    <View
      style={[styles.row, isDeadly && styles.deadlyRow]}
      accessibilityLabel={
        hazard
          ? `${candidate.scientific_name}. ${hazard}`
          : candidate.scientific_name
      }
    >
      <View style={[styles.stripe, { backgroundColor: colour }]} />

      <View style={styles.body}>
        <Text style={styles.scientific}>{candidate.scientific_name}</Text>

        {candidate.common_names.length > 0 ? (
          <Text style={styles.common}>{candidate.common_names.join(' · ')}</Text>
        ) : null}

        {hazard ? (
          <Text style={[styles.toxicity, { color: colour }]}>{hazard}</Text>
        ) : null}
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
