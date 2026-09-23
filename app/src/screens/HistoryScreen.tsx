import React, { useCallback, useState } from 'react';
import {
  Alert,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';

import { CandidateRow } from '../components/CandidateRow';
import { getHealth, type Candidate } from '../lib/api';
import {
  caveats,
  forget,
  forgetAll,
  forgetPlaces,
  photoUri,
  readLog,
  recencyLabel,
  summarise,
  type LoggedCandidate,
  type Observation,
  type Tone,
} from '../lib/observationLog';
import { theme } from '../lib/theme';

/**
 * The observation log.
 *
 * A row shows what the app was willing to say, not what the mushroom was.
 * `summarise` enforces that: for every verdict except `species` it names no
 * species, because a name on a glanceable row read weeks later is the answer
 * whatever sits around it.
 *
 * Everything else -- the candidates, any hazard on them, the warnings shown
 * at the time -- is one tap away. Expanding is a deliberate act; scrolling
 * is not.
 */

const TONE_COLOUR: Record<Tone, string> = {
  danger: theme.colour.danger,
  caution: theme.colour.caution,
  confident: theme.colour.confident,
};

/** Back to the API's shape, so the toxicity rules stay in one component. */
function asCandidate(logged: LoggedCandidate): Candidate {
  return {
    species_key: logged.speciesKey,
    scientific_name: logged.scientificName,
    common_names: logged.commonName ? [logged.commonName] : [],
    confidence: logged.confidence,
    toxicity: logged.toxicity,
    genus: logged.scientificName.split(' ')[0] ?? '',
  };
}

export function HistoryScreen({ navigation }: { navigation: any }) {
  const [entries, setEntries] = useState<Observation[] | null>(null);
  const [current, setCurrent] = useState<{
    modelVersion: string;
    calibrated: boolean;
  } | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const reload = useCallback(() => {
    readLog().then(setEntries);
    // Without this the drift caveat cannot be asserted either way, and
    // `caveats` leaves it unsaid rather than guessing. A history that works
    // offline matters more than one that always knows the model version.
    getHealth()
      .then((health) =>
        setCurrent({
          modelVersion: health.model_version,
          calibrated: health.calibrated,
        }),
      )
      .catch(() => setCurrent(null));
  }, []);

  useFocusEffect(reload);

  const confirmThen = useCallback(
    (title: string, message: string, verb: string, action: () => Promise<unknown>) => {
      Alert.alert(title, message, [
        { text: 'Cancel', style: 'cancel' },
        {
          text: verb,
          style: 'destructive',
          onPress: () => {
            action().then(reload);
          },
        },
      ]);
    },
    [reload],
  );

  if (entries === null) {
    return (
      <View style={styles.screen}>
        <Text style={styles.empty}>Reading your log…</Text>
      </View>
    );
  }

  if (entries.length === 0) {
    return (
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        <Text style={styles.emptyHeading}>Nothing logged yet</Text>
        <Text style={styles.empty}>
          Every identification is saved here — including the ones where I
          couldn't tell you anything, which are the ones worth coming back to.
        </Text>
        <Text style={styles.empty}>
          The log stays on this phone. Nothing here is uploaded.
        </Text>
        <Pressable style={styles.primary} onPress={() => navigation.navigate('Capture')}>
          <Text style={styles.primaryText}>Photograph something</Text>
        </Pressable>
      </ScrollView>
    );
  }

  const withPlaces = entries.filter((e) => e.place).length;

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.count}>
        {entries.length} observation{entries.length === 1 ? '' : 's'} · stored on this
        phone only
      </Text>

      {entries.map((entry) => {
        const summary = summarise(entry);
        const uri = photoUri(entry);
        const isOpen = expanded === entry.observationId;
        const said = caveats(entry, current);

        return (
          <View key={entry.observationId} style={styles.card}>
            <Pressable
              onPress={() => setExpanded(isOpen ? null : entry.observationId)}
              style={styles.row}
              accessibilityRole="button"
              accessibilityLabel={`${summary.line}. ${recencyLabel(entry.recordedAt)}.`}
            >
              {uri ? (
                <Image source={{ uri }} style={styles.thumb} />
              ) : (
                // The OS evicts camera cache files. The record outlives the
                // photograph, and losing one must not hide the other.
                <View style={[styles.thumb, styles.thumbGone]}>
                  <Text style={styles.thumbGoneText}>photo{'\n'}gone</Text>
                </View>
              )}

              <View style={styles.rowBody}>
                <Text style={styles.when}>{recencyLabel(entry.recordedAt)}</Text>
                <Text style={[styles.summary, { color: TONE_COLOUR[summary.tone] }]}>
                  {summary.line}
                </Text>
                {said.length > 0 ? (
                  <Text style={styles.caveatFlag}>
                    {said.length} thing{said.length === 1 ? '' : 's'} to know about this
                    record
                  </Text>
                ) : null}
              </View>

              <Text style={styles.chevron}>{isOpen ? '×' : '›'}</Text>
            </Pressable>

            {isOpen ? (
              <View style={styles.detail}>
                {said.map((caveat) => (
                  <Text key={caveat} style={styles.caveat}>
                    {caveat}
                  </Text>
                ))}

                <Text style={styles.headline}>{entry.headline}</Text>
                {entry.detail ? <Text style={styles.detailText}>{entry.detail}</Text> : null}

                {entry.candidates.length > 0 ? (
                  <View style={styles.section}>
                    <Text style={styles.sectionHeading}>POSSIBILITIES AT THE TIME</Text>
                    {entry.candidates.map((candidate) => (
                      <CandidateRow
                        key={candidate.speciesKey || candidate.scientificName}
                        candidate={asCandidate(candidate)}
                      />
                    ))}
                  </View>
                ) : null}

                <Answered
                  heading="WHAT YOU RECORDED"
                  values={{ ...entry.fieldNotes, ...entry.answers }}
                />

                {entry.place ? (
                  <Text style={styles.place}>
                    {entry.place.latitude.toFixed(4)}, {entry.place.longitude.toFixed(4)}
                  </Text>
                ) : null}

                {entry.warnings.map((warning) => (
                  <Text key={warning} style={styles.warning}>
                    {warning}
                  </Text>
                ))}

                <Pressable
                  onPress={() =>
                    navigation.navigate('Report', {
                      observationId: entry.observationId,
                      verdict: entry.verdict,
                      // Keys, not names: the server grades a report by
                      // looking these up. Entries logged before the key was
                      // stored contribute nothing rather than nonsense.
                      candidates: entry.candidates
                        .map((c) => c.speciesKey)
                        .filter(Boolean),
                      modelVersion: entry.modelVersion,
                      calibrated: entry.calibrated,
                    })
                  }
                  style={styles.destructive}
                  accessibilityRole="button"
                >
                  <Text style={styles.reportText}>This one was wrong</Text>
                </Pressable>

                <Pressable
                  onPress={() =>
                    confirmThen(
                      'Delete this observation?',
                      'The photographs stay in your camera roll. The record goes.',
                      'Delete',
                      () => forget(entry.observationId),
                    )
                  }
                  style={styles.destructive}
                  accessibilityRole="button"
                >
                  <Text style={styles.destructiveText}>Delete this observation</Text>
                </Pressable>
              </View>
            ) : null}
          </View>
        );
      })}

      <View style={styles.controls}>
        {withPlaces > 0 ? (
          <Pressable
            onPress={() =>
              confirmThen(
                'Forget where you were?',
                `${withPlaces} observation${withPlaces === 1 ? '' : 's'} will keep everything except the location.`,
                'Forget locations',
                forgetPlaces,
              )
            }
            style={styles.destructive}
            accessibilityRole="button"
          >
            <Text style={styles.destructiveText}>Forget locations ({withPlaces})</Text>
          </Pressable>
        ) : null}

        <Pressable
          onPress={() =>
            confirmThen(
              'Delete the whole log?',
              'Every observation, permanently. Your photographs are not touched.',
              'Delete everything',
              forgetAll,
            )
          }
          style={styles.destructive}
          accessibilityRole="button"
        >
          <Text style={styles.destructiveText}>Delete the whole log</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

function Answered({ heading, values }: { heading: string; values: Record<string, string> }) {
  const pairs = Object.entries(values);
  if (pairs.length === 0) return null;
  return (
    <View style={styles.section}>
      <Text style={styles.sectionHeading}>{heading}</Text>
      {pairs.map(([key, value]) => (
        <Text key={key} style={styles.answer}>
          {key.replace(/_/g, ' ')}: {value}
        </Text>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.colour.background },
  content: { padding: theme.spacing(2), gap: theme.spacing(1.5) },

  count: {
    fontSize: theme.font.tiny,
    color: theme.colour.textFaint,
    letterSpacing: 0.5,
  },
  emptyHeading: {
    fontSize: theme.font.heading,
    fontWeight: '800',
    color: theme.colour.text,
    marginTop: theme.spacing(4),
  },
  empty: {
    fontSize: theme.font.small,
    color: theme.colour.textMuted,
    lineHeight: 21,
    padding: theme.spacing(2),
    paddingHorizontal: 0,
  },

  card: {
    backgroundColor: theme.colour.surface,
    borderRadius: theme.radius.md,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.spacing(1.5),
    padding: theme.spacing(1.25),
  },
  thumb: {
    width: 58,
    height: 58,
    borderRadius: theme.radius.sm,
    backgroundColor: theme.colour.surfaceRaised,
  },
  thumbGone: { alignItems: 'center', justifyContent: 'center' },
  thumbGoneText: {
    fontSize: 10,
    color: theme.colour.textFaint,
    textAlign: 'center',
  },
  rowBody: { flex: 1, gap: 3 },
  when: { fontSize: theme.font.tiny, color: theme.colour.textFaint },
  summary: { fontSize: theme.font.small, fontWeight: '700', lineHeight: 19 },
  caveatFlag: { fontSize: theme.font.tiny, color: theme.colour.caution },
  chevron: {
    fontSize: theme.font.heading,
    color: theme.colour.textFaint,
    paddingHorizontal: theme.spacing(1),
  },

  detail: {
    gap: theme.spacing(1.5),
    padding: theme.spacing(2),
    paddingTop: 0,
    borderTopWidth: 1,
    borderTopColor: theme.colour.border,
    marginTop: theme.spacing(0.5),
    paddingBottom: theme.spacing(2),
  },
  caveat: {
    fontSize: theme.font.small,
    color: theme.colour.caution,
    backgroundColor: theme.colour.cautionSurface,
    borderRadius: theme.radius.sm,
    padding: theme.spacing(1.25),
    lineHeight: 20,
  },
  headline: {
    fontSize: theme.font.body,
    fontWeight: '700',
    color: theme.colour.text,
    marginTop: theme.spacing(1.5),
  },
  detailText: { fontSize: theme.font.small, color: theme.colour.textMuted, lineHeight: 21 },

  section: { gap: theme.spacing(1) },
  sectionHeading: {
    fontSize: theme.font.tiny,
    fontWeight: '800',
    letterSpacing: 0.9,
    color: theme.colour.textFaint,
  },
  answer: { fontSize: theme.font.small, color: theme.colour.textMuted },
  place: { fontSize: theme.font.tiny, color: theme.colour.textFaint },
  warning: { fontSize: theme.font.small, color: theme.colour.textMuted, lineHeight: 21 },

  controls: { gap: theme.spacing(1), marginTop: theme.spacing(2) },
  destructive: {
    borderWidth: 1,
    borderColor: theme.colour.border,
    borderRadius: theme.radius.md,
    padding: theme.spacing(1.5),
    alignItems: 'center',
  },
  destructiveText: { fontSize: theme.font.small, color: theme.colour.danger, fontWeight: '600' },
  reportText: { fontSize: theme.font.small, color: theme.colour.textMuted, fontWeight: '600' },

  primary: {
    backgroundColor: theme.colour.accent,
    borderRadius: theme.radius.md,
    padding: theme.spacing(2),
    alignItems: 'center',
    marginTop: theme.spacing(2),
  },
  primaryText: { fontSize: theme.font.body, fontWeight: '700', color: theme.colour.background },
});
