import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';

import {
  matchSporePrint,
  type Region,
  type SporePrintReading,
} from '../lib/api';
import {
  clearTimer,
  readTimer,
  startTimer,
  waitStatus,
  type WaitStatus,
} from '../lib/sporePrintTimer';
import { theme } from '../lib/theme';

/**
 * The guided spore print.
 *
 * Spore print colour is the most decisive test available without a
 * microscope, and it is what the interrogation engine asks for when a lethal
 * ambiguity turns on it. Until now the app asked for one and then left the
 * user to judge dust on paper by eye, hours later, under whatever light their
 * kitchen has.
 *
 * Four steps: how to set one up, a timer that outlives the app being closed,
 * a guided photograph against the half-white card, and a colour match the
 * user confirms.
 *
 * The match is never submitted automatically. The server declines to assert a
 * colour whenever the card is unusable or two chart entries are too close to
 * call, and even a confident reading is presented as a suggestion beside the
 * manual list. Spore print colour is what separates an Amanita from a young
 * Agaricus, so the app proposes and the person decides.
 */

type Phase = 'setup' | 'waiting' | 'reading';

// Where the two patches are sampled from. Fixed rather than draggable: the
// screen shows the user exactly these boxes over their photograph before
// anything is read, so a misaligned card is visible rather than silent.
const DEPOSIT_REGION: Region = { x: 0.08, y: 0.3, width: 0.32, height: 0.4 };
const CARD_REGION: Region = { x: 0.6, y: 0.3, width: 0.32, height: 0.4 };

export function SporePrintScreen({ navigation, route }: { navigation: any; route: any }) {
  const { observationId, onMatched } = route.params as {
    observationId: string;
    onMatched?: (option: string) => void;
  };

  const [phase, setPhase] = useState<Phase>('setup');
  const [status, setStatus] = useState<WaitStatus | null>(null);
  const [photo, setPhoto] = useState<string | null>(null);
  const [swapped, setSwapped] = useState(false);
  const [reading, setReading] = useState<SporePrintReading | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const timer = await readTimer();
    if (!timer) {
      setPhase('setup');
      setStatus(null);
      return;
    }
    setStatus(waitStatus(Date.now() - timer.startedAt));
    setPhase('waiting');
  }, []);

  useEffect(() => {
    refresh();
    // Re-checked on a slow tick rather than a countdown: the wait is measured
    // in hours, and the elapsed time is derived from a stored timestamp so it
    // stays correct across the app being closed entirely.
    const handle = setInterval(refresh, 30 * 1000);
    return () => clearInterval(handle);
  }, [refresh]);

  const begin = useCallback(async () => {
    await startTimer(observationId);
    await refresh();
  }, [observationId, refresh]);

  const abandon = useCallback(async () => {
    await clearTimer();
    setPhoto(null);
    setReading(null);
    await refresh();
  }, [refresh]);

  const capture = useCallback(async () => {
    const { status: permission } = await ImagePicker.requestCameraPermissionsAsync();
    if (permission !== 'granted') {
      Alert.alert('Camera needed', 'Allow camera access to photograph the print.');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({ quality: 0.9, exif: false });
    if (!result.canceled && result.assets[0]) {
      setPhoto(result.assets[0].uri);
      setReading(null);
      setPhase('reading');
    }
  }, []);

  const read = useCallback(async () => {
    if (!photo) return;
    setBusy(true);
    try {
      const deposit = swapped ? CARD_REGION : DEPOSIT_REGION;
      const card = swapped ? DEPOSIT_REGION : CARD_REGION;
      setReading(await matchSporePrint(photo, deposit, card));
    } catch (error) {
      Alert.alert(
        'Could not read the print',
        error instanceof Error ? error.message : 'Something went wrong.',
      );
    } finally {
      setBusy(false);
    }
  }, [photo, swapped]);

  const accept = useCallback(
    async (option: string) => {
      await clearTimer();
      onMatched?.(option);
      navigation.goBack();
    },
    [navigation, onMatched],
  );

  // --- Setup -----------------------------------------------------------------

  if (phase === 'setup') {
    return (
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        <Text style={styles.heading}>Making a spore print</Text>
        <Text style={styles.body}>
          It takes a few minutes to set up and several hours to develop. It is
          the most decisive test you can do without a microscope.
        </Text>

        <View style={styles.steps}>
          {[
            'Cut the cap off, as close under the cap as you can.',
            'Lay it gills-down on paper that is half white and half black. A sheet of each, side by side, works.',
            'Cover it with a bowl or a glass so draughts cannot disturb it.',
            'Leave it somewhere still for two to twelve hours. Overnight is easiest.',
          ].map((step, index) => (
            <View key={step} style={styles.step}>
              <Text style={styles.stepNumber}>{index + 1}</Text>
              <Text style={styles.stepText}>{step}</Text>
            </View>
          ))}
        </View>

        <View style={styles.why}>
          <Text style={styles.whyText}>
            The half-and-half paper matters twice over: a pale print is
            invisible on white and a dark one is invisible on black, and the
            white half also lets the app correct for the colour of your
            kitchen light when it reads the photograph.
          </Text>
        </View>

        <Pressable style={styles.primary} onPress={begin}>
          <Text style={styles.primaryText}>It's set up — start the timer</Text>
        </Pressable>
        <Text style={styles.footnote}>
          You can close the app. The timer keeps running.
        </Text>
      </ScrollView>
    );
  }

  // --- Waiting ---------------------------------------------------------------

  if (phase === 'waiting') {
    const readiness = status?.readiness ?? 'too-soon';
    const early = readiness === 'too-soon';
    return (
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        <Text style={styles.heading}>Print developing</Text>
        <View
          style={[
            styles.statusCard,
            readiness === 'ready' && styles.statusReady,
            readiness === 'stale' && styles.statusStale,
          ]}
        >
          <Text style={styles.statusText}>{status?.summary}</Text>
        </View>

        <Pressable style={styles.primary} onPress={capture}>
          <Text style={styles.primaryText}>
            {early ? 'Look anyway' : 'Photograph the print'}
          </Text>
        </Pressable>
        {early ? (
          <Text style={styles.footnote}>
            Nothing stops you looking early — just treat a faint colour as
            unreliable rather than as an answer.
          </Text>
        ) : null}

        <Pressable onPress={abandon}>
          <Text style={styles.abandon}>Start over</Text>
        </Pressable>
      </ScrollView>
    );
  }

  // --- Reading ---------------------------------------------------------------

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.heading}>Reading the colour</Text>

      {photo ? (
        <View>
          <Image source={{ uri: photo }} style={styles.photo} />
          {/* The sampled patches, drawn where they will actually be read
              from, so a card photographed the wrong way round is obvious
              before anything is measured rather than after. */}
          <View
            pointerEvents="none"
            style={[styles.patch, styles.depositPatch, regionStyle(swapped ? CARD_REGION : DEPOSIT_REGION)]}
          >
            <Text style={styles.patchLabel}>print</Text>
          </View>
          <View
            pointerEvents="none"
            style={[styles.patch, styles.cardPatch, regionStyle(swapped ? DEPOSIT_REGION : CARD_REGION)]}
          >
            <Text style={styles.patchLabel}>white card</Text>
          </View>
        </View>
      ) : null}

      <Text style={styles.body}>
        The two boxes are where the colour is read from. The print must be in
        one and the plain white card in the other.
      </Text>

      <View style={styles.row}>
        <Pressable style={styles.secondary} onPress={() => setSwapped((s) => !s)}>
          <Text style={styles.secondaryText}>Swap boxes</Text>
        </Pressable>
        <Pressable style={styles.secondary} onPress={capture}>
          <Text style={styles.secondaryText}>Retake</Text>
        </Pressable>
      </View>

      {busy ? (
        <ActivityIndicator color={theme.colour.accent} />
      ) : (
        <Pressable style={styles.primary} onPress={read}>
          <Text style={styles.primaryText}>Read the colour</Text>
        </Pressable>
      )}

      {reading ? (
        <View style={styles.section}>
          <View
            style={[
              styles.readingCard,
              !reading.confident && styles.readingUnsure,
            ]}
          >
            <Text style={styles.readingReason}>{reading.reason}</Text>
          </View>

          <Text style={styles.sectionHeading}>
            {reading.confident ? 'SUGGESTED — CHECK IT YOURSELF' : 'CHOOSE BY EYE'}
          </Text>
          {reading.ranked.map((match) => (
            <Pressable
              key={match.option}
              style={[
                styles.option,
                reading.confident &&
                  match.option === reading.option &&
                  styles.optionSuggested,
              ]}
              onPress={() => accept(match.option)}
            >
              <Text style={styles.optionText}>{match.option}</Text>
            </Pressable>
          ))}
          <Text style={styles.footnote}>
            Nothing is recorded until you pick one. If the photograph and the
            colour disagree, trust your eyes.
          </Text>
        </View>
      ) : null}
    </ScrollView>
  );
}

function regionStyle(region: Region) {
  return {
    left: `${region.x * 100}%` as const,
    top: `${region.y * 100}%` as const,
    width: `${region.width * 100}%` as const,
    height: `${region.height * 100}%` as const,
  };
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.colour.background },
  content: { padding: theme.spacing(2.5), gap: theme.spacing(2) },
  heading: { fontSize: theme.font.title, fontWeight: '800', color: theme.colour.text },
  body: { fontSize: theme.font.body, color: theme.colour.textMuted, lineHeight: 23 },
  steps: { gap: theme.spacing(1.5) },
  step: { flexDirection: 'row', gap: theme.spacing(1.5), alignItems: 'flex-start' },
  stepNumber: {
    fontSize: theme.font.small,
    fontWeight: '800',
    color: theme.colour.background,
    backgroundColor: theme.colour.accent,
    width: 24,
    height: 24,
    borderRadius: 12,
    textAlign: 'center',
    lineHeight: 24,
    overflow: 'hidden',
  },
  stepText: { flex: 1, fontSize: theme.font.body, color: theme.colour.text, lineHeight: 23 },
  why: {
    backgroundColor: theme.colour.surface,
    borderRadius: theme.radius.lg,
    padding: theme.spacing(2),
  },
  whyText: { fontSize: theme.font.small, color: theme.colour.textMuted, lineHeight: 21 },
  statusCard: {
    backgroundColor: theme.colour.surface,
    borderRadius: theme.radius.lg,
    borderWidth: 1,
    borderColor: theme.colour.border,
    padding: theme.spacing(2.5),
  },
  statusReady: { borderColor: theme.colour.confident },
  statusStale: { borderColor: theme.colour.caution },
  statusText: { fontSize: theme.font.body, color: theme.colour.text, lineHeight: 23 },
  photo: {
    width: '100%',
    height: 240,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colour.surface,
  },
  patch: { position: 'absolute', borderWidth: 2, borderRadius: 4, justifyContent: 'flex-end' },
  depositPatch: { borderColor: theme.colour.accent },
  cardPatch: { borderColor: theme.colour.confident },
  patchLabel: {
    fontSize: theme.font.tiny,
    color: theme.colour.text,
    backgroundColor: 'rgba(0,0,0,0.6)',
    textAlign: 'center',
  },
  row: { flexDirection: 'row', gap: theme.spacing(1.5) },
  section: { gap: theme.spacing(1.25) },
  sectionHeading: {
    fontSize: theme.font.tiny,
    fontWeight: '800',
    letterSpacing: 0.9,
    color: theme.colour.textFaint,
  },
  readingCard: {
    backgroundColor: theme.colour.surface,
    borderRadius: theme.radius.md,
    padding: theme.spacing(2),
    borderLeftWidth: 3,
    borderLeftColor: theme.colour.confident,
  },
  readingUnsure: { borderLeftColor: theme.colour.caution },
  readingReason: { fontSize: theme.font.small, color: theme.colour.text, lineHeight: 21 },
  option: {
    backgroundColor: theme.colour.surfaceRaised,
    borderRadius: theme.radius.md,
    paddingVertical: theme.spacing(1.75),
    paddingHorizontal: theme.spacing(2),
    borderWidth: 1,
    borderColor: 'transparent',
  },
  optionSuggested: { borderColor: theme.colour.accent },
  optionText: { fontSize: theme.font.body, color: theme.colour.text },
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
    flex: 1,
    backgroundColor: theme.colour.surfaceRaised,
    borderRadius: theme.radius.lg,
    paddingVertical: theme.spacing(1.75),
    alignItems: 'center',
  },
  secondaryText: { fontSize: theme.font.body, color: theme.colour.text },
  footnote: {
    fontSize: theme.font.tiny,
    color: theme.colour.textFaint,
    textAlign: 'center',
    lineHeight: 18,
  },
  abandon: {
    fontSize: theme.font.small,
    color: theme.colour.textFaint,
    textAlign: 'center',
    paddingVertical: theme.spacing(1),
  },
});
