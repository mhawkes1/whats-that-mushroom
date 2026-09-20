import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { theme } from '../lib/theme';
import { IdentifyResponse, verdictColour } from '../lib/api';

/**
 * The verdict banner.
 *
 * This is the single most important piece of UI in the app. It occupies the
 * top of the result screen and states plainly what the app is and is not
 * willing to claim. Competing apps put a species name and a percentage here;
 * when we cannot honestly do that, this says so instead.
 */
export function VerdictCard({ result }: { result: IdentifyResponse }) {
  const accent = verdictColour(result.verdict, result.deadly_in_play, theme.colour);
  const isDangerous = result.verdict === 'dangerous_group' || result.deadly_in_play;

  return (
    <View
      style={[
        styles.card,
        {
          borderColor: accent,
          backgroundColor: isDangerous
            ? theme.colour.dangerSurface
            : theme.colour.surface,
        },
      ]}
      accessibilityRole="header"
    >
      {isDangerous ? (
        <Text style={[styles.flag, { color: accent }]}>
          A SPECIES THAT CAN KILL IS AMONG THE POSSIBILITIES
        </Text>
      ) : null}

      <Text style={[styles.headline, { color: accent }]}>{result.headline}</Text>

      {result.detail ? <Text style={styles.detail}>{result.detail}</Text> : null}

      {!result.calibrated ? (
        <Text style={styles.uncalibrated}>
          This model has not been calibrated. Treat the percentages below as
          rough ordering only, not as probabilities.
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderWidth: 2,
    borderRadius: theme.radius.lg,
    padding: theme.spacing(2.5),
    gap: theme.spacing(1.5),
  },
  flag: {
    fontSize: theme.font.tiny,
    fontWeight: '800',
    letterSpacing: 0.8,
  },
  headline: {
    fontSize: theme.font.title,
    fontWeight: '700',
    lineHeight: 32,
  },
  detail: {
    fontSize: theme.font.body,
    color: theme.colour.textMuted,
    lineHeight: 23,
  },
  uncalibrated: {
    fontSize: theme.font.tiny,
    color: theme.colour.caution,
    fontStyle: 'italic',
  },
});
