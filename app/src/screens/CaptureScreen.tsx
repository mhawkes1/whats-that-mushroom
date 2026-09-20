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
import * as ImagePicker from 'expo-image-picker';

import { theme } from '../lib/theme';

/**
 * Capture screen.
 *
 * Three views rather than one. The cap alone is the weakest evidence a
 * mushroom offers: what is underneath separates gills from pores from spines,
 * which separates whole families, and the base of the stem is where the volva
 * is -- the single feature that most reliably marks the genus responsible for
 * most fatal poisonings.
 *
 * Only the top view is required. Making the other two mandatory would train
 * people to photograph something, anything, to get past the screen, and a
 * photograph taken to satisfy a form is worse than no photograph at all.
 */

type Slot = 'top' | 'side' | 'underside';

const SLOTS: { key: Slot; label: string; hint: string; required: boolean }[] = [
  {
    key: 'top',
    label: 'The cap, from above',
    hint: 'Straight down, in daylight if you can.',
    required: true,
  },
  {
    key: 'side',
    label: 'From the side',
    hint: 'Include the whole stem, right down to the base.',
    required: false,
  },
  {
    key: 'underside',
    label: 'Underneath',
    hint: 'Turn it over. Gills, pores or spines — this one carries the most.',
    required: false,
  },
];

export function CaptureScreen({ navigation }: { navigation: any }) {
  const [photos, setPhotos] = useState<Partial<Record<Slot, string>>>({});

  const capture = useCallback(async (slot: Slot, fromLibrary: boolean) => {
    if (!fromLibrary) {
      const { status } = await ImagePicker.requestCameraPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Camera needed', 'Allow camera access to photograph a mushroom.');
        return;
      }
    }

    const result = fromLibrary
      ? await ImagePicker.launchImageLibraryAsync({
          quality: 0.85,
          mediaTypes: ImagePicker.MediaTypeOptions.Images,
        })
      : await ImagePicker.launchCameraAsync({
          quality: 0.85,
          allowsEditing: false,
          exif: true,
        });

    if (!result.canceled && result.assets[0]) {
      setPhotos((current) => ({ ...current, [slot]: result.assets[0].uri }));
    }
  }, []);

  const chooseSource = useCallback(
    (slot: Slot) => {
      Alert.alert('Add a photo', undefined, [
        { text: 'Take a photo', onPress: () => capture(slot, false) },
        { text: 'Choose from library', onPress: () => capture(slot, true) },
        { text: 'Cancel', style: 'cancel' },
      ]);
    },
    [capture],
  );

  const goToNotes = useCallback(() => {
    if (!photos.top) return;
    navigation.navigate('FieldNotes', { views: photos });
  }, [navigation, photos]);

  const taken = SLOTS.filter((slot) => photos[slot.key]).length;

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>What's That Mushroom?</Text>
      <Text style={styles.subtitle}>
        Photograph a mushroom and I'll tell you what it might be — and, just as
        importantly, when I can't tell.
      </Text>

      <View style={styles.slots}>
        {SLOTS.map((slot) => {
          const uri = photos[slot.key];
          return (
            <Pressable
              key={slot.key}
              onPress={() => chooseSource(slot.key)}
              style={[styles.slot, uri ? styles.slotFilled : null]}
              accessibilityRole="button"
              accessibilityLabel={`${slot.label}. ${uri ? 'Photo added' : 'No photo yet'}`}
            >
              {uri ? (
                <Image source={{ uri }} style={styles.thumb} />
              ) : (
                <View style={[styles.thumb, styles.thumbEmpty]}>
                  <Text style={styles.thumbPlus}>+</Text>
                </View>
              )}

              <View style={styles.slotText}>
                <Text style={styles.slotLabel}>
                  {slot.label}
                  {slot.required ? '' : '  ·  optional'}
                </Text>
                <Text style={styles.slotHint}>{slot.hint}</Text>
                {uri ? <Text style={styles.slotRetake}>Tap to replace</Text> : null}
              </View>
            </Pressable>
          );
        })}
      </View>

      <Pressable
        style={[styles.primary, !photos.top && styles.primaryDisabled]}
        onPress={goToNotes}
        disabled={!photos.top}
        accessibilityRole="button"
      >
        <Text style={styles.primaryText}>
          {photos.top ? 'Next — what did you see?' : 'Add the cap photo to start'}
        </Text>
      </Pressable>

      {photos.top && taken < SLOTS.length ? (
        <Text style={styles.nudge}>
          You can go on with {taken} photo{taken === 1 ? '' : 's'}, but the
          underside and the base of the stem are where the answer usually is.
        </Text>
      ) : null}

      <View style={styles.tips}>
        <Text style={styles.tipsHeading}>Worth doing before you photograph</Text>
        <Text style={styles.tip}>
          • Lever the whole mushroom out of the ground rather than cutting it.
          The base is the part that matters most and the part almost everyone
          leaves behind.
        </Text>
        <Text style={styles.tip}>• Note what it was growing on: soil, wood, grass</Text>
        <Text style={styles.tip}>• Daylight beats indoor light for colour</Text>
      </View>

      <View style={styles.disclaimer}>
        <Text style={styles.disclaimerText}>
          This app never tells you whether a mushroom is safe to eat. Never eat a
          wild mushroom identified only by an app.
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.colour.background },
  content: { padding: theme.spacing(3), gap: theme.spacing(2.5) },
  title: { fontSize: theme.font.title, fontWeight: '800', color: theme.colour.text },
  subtitle: {
    fontSize: theme.font.body,
    color: theme.colour.textMuted,
    lineHeight: 23,
  },
  slots: { gap: theme.spacing(1.5) },
  slot: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.spacing(2),
    backgroundColor: theme.colour.surface,
    borderRadius: theme.radius.lg,
    borderWidth: 1,
    borderColor: theme.colour.border,
    padding: theme.spacing(1.5),
  },
  slotFilled: { borderColor: theme.colour.accent },
  thumb: { width: 68, height: 68, borderRadius: theme.radius.md },
  thumbEmpty: {
    backgroundColor: theme.colour.surfaceRaised,
    alignItems: 'center',
    justifyContent: 'center',
  },
  thumbPlus: { fontSize: 30, color: theme.colour.textFaint },
  slotText: { flex: 1, gap: 2 },
  slotLabel: { fontSize: theme.font.body, color: theme.colour.text, fontWeight: '600' },
  slotHint: { fontSize: theme.font.small, color: theme.colour.textMuted, lineHeight: 19 },
  slotRetake: { fontSize: theme.font.tiny, color: theme.colour.accent },
  primary: {
    backgroundColor: theme.colour.accent,
    borderRadius: theme.radius.lg,
    paddingVertical: theme.spacing(2.25),
    alignItems: 'center',
  },
  primaryDisabled: { backgroundColor: theme.colour.surfaceRaised },
  primaryText: {
    fontSize: theme.font.heading,
    fontWeight: '700',
    color: theme.colour.background,
  },
  nudge: {
    fontSize: theme.font.small,
    color: theme.colour.textMuted,
    lineHeight: 20,
    textAlign: 'center',
  },
  tips: {
    backgroundColor: theme.colour.surface,
    borderRadius: theme.radius.lg,
    padding: theme.spacing(2.5),
    gap: theme.spacing(1),
  },
  tipsHeading: {
    fontSize: theme.font.tiny,
    fontWeight: '800',
    letterSpacing: 0.8,
    color: theme.colour.accent,
  },
  tip: { fontSize: theme.font.small, color: theme.colour.textMuted, lineHeight: 21 },
  disclaimer: {
    borderTopWidth: 1,
    borderTopColor: theme.colour.border,
    paddingTop: theme.spacing(2),
  },
  disclaimerText: {
    fontSize: theme.font.tiny,
    color: theme.colour.textFaint,
    lineHeight: 18,
    textAlign: 'center',
  },
});
