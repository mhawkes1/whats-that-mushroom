import React from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { EMERGENCY_HEADLINE, EMERGENCY_STEPS } from '../lib/emergency';
import { theme } from '../lib/theme';

/**
 * The one screen that must always work.
 *
 * No network, no data fetched, nothing that can be in a loading state. It is
 * reachable before consent, from the report form, and from the capture
 * screen, because the person who needs it is not going to navigate.
 *
 * The two call buttons are first and are the only affordances. Everything
 * else is text they can read while the phone is ringing.
 */
export function EmergencyScreen() {
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.headline}>{EMERGENCY_HEADLINE}</Text>

      <View style={styles.calls}>
        <Pressable
          style={[styles.call, styles.call999]}
          onPress={() => Linking.openURL('tel:999')}
          accessibilityRole="button"
          accessibilityLabel="Call 999"
        >
          <Text style={styles.call999Text}>Call 999</Text>
          <Text style={styles.callHint}>Seriously unwell</Text>
        </Pressable>
        <Pressable
          style={styles.call}
          onPress={() => Linking.openURL('tel:111')}
          accessibilityRole="button"
          accessibilityLabel="Call NHS 111"
        >
          <Text style={styles.callText}>Call 111</Text>
          <Text style={styles.callHint}>Advice, any hour</Text>
        </Pressable>
      </View>

      {EMERGENCY_STEPS.map((step, index) => (
        <View key={step.heading} style={styles.step}>
          <Text style={styles.stepNumber}>{index + 1}</Text>
          <View style={styles.stepBody}>
            <Text style={styles.stepHeading}>{step.heading}</Text>
            <Text style={styles.stepText}>{step.body}</Text>
          </View>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.colour.dangerSurface },
  content: { padding: theme.spacing(2.5), gap: theme.spacing(2.5) },
  headline: {
    fontSize: theme.font.title,
    fontWeight: '800',
    color: theme.colour.text,
    lineHeight: 32,
  },
  calls: { flexDirection: 'row', gap: theme.spacing(1.5) },
  call: {
    flex: 1,
    alignItems: 'center',
    borderRadius: theme.radius.md,
    paddingVertical: theme.spacing(2),
    borderWidth: 1,
    borderColor: theme.colour.danger,
    gap: 2,
  },
  call999: { backgroundColor: theme.colour.danger, borderColor: theme.colour.danger },
  call999Text: { fontSize: theme.font.heading, fontWeight: '800', color: '#fff' },
  callText: { fontSize: theme.font.heading, fontWeight: '800', color: theme.colour.danger },
  callHint: { fontSize: theme.font.tiny, color: theme.colour.textMuted },
  step: { flexDirection: 'row', gap: theme.spacing(1.5) },
  stepNumber: {
    fontSize: theme.font.small,
    fontWeight: '800',
    color: theme.colour.danger,
    width: 18,
    paddingTop: 2,
  },
  stepBody: { flex: 1, gap: theme.spacing(0.5) },
  stepHeading: { fontSize: theme.font.body, fontWeight: '700', color: theme.colour.text },
  stepText: { fontSize: theme.font.small, color: theme.colour.textMuted, lineHeight: 21 },
});
