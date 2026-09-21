import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import {
  getSpeciesList,
  reportIncident,
  type SpeciesListEntry,
} from '../lib/api';
import { EMERGENCY_STEPS } from '../lib/emergency';
import { theme } from '../lib/theme';

/**
 * Report that the app was wrong.
 *
 * An app that tells people it might be wrong owes them somewhere to say that
 * it was. Two things about this screen are load-bearing.
 *
 * **The two questions about eating come first, and answering yes stops the
 * form.** If someone ate it, or anyone is unwell, this is not a bug report
 * and must not behave like one: the screen turns into the emergency guidance
 * before anything is submitted. The check happens here rather than only on
 * the server's reply, because the network is exactly what fails in a wood.
 * The report can still be sent afterwards, from underneath the guidance.
 *
 * **The species picker covers the whole label space, not just the candidates
 * the app offered.** The failure most worth hearing about is the app missing
 * something dangerous, and the species it missed is by definition not among
 * the ones it named.
 */
export function ReportScreen({ navigation, route }: { navigation: any; route: any }) {
  const context = (route.params ?? {}) as {
    observationId?: string;
    verdict?: string;
    candidates?: string[];
    modelVersion?: string;
    calibrated?: boolean;
  };

  const [ate, setAte] = useState<boolean | null>(null);
  const [unwell, setUnwell] = useState<boolean | null>(null);
  const [believed, setBelieved] = useState<SpeciesListEntry | null>(null);
  const [query, setQuery] = useState('');
  const [account, setAccount] = useState('');
  const [contact, setContact] = useState('');
  const [species, setSpecies] = useState<SpeciesListEntry[]>([]);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSpeciesList()
      .then(setSpecies)
      .catch(() => setSpecies([]));
  }, []);

  const medical = ate === true || unwell === true;

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return [];
    return species
      .filter(
        (s) =>
          s.scientific_name.toLowerCase().includes(needle) ||
          s.common_names.some((n) => n.toLowerCase().includes(needle)),
      )
      .slice(0, 8);
  }, [query, species]);

  const submit = useCallback(async () => {
    setSending(true);
    setError(null);
    try {
      const receipt = await reportIncident({
        observation_id: context.observationId ?? null,
        verdict: context.verdict ?? null,
        reported_candidates: context.candidates ?? [],
        model_version: context.modelVersion ?? null,
        calibrated: context.calibrated ?? null,
        believed_species_key: believed?.species_key ?? null,
        account: account.slice(0, 4000),
        anyone_ate_it: ate === true,
        anyone_unwell: unwell === true,
        contact: contact.trim() || null,
      });
      setSent(receipt.acknowledgement);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not send that.');
    } finally {
      setSending(false);
    }
  }, [account, ate, believed, contact, context, unwell]);

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.intro}>
        Telling me I got this wrong is the most useful thing you can do with
        this app. A person reads these; nothing is changed automatically.
      </Text>

      <Question
        label="Has anyone eaten any of it?"
        value={ate}
        onChange={setAte}
      />
      <Question
        label="Is anyone unwell?"
        value={unwell}
        onChange={setUnwell}
      />

      {medical ? (
        // Before the form, before the network, before anything is sent.
        <View style={styles.emergency}>
          <Text style={styles.emergencyHeading}>Stop and deal with this first</Text>
          {EMERGENCY_STEPS.map((step) => (
            <View key={step.heading} style={styles.emergencyStep}>
              <Text style={styles.emergencyStepHeading}>{step.heading}</Text>
              <Text style={styles.emergencyStepBody}>{step.body}</Text>
            </View>
          ))}
          <Pressable
            style={styles.emergencyButton}
            onPress={() => navigation.navigate('Emergency')}
            accessibilityRole="button"
          >
            <Text style={styles.emergencyButtonText}>Open the emergency page</Text>
          </Pressable>
        </View>
      ) : null}

      <View style={styles.section}>
        <Text style={styles.sectionHeading}>WHAT DO YOU THINK IT ACTUALLY WAS?</Text>
        <Text style={styles.hint}>
          Optional, and a guess is fine. It tells me which two species were
          confused, which is the part I can act on.
        </Text>

        {believed ? (
          <Pressable
            style={styles.chosen}
            onPress={() => {
              setBelieved(null);
              setQuery('');
            }}
            accessibilityRole="button"
          >
            <Text style={styles.chosenName}>{believed.scientific_name}</Text>
            <Text style={styles.chosenClear}>change</Text>
          </Pressable>
        ) : (
          <>
            <TextInput
              style={styles.input}
              value={query}
              onChangeText={setQuery}
              placeholder="Start typing a name"
              placeholderTextColor={theme.colour.textFaint}
              autoCapitalize="none"
              autoCorrect={false}
            />
            {matches.map((match) => (
              <Pressable
                key={match.species_key}
                style={styles.match}
                onPress={() => setBelieved(match)}
                accessibilityRole="button"
              >
                <Text style={styles.matchScientific}>{match.scientific_name}</Text>
                {match.common_names.length > 0 ? (
                  <Text style={styles.matchCommon}>{match.common_names.join(' · ')}</Text>
                ) : null}
              </Pressable>
            ))}
            {query.trim() && matches.length === 0 ? (
              <Text style={styles.hint}>
                Nothing matching. This app only knows {species.length} species, so
                it may not be one it could ever have named — say so below.
              </Text>
            ) : null}
          </>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionHeading}>WHAT HAPPENED</Text>
        <TextInput
          style={[styles.input, styles.multiline]}
          value={account}
          onChangeText={setAccount}
          multiline
          maxLength={4000}
          placeholder="What it said, what you saw, and what made you think otherwise."
          placeholderTextColor={theme.colour.textFaint}
        />
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionHeading}>HOW TO REACH YOU — OPTIONAL</Text>
        <Text style={styles.hint}>
          Only if you are happy to be asked a follow-up. Leave it blank
          otherwise; the report is just as useful.
        </Text>
        <TextInput
          style={styles.input}
          value={contact}
          onChangeText={setContact}
          maxLength={200}
          autoCapitalize="none"
          keyboardType="email-address"
          placeholder="Email address"
          placeholderTextColor={theme.colour.textFaint}
        />
      </View>

      {sent ? (
        <Text style={styles.sent}>{sent}</Text>
      ) : (
        <Pressable
          style={styles.primary}
          onPress={submit}
          disabled={sending}
          accessibilityRole="button"
        >
          {sending ? (
            <ActivityIndicator color={theme.colour.background} />
          ) : (
            <Text style={styles.primaryText}>Send the report</Text>
          )}
        </Pressable>
      )}

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Text style={styles.footnote}>
        Sent: what the app said, what you have written here, and nothing else.
        No photographs — storing those needs answers this project has not got
        yet.
      </Text>
    </ScrollView>
  );
}

function Question({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean | null;
  onChange: (v: boolean) => void;
}) {
  return (
    <View style={styles.question}>
      <Text style={styles.questionLabel}>{label}</Text>
      <View style={styles.answers}>
        {[
          { text: 'No', v: false },
          { text: 'Yes', v: true },
        ].map((option) => (
          <Pressable
            key={option.text}
            onPress={() => onChange(option.v)}
            style={[
              styles.answer,
              value === option.v && (option.v ? styles.answerYes : styles.answerOn),
            ]}
            accessibilityRole="button"
            accessibilityState={{ selected: value === option.v }}
          >
            <Text
              style={[
                styles.answerText,
                value === option.v && styles.answerTextOn,
              ]}
            >
              {option.text}
            </Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.colour.background },
  content: { padding: theme.spacing(2), gap: theme.spacing(2.5) },
  intro: { fontSize: theme.font.small, color: theme.colour.textMuted, lineHeight: 21 },

  question: { gap: theme.spacing(1) },
  questionLabel: { fontSize: theme.font.body, fontWeight: '700', color: theme.colour.text },
  answers: { flexDirection: 'row', gap: theme.spacing(1) },
  answer: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: theme.spacing(1.25),
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colour.border,
    backgroundColor: theme.colour.surface,
  },
  answerOn: { borderColor: theme.colour.accent, backgroundColor: theme.colour.surfaceRaised },
  answerYes: { borderColor: theme.colour.danger, backgroundColor: theme.colour.dangerSurface },
  answerText: { fontSize: theme.font.small, color: theme.colour.textMuted, fontWeight: '600' },
  answerTextOn: { color: theme.colour.text },

  emergency: {
    gap: theme.spacing(1.5),
    backgroundColor: theme.colour.dangerSurface,
    borderWidth: 1,
    borderColor: theme.colour.danger,
    borderRadius: theme.radius.md,
    padding: theme.spacing(2),
  },
  emergencyHeading: { fontSize: theme.font.heading, fontWeight: '800', color: theme.colour.text },
  emergencyStep: { gap: 2 },
  emergencyStepHeading: {
    fontSize: theme.font.small,
    fontWeight: '700',
    color: theme.colour.text,
  },
  emergencyStepBody: {
    fontSize: theme.font.small,
    color: theme.colour.textMuted,
    lineHeight: 21,
  },
  emergencyButton: {
    backgroundColor: theme.colour.danger,
    borderRadius: theme.radius.md,
    padding: theme.spacing(1.5),
    alignItems: 'center',
  },
  emergencyButtonText: { fontSize: theme.font.body, fontWeight: '800', color: '#fff' },

  section: { gap: theme.spacing(1) },
  sectionHeading: {
    fontSize: theme.font.tiny,
    fontWeight: '800',
    letterSpacing: 0.9,
    color: theme.colour.textFaint,
  },
  hint: { fontSize: theme.font.small, color: theme.colour.textMuted, lineHeight: 20 },
  input: {
    backgroundColor: theme.colour.surface,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colour.border,
    padding: theme.spacing(1.5),
    color: theme.colour.text,
    fontSize: theme.font.small,
  },
  multiline: { minHeight: 120, textAlignVertical: 'top' },
  match: {
    backgroundColor: theme.colour.surface,
    borderRadius: theme.radius.sm,
    padding: theme.spacing(1.25),
  },
  matchScientific: {
    fontSize: theme.font.small,
    fontStyle: 'italic',
    color: theme.colour.text,
  },
  matchCommon: { fontSize: theme.font.tiny, color: theme.colour.textMuted },
  chosen: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: theme.colour.surfaceRaised,
    borderRadius: theme.radius.md,
    padding: theme.spacing(1.5),
  },
  chosenName: { fontSize: theme.font.small, fontStyle: 'italic', color: theme.colour.text },
  chosenClear: { fontSize: theme.font.tiny, color: theme.colour.accent },

  primary: {
    backgroundColor: theme.colour.accent,
    borderRadius: theme.radius.md,
    padding: theme.spacing(2),
    alignItems: 'center',
  },
  primaryText: { fontSize: theme.font.body, fontWeight: '700', color: theme.colour.background },
  sent: {
    fontSize: theme.font.small,
    color: theme.colour.confident,
    textAlign: 'center',
    lineHeight: 21,
  },
  error: { fontSize: theme.font.small, color: theme.colour.danger },
  footnote: { fontSize: theme.font.tiny, color: theme.colour.textFaint, lineHeight: 18 },
});
