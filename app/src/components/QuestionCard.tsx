import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Question } from '../lib/api';
import { theme } from '../lib/theme';

const EFFORT_LABEL: Record<Question['effort'], string> = {
  instant: 'Look now',
  minutes: 'A few minutes',
  hours: 'Takes hours',
};

/**
 * A single diagnostic question.
 *
 * The `rationale` and `how` fields are always shown. Explaining why a question
 * is being asked, and how to answer it, is what separates this from a quiz --
 * and it is how the app teaches rather than merely pronounces.
 */
export function QuestionCard({
  question,
  onAnswer,
  disabled = false,
}: {
  question: Question;
  onAnswer: (answer: string) => void;
  disabled?: boolean;
}) {
  const critical = Boolean(question.safety_note);

  return (
    <View style={[styles.card, critical && styles.criticalCard]}>
      <View style={styles.headerRow}>
        <Text style={[styles.label, critical && { color: theme.colour.danger }]}>
          {question.label.toUpperCase()}
        </Text>
        <Text style={styles.effort}>{EFFORT_LABEL[question.effort]}</Text>
      </View>

      <Text style={styles.prompt}>{question.prompt}</Text>
      <Text style={styles.rationale}>{question.rationale}</Text>

      {question.safety_note ? (
        <View style={styles.safetyBox}>
          <Text style={styles.safetyText}>{question.safety_note}</Text>
        </View>
      ) : null}

      <Text style={styles.how}>{question.how}</Text>

      <View style={styles.options}>
        {question.options.map((option) => (
          <Pressable
            key={option}
            onPress={() => onAnswer(option)}
            disabled={disabled}
            style={({ pressed }) => [
              styles.option,
              pressed && styles.optionPressed,
              disabled && styles.optionDisabled,
            ]}
            accessibilityRole="button"
          >
            <Text style={styles.optionText}>{option}</Text>
          </Pressable>
        ))}
      </View>

      <Pressable onPress={() => onAnswer('')} disabled={disabled}>
        <Text style={styles.skip}>I can't tell / skip this</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.colour.surface,
    borderRadius: theme.radius.lg,
    padding: theme.spacing(2.5),
    gap: theme.spacing(1.25),
    borderWidth: 1,
    borderColor: theme.colour.border,
  },
  criticalCard: { borderColor: theme.colour.danger, borderWidth: 2 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between' },
  label: {
    fontSize: theme.font.tiny,
    fontWeight: '800',
    letterSpacing: 0.8,
    color: theme.colour.accent,
  },
  effort: { fontSize: theme.font.tiny, color: theme.colour.textFaint },
  prompt: {
    fontSize: theme.font.heading,
    color: theme.colour.text,
    fontWeight: '600',
    lineHeight: 26,
  },
  rationale: {
    fontSize: theme.font.small,
    color: theme.colour.confident,
    lineHeight: 20,
  },
  safetyBox: {
    backgroundColor: theme.colour.dangerSurface,
    borderRadius: theme.radius.sm,
    padding: theme.spacing(1.5),
  },
  safetyText: {
    fontSize: theme.font.small,
    color: theme.colour.text,
    lineHeight: 20,
  },
  how: {
    fontSize: theme.font.small,
    color: theme.colour.textMuted,
    lineHeight: 20,
  },
  options: { gap: theme.spacing(1), marginTop: theme.spacing(0.5) },
  option: {
    backgroundColor: theme.colour.surfaceRaised,
    borderRadius: theme.radius.md,
    paddingVertical: theme.spacing(1.75),
    paddingHorizontal: theme.spacing(2),
  },
  optionPressed: { backgroundColor: theme.colour.border },
  optionDisabled: { opacity: 0.4 },
  optionText: { fontSize: theme.font.body, color: theme.colour.text },
  skip: {
    fontSize: theme.font.small,
    color: theme.colour.textFaint,
    textAlign: 'center',
    paddingVertical: theme.spacing(1),
  },
});
