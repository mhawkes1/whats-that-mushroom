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

import { getDisclaimer, type Disclaimer } from '../lib/api';
import { isComplete, outstanding, recordConsent } from '../lib/consent';
import { theme } from '../lib/theme';

/**
 * What a user acknowledges before first use.
 *
 * Three things about the shape of this screen are deliberate.
 *
 * The statements are fetched, not written here, so one copy of them exists
 * and so they can depend on what the service currently is -- while there is
 * no trained model, no fitted calibration and no reviewed taxonomy, each of
 * those is stated here rather than in a settings screen nobody opens.
 *
 * Each statement is ticked on its own and there is no "accept all". The
 * button says how many are left rather than sitting greyed out, because a
 * disabled control with no explanation is a puzzle and this is not the place
 * for one.
 *
 * The emergency link is on this screen, above the gate. Someone opening the
 * app because a child has eaten something in the garden is not going to work
 * through an onboarding flow first.
 */
export function ConsentScreen({ navigation }: { navigation: any }) {
  const [disclaimer, setDisclaimer] = useState<Disclaimer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ticked, setTicked] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setError(null);
    getDisclaimer()
      .then(setDisclaimer)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : 'Could not load this.'),
      );
  }, []);

  useEffect(load, [load]);

  const accept = useCallback(async () => {
    if (!disclaimer) return;
    setSaving(true);
    const saved = await recordConsent(
      disclaimer.version,
      disclaimer.acknowledgements.map((a) => a.key),
    );
    setSaving(false);
    if (!saved) {
      // Proceeding on a consent that was never written would leave no record
      // that the disclaimer was shown, which is the thing being asked for.
      Alert.alert(
        'Could not save that',
        'This phone would not store your acknowledgement, so I would have to ask again next time. Try once more.',
      );
      return;
    }
    navigation.reset({ index: 0, routes: [{ name: 'Capture' }] });
  }, [disclaimer, navigation]);

  const emergency = (
    <Pressable
      style={styles.emergency}
      onPress={() => navigation.navigate('Emergency')}
      accessibilityRole="button"
    >
      <Text style={styles.emergencyText}>
        Someone has eaten a wild mushroom — what to do
      </Text>
    </Pressable>
  );

  if (error) {
    return (
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        {emergency}
        <Text style={styles.heading}>Can't reach the service</Text>
        <Text style={styles.body}>
          The things you need to know before using this app are kept in one
          place, on the server, so they can't drift out of step with what the
          app actually does. I can't read them right now.
        </Text>
        <Text style={styles.errorText}>{error}</Text>
        <Pressable style={styles.primary} onPress={load} accessibilityRole="button">
          <Text style={styles.primaryText}>Try again</Text>
        </Pressable>
      </ScrollView>
    );
  }

  if (!disclaimer) {
    return (
      <View style={[styles.screen, styles.centred]}>
        <ActivityIndicator color={theme.colour.accent} />
      </View>
    );
  }

  const left = outstanding(ticked, disclaimer.acknowledgements);
  const ready = isComplete(ticked, disclaimer.acknowledgements);

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      {emergency}

      <Text style={styles.heading}>{disclaimer.heading}</Text>
      <Text style={styles.body}>{disclaimer.body}</Text>

      <View style={styles.acks}>
        {disclaimer.acknowledgements.map((ack) => {
          const on = ticked[ack.key] === true;
          return (
            <Pressable
              key={ack.key}
              onPress={() => setTicked((c) => ({ ...c, [ack.key]: !on }))}
              style={[styles.ack, on && styles.ackOn]}
              accessibilityRole="checkbox"
              accessibilityState={{ checked: on }}
              accessibilityLabel={ack.statement}
            >
              <View style={[styles.box, on && styles.boxOn]}>
                {on ? <Text style={styles.tick}>✓</Text> : null}
              </View>
              <View style={styles.ackBody}>
                <Text style={styles.statement}>{ack.statement}</Text>
                <Text style={styles.because}>{ack.because}</Text>
              </View>
            </Pressable>
          );
        })}
      </View>

      <Pressable
        style={[styles.primary, !ready && styles.primaryWaiting]}
        onPress={accept}
        disabled={!ready || saving}
        accessibilityRole="button"
      >
        <Text style={[styles.primaryText, !ready && styles.primaryWaitingText]}>
          {ready
            ? 'I understand — continue'
            : `${left} more to acknowledge`}
        </Text>
      </Pressable>

      <Text style={styles.footnote}>
        Kept on this phone. There is no account and nothing is uploaded.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.colour.background },
  centred: { alignItems: 'center', justifyContent: 'center' },
  content: { padding: theme.spacing(2.5), gap: theme.spacing(2) },

  emergency: {
    backgroundColor: theme.colour.dangerSurface,
    borderWidth: 1,
    borderColor: theme.colour.danger,
    borderRadius: theme.radius.md,
    padding: theme.spacing(1.5),
  },
  emergencyText: {
    fontSize: theme.font.small,
    fontWeight: '700',
    color: theme.colour.danger,
    textAlign: 'center',
  },

  heading: { fontSize: theme.font.title, fontWeight: '800', color: theme.colour.text },
  body: { fontSize: theme.font.body, color: theme.colour.textMuted, lineHeight: 24 },
  errorText: { fontSize: theme.font.small, color: theme.colour.caution },

  acks: { gap: theme.spacing(1.25) },
  ack: {
    flexDirection: 'row',
    gap: theme.spacing(1.5),
    backgroundColor: theme.colour.surface,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colour.border,
    padding: theme.spacing(1.75),
  },
  ackOn: { borderColor: theme.colour.accent },
  box: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: theme.colour.textFaint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  boxOn: { borderColor: theme.colour.accent, backgroundColor: theme.colour.accent },
  tick: { color: theme.colour.background, fontSize: 15, fontWeight: '900' },
  ackBody: { flex: 1, gap: theme.spacing(0.75) },
  statement: {
    fontSize: theme.font.small,
    fontWeight: '700',
    color: theme.colour.text,
    lineHeight: 20,
  },
  because: { fontSize: theme.font.small, color: theme.colour.textMuted, lineHeight: 20 },

  primary: {
    backgroundColor: theme.colour.accent,
    borderRadius: theme.radius.md,
    padding: theme.spacing(2),
    alignItems: 'center',
  },
  primaryWaiting: { backgroundColor: theme.colour.surfaceRaised },
  primaryText: { fontSize: theme.font.body, fontWeight: '700', color: theme.colour.background },
  primaryWaitingText: { color: theme.colour.textFaint },
  footnote: { fontSize: theme.font.tiny, color: theme.colour.textFaint, textAlign: 'center' },
});
