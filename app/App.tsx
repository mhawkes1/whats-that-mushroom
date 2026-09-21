import React, { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { NavigationContainer, DefaultTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { CaptureScreen } from './src/screens/CaptureScreen';
import { ConsentScreen } from './src/screens/ConsentScreen';
import { EmergencyScreen } from './src/screens/EmergencyScreen';
import { FieldNotesScreen } from './src/screens/FieldNotesScreen';
import { HistoryScreen } from './src/screens/HistoryScreen';
import { ReportScreen } from './src/screens/ReportScreen';
import { ResultScreen } from './src/screens/ResultScreen';
import { SporePrintScreen } from './src/screens/SporePrintScreen';
import { getDisclaimer } from './src/lib/api';
import { gate, readConsent, type Gate } from './src/lib/consent';
import { theme } from './src/lib/theme';

const Stack = createNativeStackNavigator();

const navTheme = {
  ...DefaultTheme,
  dark: true,
  colors: {
    ...DefaultTheme.colors,
    background: theme.colour.background,
    card: theme.colour.surface,
    text: theme.colour.text,
    border: theme.colour.border,
    primary: theme.colour.accent,
  },
};

/**
 * Where the app opens.
 *
 * The disclaimer must be acknowledged before first use, and re-acknowledged
 * if it has materially changed -- the server derives its version from the
 * text, so "changed" means the statements actually differ, not that a
 * constant was bumped.
 *
 * A device that has consented and cannot reach the service is let through.
 * Everything else here needs the network, but locking someone out of their
 * own observation log over a dropped connection is not a safety measure. A
 * device that has *not* consented is not, because it has never been shown
 * what the app does not do.
 */
function useGate(): Gate | null {
  const [decision, setDecision] = useState<Gate | null>(null);

  useEffect(() => {
    let live = true;
    (async () => {
      const [stored, version] = await Promise.all([
        readConsent(),
        getDisclaimer()
          .then((d) => d.version)
          .catch(() => null),
      ]);
      if (live) setDecision(gate(stored, version));
    })();
    return () => {
      live = false;
    };
  }, []);

  return decision;
}

export default function App() {
  const decision = useGate();

  if (decision === null) {
    return (
      <SafeAreaProvider>
        <StatusBar style="light" />
        <View
          style={{
            flex: 1,
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: theme.colour.background,
          }}
        >
          <ActivityIndicator color={theme.colour.accent} />
        </View>
      </SafeAreaProvider>
    );
  }

  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      <NavigationContainer theme={navTheme}>
        <Stack.Navigator
          initialRouteName={decision === 'allow' ? 'Capture' : 'Consent'}
          screenOptions={{
            headerStyle: { backgroundColor: theme.colour.surface },
            headerTintColor: theme.colour.text,
            contentStyle: { backgroundColor: theme.colour.background },
          }}
        >
          <Stack.Screen
            name="Consent"
            component={ConsentScreen}
            options={{ headerShown: false }}
          />
          <Stack.Screen
            name="Capture"
            component={CaptureScreen}
            options={{ headerShown: false }}
          />
          <Stack.Screen
            name="FieldNotes"
            component={FieldNotesScreen}
            options={{ title: 'What did you see?' }}
          />
          <Stack.Screen
            name="Result"
            component={ResultScreen}
            options={{ title: 'What I can tell you' }}
          />
          <Stack.Screen
            name="History"
            component={HistoryScreen}
            options={{ title: 'Your observations' }}
          />
          <Stack.Screen
            name="Report"
            component={ReportScreen}
            options={{ title: 'Tell me I got it wrong' }}
          />
          {/* Reachable from every screen, including before consent. */}
          <Stack.Screen
            name="Emergency"
            component={EmergencyScreen}
            options={{ title: 'Someone has eaten one' }}
          />
          <Stack.Screen
            name="SporePrint"
            component={SporePrintScreen}
            options={{ title: 'Spore print' }}
          />
        </Stack.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
