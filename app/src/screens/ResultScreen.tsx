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
import {
  answerQuestion,
  hazardLabel,
  type Comparison,
  type IdentifyResponse,
  type Views,
} from '../lib/api';
import { fromResult, record, type Place } from '../lib/observationLog';
import { theme } from '../lib/theme';

/**
 * One lookalike, and what separates it from the species just named.
 *
 * Built from the lookalike graph, which is 92% complete across the label
 * space, and from `character_states`, which was written as a classifier
 * tiebreaker -- thin as a description and dense as a comparison. This
 * renders it as the second thing, which is what it is.
 *
 * **Shared states are shown, in their own line, last.** A feature both
 * species can show is the single most important thing on a page headed
 * "how to tell them apart", because it is the one a user will otherwise
 * settle it with. The funeral bell and honey fungus both show a firm
 * skirt-like ring; a panel that printed only the differences would have a
 * reader check the ring and conclude the wrong one.
 *
 * **It never says which is preferable.** The hazard renders exactly as it
 * does on a candidate row -- `NO_RECORDED_TOXICITY` renders as nothing --
 * and there is no line anywhere that compares the two on safety, because
 * the app has no view on that and a comparison is where an edibility claim
 * would get in wearing something else's clothes.
 */
function TellApart({ named, other }: { named: string; other: Comparison }) {
  const hazard = hazardLabel(other.toxicity);
  const common = other.common_names[0];
  return (
    <View style={styles.tellApart}>
      <View style={styles.tellApartHead}>
        <Text style={styles.tellApartName}>
          {common ?? other.scientific_name}
        </Text>
        {common ? (
          <Text style={styles.tellApartLatin}>{other.scientific_name}</Text>
        ) : null}
        {hazard ? <Text style={styles.tellApartHazard}>{hazard}</Text> : null}
      </View>

      {other.differences.length === 0 ? (
        <Text style={styles.tellApartNone}>
          These are confused with each other and nothing recorded here
          separates them from a photograph. Treat them as one until somebody
          who knows has looked.
        </Text>
      ) : (
        other.differences.map((d) => (
          <View key={d.character} style={styles.difference}>
            <Text style={styles.differenceLabel}>{d.label}</Text>
            {d.this_only.length ? (
              <Text style={styles.differenceLine}>
                <Text style={styles.differenceWho}>{named}: </Text>
                {d.this_only.join(', ')}
              </Text>
            ) : null}
            {d.other_only.length ? (
              <Text style={styles.differenceLine}>
                <Text style={styles.differenceWho}>
                  {common ?? other.scientific_name}:{' '}
                </Text>
                {d.other_only.join(', ')}
              </Text>
            ) : null}
            {d.shared.length ? (
              <Text style={styles.differenceShared}>
                Both can show: {d.shared.join(', ')} — so this does not settle it
              </Text>
            ) : null}
          </View>
        ))
      )}
    </View>
  );
}

/**
 * Result screen.
 *
 * Ordering is deliberate and is the opposite of the competition's:
 *
 *   1. the verdict, including a refusal when that is the honest answer
 *   2. the next diagnostic question, so the user can actually resolve it
 *   3. the candidate list, with a hazard on the rows that have one
 *   4. warnings
 *
 * The candidate list is not the headline. Putting a species name and a big
 * percentage at the top is precisely the design that gets people poisoned.
 */
export function ResultScreen({ navigation, route }: { navigation: any; route: any }) {
  const { imageUri, views, fieldNotes, place, identity } = route.params as {
    imageUri?: string;
    views?: Views;
    fieldNotes?: Record<string, string>;
    place?: Place | null;
    /**
     * Set when this screen is showing a REOPENED observation. The server
     * has issued a fresh id for the live session; the log entry keeps the
     * one it was first recorded under, or reopening a find appears in the
     * history as a second find, today, of the same mushroom.
     */
    identity?: { observationId: string; recordedAt: number };
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
        identity,
      }),
    );
  }, [result, views, imageUri, place, fieldNotes, identity]);

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

  /**
   * Whether the questions are asked, or merely offered.
   *
   * Martin, 2026-10-29: a wall of questions between the name and the
   * percentages gets skipped, because the user wants the answer and the
   * questions are in the way. True, and worth fixing -- but only where
   * skipping them is a reasonable thing to do.
   *
   * It is not reasonable when a deadly species holds mass or when the app
   * declined to name one. There the questions are not an optional extra:
   * they are the only mechanism that can resolve the ambiguity, and the
   * user's instinct to skip to the answer is exactly what you do not want
   * when there is no safe answer yet. Collapsing them behind a tap would
   * hide the one thing that could help, from the people it could help
   * most. Same shape as rule 5, which gates the taste question on whether
   * a deadly candidate holds mass.
   */
  const mustAsk = result.deadly_in_play || result.verdict !== 'species';
  const [opened, setOpened] = useState(false);
  const askingNow = mustAsk || opened;

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      {imageUri ? <Image source={{ uri: imageUri }} style={styles.photo} /> : null}

      <VerdictCard result={result} />

      {nextQuestion && !askingNow ? (
        /* The offer, not the question.
         *
         * It deliberately does NOT say "to increase the probability".
         * A consistent answer never boosts in this engine -- evidence
         * eliminates, and the leading species' share moves as a side
         * effect of its rivals being contradicted. It can fall: answering
         * the follow-up on a dangerous pair once moved the destroying
         * angel UP from 24% to 26%, because its partner was ruled out and
         * the mass had to go somewhere. A label promising the number will
         * rise would make that read as a malfunction, when it is the app
         * learning something.
         */
        <Pressable
          onPress={() => setOpened(true)}
          style={styles.offer}
          accessibilityRole="button"
          accessibilityLabel={
            `Answer ${result.questions.length} question` +
            `${result.questions.length === 1 ? '' : 's'} to narrow this down`
          }
        >
          <Text style={styles.offerTitle}>
            Tell me more and I'll rule things out
          </Text>
          <Text style={styles.offerSub}>
            {result.questions.length} question
            {result.questions.length === 1 ? '' : 's'} · this can change the
            answer
          </Text>
        </Pressable>
      ) : null}

      {nextQuestion && askingNow ? (
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
                      // The LOG id, which survives the two to twelve hours
                      // this takes. The server's session id does not.
                      observationId:
                        identity?.observationId ?? result.observation_id,
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

      {result.how_to_tell_apart?.length ? (
        <View style={styles.section}>
          <Text style={styles.sectionHeading}>
            HOW TO TELL IT FROM WHAT IT IS CONFUSED WITH
          </Text>
          {result.how_to_tell_apart.map((other) => (
            <TellApart
              key={other.species_key}
              named={result.candidates[0]?.common_names[0] ??
                     result.candidates[0]?.scientific_name ?? 'this'}
              other={other}
            />
          ))}
          <Text style={styles.tellApartFoot}>
            Recorded field confusions, not a judgement about either of them.
            Where a feature is listed under both, it cannot settle the
            question however obvious it looks.
          </Text>
        </View>
      ) : null}

      <View style={styles.warnings}>
        {result.warnings.map((warning) => (
          <Text key={warning} style={styles.warning}>
            {warning}
          </Text>
        ))}
        <Text style={styles.logged}>
          Saved to your observations, on this phone.
        </Text>

        {/* An app that says it might be wrong owes the user somewhere to say
            that it was. The report carries what this screen showed, so it is
            actionable without the server remembering the observation. */}
        <Pressable
          onPress={() =>
            navigation.navigate('Report', {
              observationId: result.observation_id,
              verdict: result.verdict,
              candidates: result.candidates.map((c) => c.species_key),
              modelVersion: result.model_version,
              calibrated: result.calibrated,
            })
          }
          style={styles.report}
          accessibilityRole="button"
        >
          <Text style={styles.reportText}>This is wrong — tell me why</Text>
        </Pressable>
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
  // An invitation, not an obstruction. Quiet enough that it does not
  // compete with the verdict above it, present enough that it is clearly
  // a thing to press.
  offer: {
    backgroundColor: theme.colour.surface,
    borderWidth: 1,
    borderColor: theme.colour.border,
    borderRadius: theme.radius.md,
    padding: theme.spacing(2),
    gap: 4,
  },
  offerTitle: {
    fontSize: theme.font.body,
    fontWeight: '700',
    color: theme.colour.accent,
  },
  offerSub: {
    fontSize: theme.font.small,
    color: theme.colour.textMuted,
  },
  tellApart: {
    backgroundColor: theme.colour.surface,
    borderWidth: 1,
    borderColor: theme.colour.border,
    borderRadius: theme.radius.md,
    padding: theme.spacing(2),
    gap: theme.spacing(1.5),
  },
  tellApartHead: { gap: 2 },
  tellApartName: {
    fontSize: theme.font.body,
    fontWeight: '700',
    color: theme.colour.text,
  },
  tellApartLatin: {
    fontSize: theme.font.small,
    fontStyle: 'italic',
    color: theme.colour.textMuted,
  },
  tellApartHazard: {
    fontSize: theme.font.small,
    fontWeight: '700',
    color: theme.colour.danger,
    marginTop: 2,
  },
  tellApartNone: {
    fontSize: theme.font.small,
    lineHeight: 20,
    color: theme.colour.text,
  },
  tellApartFoot: {
    fontSize: theme.font.small,
    lineHeight: 18,
    color: theme.colour.textMuted,
  },
  difference: { gap: 2 },
  differenceLabel: {
    fontSize: theme.font.small,
    fontWeight: '700',
    color: theme.colour.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  differenceLine: {
    fontSize: theme.font.small,
    lineHeight: 20,
    color: theme.colour.text,
  },
  differenceWho: { fontWeight: '700' },
  // Deliberately not muted into invisibility: a feature that settles
  // nothing is the one a user will otherwise settle it with.
  differenceShared: {
    fontSize: theme.font.small,
    lineHeight: 20,
    color: theme.colour.caution,
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
  report: {
    borderWidth: 1,
    borderColor: theme.colour.border,
    borderRadius: theme.radius.md,
    padding: theme.spacing(1.5),
    alignItems: 'center',
    marginTop: theme.spacing(1),
  },
  reportText: { fontSize: theme.font.small, color: theme.colour.textMuted, fontWeight: '600' },
});
