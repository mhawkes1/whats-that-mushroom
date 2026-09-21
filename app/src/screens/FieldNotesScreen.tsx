import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import * as Location from 'expo-location';

import {
  getFieldForm,
  identify,
  type FieldContext,
  type FieldForm,
  type FieldNotes,
  type Views,
} from '../lib/api';
import { theme } from '../lib/theme';

/**
 * Field notes.
 *
 * Everything a person can answer by looking, asked once, on one screen,
 * instead of one question at a time after the fact. The interrogation engine
 * still runs afterwards -- but it is then spending its questions on what is
 * genuinely still ambiguous, rather than on things the user could have told
 * us before they left the wood.
 *
 * Two rules shape this screen:
 *
 * 1. Every field is skippable, and skipping is offered as prominently as
 *    answering. A guess recorded as an observation is worse than a blank,
 *    because nothing downstream can tell the two apart.
 * 2. The fields and their options come from `/field-form`. Hardcoding them
 *    here would let the client drift from the character catalogue the server
 *    validates against.
 */
export function FieldNotesScreen({ navigation, route }: { navigation: any; route: any }) {
  const { views } = route.params as { views: Views };

  const [form, setForm] = useState<FieldForm | null>(null);
  const [notes, setNotes] = useState<FieldNotes>({});
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    getFieldForm()
      .then(setForm)
      .catch((error: unknown) =>
        setLoadError(error instanceof Error ? error.message : 'Could not load the form.'),
      );
  }, []);

  const collectContext = useCallback(async (): Promise<FieldContext> => {
    const context: FieldContext = { month: new Date().getMonth() + 1 };
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status === 'granted') {
        const position = await Location.getCurrentPositionAsync({
          accuracy: Location.Accuracy.Balanced,
        });
        context.latitude = position.coords.latitude;
        context.longitude = position.coords.longitude;
      }
    } catch {
      // Location is a bonus, never a blocker.
    }
    return context;
  }, []);

  const submit = useCallback(async () => {
    setBusy(true);
    try {
      const context = await collectContext();
      const result = await identify(views, context, notes);
      navigation.navigate('Result', { result, imageUri: views.top });
    } catch (error) {
      Alert.alert(
        'Could not identify',
        error instanceof Error ? error.message : 'Something went wrong.',
      );
    } finally {
      setBusy(false);
    }
  }, [collectContext, navigation, notes, views]);

  const toggle = useCallback((key: string, option: string) => {
    setNotes((current) => {
      const next = { ...current };
      // Tapping the chosen option again clears it, so a mis-tap is
      // recoverable without a separate "clear" control.
      if (next[key] === option) delete next[key];
      else next[key] = option;
      return next;
    });
  }, []);

  const answered = Object.keys(notes).length;

  if (loadError) {
    return (
      <View style={[styles.screen, styles.centred]}>
        <Text style={styles.error}>{loadError}</Text>
        <Pressable style={styles.secondary} onPress={submit}>
          <Text style={styles.secondaryText}>Identify from the photos alone</Text>
        </Pressable>
      </View>
    );
  }

  if (!form) {
    return (
      <View style={[styles.screen, styles.centred]}>
        <ActivityIndicator color={theme.colour.accent} />
      </View>
    );
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.intro}>{form.note}</Text>

      {form.fields.map((field) => (
        <View key={field.key} style={styles.field}>
          <View style={styles.fieldHeader}>
            <Text style={styles.fieldLabel}>{field.label.toUpperCase()}</Text>
            {field.effort === 'hours' ? (
              <Text style={styles.effort}>only if you already have one</Text>
            ) : null}
          </View>
          <Text style={styles.prompt}>{field.prompt}</Text>

          <View style={styles.options}>
            {field.options.map((option) => {
              const chosen = notes[field.key] === option;
              return (
                <Pressable
                  key={option}
                  onPress={() => toggle(field.key, option)}
                  style={[styles.chip, chosen && styles.chipChosen]}
                  accessibilityRole="button"
                  accessibilityState={{ selected: chosen }}
                >
                  <Text style={[styles.chipText, chosen && styles.chipTextChosen]}>
                    {option}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          {notes[field.key] ? (
            <Text style={styles.clearHint}>Tap again to unset</Text>
          ) : (
            <Text style={styles.skipHint}>Leave blank if you're not sure</Text>
          )}
        </View>
      ))}

      {busy ? (
        <View style={styles.busy}>
          <ActivityIndicator color={theme.colour.accent} />
          <Text style={styles.busyText}>Looking…</Text>
        </View>
      ) : (
        <View style={styles.actions}>
          <Pressable style={styles.primary} onPress={submit}>
            <Text style={styles.primaryText}>
              {answered > 0
                ? `Identify — with ${answered} note${answered === 1 ? '' : 's'}`
                : 'Identify'}
            </Text>
          </Pressable>
          {answered > 0 ? null : (
            <Text style={styles.skipAll}>
              You can skip all of this. It only ever narrows things down.
            </Text>
          )}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.colour.background },
  centred: { alignItems: 'center', justifyContent: 'center', gap: theme.spacing(2) },
  content: { padding: theme.spacing(2.5), gap: theme.spacing(3) },
  intro: {
    fontSize: theme.font.small,
    color: theme.colour.textMuted,
    lineHeight: 21,
  },
  field: { gap: theme.spacing(1) },
  fieldHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  fieldLabel: {
    fontSize: theme.font.tiny,
    fontWeight: '800',
    letterSpacing: 0.8,
    color: theme.colour.accent,
  },
  effort: { fontSize: theme.font.tiny, color: theme.colour.textFaint },
  prompt: { fontSize: theme.font.body, color: theme.colour.text, lineHeight: 22 },
  options: { flexDirection: 'row', flexWrap: 'wrap', gap: theme.spacing(1) },
  chip: {
    backgroundColor: theme.colour.surface,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colour.border,
    paddingVertical: theme.spacing(1.25),
    paddingHorizontal: theme.spacing(1.75),
  },
  chipChosen: { backgroundColor: theme.colour.accent, borderColor: theme.colour.accent },
  chipText: { fontSize: theme.font.small, color: theme.colour.text },
  chipTextChosen: { color: theme.colour.background, fontWeight: '700' },
  skipHint: { fontSize: theme.font.tiny, color: theme.colour.textFaint },
  clearHint: { fontSize: theme.font.tiny, color: theme.colour.textFaint },
  actions: { gap: theme.spacing(1.25) },
  primary: {
    backgroundColor: theme.colour.accent,
    borderRadius: theme.radius.lg,
    paddingVertical: theme.spacing(2.25),
    alignItems: 'center',
  },
  primaryText: {
    fontSize: theme.font.heading,
    fontWeight: '700',
    color: theme.colour.background,
  },
  secondary: {
    backgroundColor: theme.colour.surfaceRaised,
    borderRadius: theme.radius.lg,
    paddingVertical: theme.spacing(2),
    paddingHorizontal: theme.spacing(3),
    alignItems: 'center',
  },
  secondaryText: { fontSize: theme.font.body, color: theme.colour.text },
  skipAll: {
    fontSize: theme.font.tiny,
    color: theme.colour.textFaint,
    textAlign: 'center',
  },
  error: {
    fontSize: theme.font.small,
    color: theme.colour.caution,
    textAlign: 'center',
    paddingHorizontal: theme.spacing(3),
  },
  busy: { alignItems: 'center', gap: theme.spacing(1), paddingVertical: theme.spacing(3) },
  busyText: { color: theme.colour.textMuted, fontSize: theme.font.small },
});
