import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { CandidateRow } from '../components/CandidateRow';
import { QuestionCard } from '../components/QuestionCard';
import { VerdictCard } from '../components/VerdictCard';
import { answerQuestion, type IdentifyResponse, type Views } from '../lib/api';
import { fromResult, record, type Place } from '../lib/observationLog';
import { theme } from '../lib/theme';

/**
 * Result screen.
 *
 * Ordering is deliberate and is the opposite of the competition's:
 *
 *   1. the verdict, including a refusal when that is the honest answer
 *   2. the next diagnostic question, so the user can actually resolve it
 *   3. the candidate list, with toxicity on every row
 *   4. warnings
 *
 * The candidate list is not the headline. Putting a species name and a big
 * percentage at the top is precisely the design that gets people poisoned.
 */
export function ResultScreen({ navigation, route }: { navigation: any; route: any }) {
  const { imageUri, views, fieldNotes, place } = route.params as {
    imageUri?: string;
    views?: Views;
    fieldNotes?: Record<string, string>;
    place?: Place | null;
  };
  const [result, setResult] = useState<IdentifyResponse>(route.params.result);
  const [busy, setBusy] = useState(false);
  // Answers given here, as opposed to on the field-notes form. Kept in a ref
  // rather than state because nothing on this screen renders them and a
  // re-render between the answer and the save would lose one.
  const answers = useRef<Record<string, string>>({});

  // Logged on arrival and re-logged after every answer, keyed on the
  // observation id so the entry is replaced rather than duplicated. An
  // answered question often turns a refusal into an identification or the
  // reverse, and the log holds where the user got to, not where they started.
  //
  // Refusals are saved like anything else. A history that quietly kept only
  // the confident results would misrepresent the app to its own user.
  useEffect(() => {
    record(
      fromResult(result, {
        photos: views ?? (imageUri ? { top: imageUri } : {}),
        place: place ?? null,
        fieldNotes,
        answers: answers.current,
      }),
    );
  }, [result, views, imageUri, place, fieldNotes]);

  const onAnswer = useCallback(
    async (characterKey: string, answer: string) => {
      setBusy(true);
      try {
        const next = await answerQuestion(result.observation_id, characterKey, answer);
        answers.current = { ...answers.current, [characterKey]: answer };
        setResult(next);
      } catch {
        // Keep the current result on failure; the user loses nothing.
      } finally {
        setBusy(false);
      }
    },
    [result.observation_id],
  );

  const nextQuestion = result.questions[0];

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      {imageUri ? <Image source={{ uri: imageUri }} style={styles.photo} /> : null}

      <VerdictCard result={result} />

      {nextQuestion ? (
        <View style={styles.section}>
          <Text style={styles.sectionHeading}>
            {result.deadly_in_play ? 'CHECK THIS BEFORE ANYTHING ELSE' : 'NARROW IT DOWN'}
          </Text>
          <QuestionCard
            question={nextQuestion}
            disabled={busy}
            onAnswer={(answer) => onAnswer(nextQuestion.key, answer)}
            // The only character the app can currently walk someone through
            // obtaining. It is also the one that takes hours and the one that
            // most often settles a lethal ambiguity.
            onGuide={
              nextQuestion.key === 'spore_print_colour'
                ? () =>
                    navigation.navigate('SporePrint', {
                      observationId: result.observation_id,
                      onMatched: (option: string) =>
                        onAnswer('spore_print_colour', option),
                    })
                : undefined
            }
          />
          {result.questions.length > 1 ? (
            <Text style={styles.remaining}>
              {result.questions.length - 1} more question
              {result.questions.length > 2 ? 's' : ''} after this
            </Text>
          ) : null}
        </View>
      ) : null}

      {busy ? <ActivityIndicator color={theme.colour.accent} /> : null}

      <View style={styles.section}>
        <Text style={styles.sectionHeading}>POSSIBILITIES</Text>
        {result.candidates.map((candidate) => (
          <CandidateRow key={candidate.species_key} candidate={candidate} />
        ))}
      </View>

      <View style={styles.warnings}>
        {result.warnings.map((warning) => (
          <Text key={warning} style={styles.warning}>
            {warning}
          </Text>
        ))}
        <Text style={styles.logged}>
          Saved to your observations, on this phone.
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.colour.background },
  content: { padding: theme.spacing(2), gap: theme.spacing(2.5) },
  photo: {
    width: '100%',
    height: 220,
    borderRadius: theme.radius.lg,
    backgroundColor: theme.colour.surface,
  },
  section: { gap: theme.spacing(1.25) },
  sectionHeading: {
    fontSize: theme.font.tiny,
    fontWeight: '800',
    letterSpacing: 0.9,
    color: theme.colour.textFaint,
  },
  remaining: {
    fontSize: theme.font.tiny,
    color: theme.colour.textFaint,
    textAlign: 'center',
  },
  warnings: {
    gap: theme.spacing(1.25),
    borderTopWidth: 1,
    borderTopColor: theme.colour.border,
    paddingTop: theme.spacing(2),
  },
  warning: {
    fontSize: theme.font.small,
    color: theme.colour.textMuted,
    lineHeight: 21,
  },
  logged: { fontSize: theme.font.tiny, color: theme.colour.textFaint },
});
