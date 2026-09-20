import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import * as Location from 'expo-location';

import { identify, type FieldContext } from '../lib/api';
import { theme } from '../lib/theme';

/**
 * Capture screen.
 *
 * Location is requested but never required. It measurably improves accuracy
 * (fungal fruiting is tightly bound to season and region), and the copy says
 * so rather than asking for the permission unexplained.
 */
export function CaptureScreen({ navigation }: { navigation: any }) {
  const [busy, setBusy] = useState(false);

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

  const run = useCallback(
    async (uri: string) => {
      setBusy(true);
      try {
        const context = await collectContext();
        const result = await identify(uri, context);
        navigation.navigate('Result', { result, imageUri: uri });
      } catch (error) {
        Alert.alert(
          'Could not identify',
          error instanceof Error ? error.message : 'Something went wrong.',
        );
      } finally {
        setBusy(false);
      }
    },
    [collectContext, navigation],
  );

  const takePhoto = useCallback(async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Camera needed', 'Allow camera access to photograph a mushroom.');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      quality: 0.85,
      allowsEditing: false,
      exif: true,
    });
    if (!result.canceled && result.assets[0]) run(result.assets[0].uri);
  }, [run]);

  const pickPhoto = useCallback(async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      quality: 0.85,
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
    });
    if (!result.canceled && result.assets[0]) run(result.assets[0].uri);
  }, [run]);

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      <Text style={styles.title}>What's That Mushroom?</Text>
      <Text style={styles.subtitle}>
        Photograph a mushroom and I'll tell you what it might be — and, just as
        importantly, when I can't tell.
      </Text>

      <View style={styles.tips}>
        <Text style={styles.tipsHeading}>For a useful answer</Text>
        <Text style={styles.tip}>• Photograph the cap from above, in daylight</Text>
        <Text style={styles.tip}>• Turn one over and show the underside</Text>
        <Text style={styles.tip}>
          • Dig up the whole stem, including the base — this is the part that
          matters most, and it's the part almost everyone cuts off
        </Text>
        <Text style={styles.tip}>• Note what it's growing on: soil, wood, grass</Text>
      </View>

      {busy ? (
        <View style={styles.busy}>
          <ActivityIndicator color={theme.colour.accent} />
          <Text style={styles.busyText}>Looking…</Text>
        </View>
      ) : (
        <View style={styles.actions}>
          <Pressable style={styles.primary} onPress={takePhoto}>
            <Text style={styles.primaryText}>Take a photo</Text>
          </Pressable>
          <Pressable style={styles.secondary} onPress={pickPhoto}>
            <Text style={styles.secondaryText}>Choose from library</Text>
          </Pressable>
        </View>
      )}

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
  title: {
    fontSize: theme.font.title,
    fontWeight: '800',
    color: theme.colour.text,
  },
  subtitle: {
    fontSize: theme.font.body,
    color: theme.colour.textMuted,
    lineHeight: 23,
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
  tip: {
    fontSize: theme.font.small,
    color: theme.colour.textMuted,
    lineHeight: 21,
  },
  actions: { gap: theme.spacing(1.5) },
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
    alignItems: 'center',
  },
  secondaryText: { fontSize: theme.font.body, color: theme.colour.text },
  busy: { alignItems: 'center', gap: theme.spacing(1), paddingVertical: theme.spacing(4) },
  busyText: { color: theme.colour.textMuted, fontSize: theme.font.small },
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
