import React, { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { NavigationContainer, DefaultTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { StatusBar } from 'expo-status-bar';
import { useFonts } from 'expo-font';
import {
  Fraunces_300Light_Italic,
  Fraunces_600SemiBold,
} from '@expo-google-fonts/fraunces';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { CaptureScreen } from './src/screens/CaptureScreen';
import { ConsentScreen } from './src/screens/ConsentScreen';
import { EmergencyScreen } from './src/screens/EmergencyScreen';
import { FieldNotesScreen } from './src/screens/FieldNotesScreen';
import { HistoryScreen } from './src/screens/HistoryScreen';
import { HomeScreen } from './src/screens/HomeScreen';
import { ReportScreen } from './src/screens/ReportScreen';
import { ResultScreen } from './src/screens/ResultScreen';
import { SporePrintScreen } from './src/screens/SporePrintScreen';
import { getDisclaimer } from './src/lib/api';
import { gate, readConsent, type Gate } from './src/lib/consent';
import { theme } from './src/lib/theme';

const Stack = createNativeStackNavigator();
const Tabs = createBottomTabNavigator();

/**
 * Home, Observe, Me.
 *
 * Martin's structure, 2026-10-29, after looking at what other mushroom
 * apps do. It solved something the single-stack arrangement had been
 * fudging: the app had no screen that said what it was for, so the saying
 * had to happen in the corners of the screen people use to work -- which
 * is how the emergency route came to be a red button on the front page and
 * why a corner people read as "add" had to be argued about twice.
 *
 * Each tab now states its own job in a word, and two of the three problems
 * went with it. "Observe" says "another mushroom" more plainly than any
 * corner button; "Me" is where your finds live; Home holds the honesty and
 * a quiet route to the emergency screen.
 *
 * **It opens on Observe, not Home.** People open this app holding a
 * mushroom. Home is one tap to the left for anyone who wants to know what
 * the app refuses to do, and nobody has to tap past a dashboard to do the
 * thing they came for.
 *
 * The flow screens -- notes, result, spore print, report, emergency -- stay
 * on the ROOT stack above the tabs rather than inside a tab. A result that
 * left the tab bar on screen would invite a tap to Observe in the middle of
 * reading a lethal-pair refusal, and the back gesture would then land
 * somewhere nobody intended.
 */
function MainTabs() {
  return (
    <Tabs.Navigator
      initialRouteName="Observe"
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: theme.colour.accent,
        tabBarInactiveTintColor: theme.colour.textMuted,
        tabBarStyle: {
          backgroundColor: theme.colour.surface,
          borderTopColor: theme.colour.border,
        },
        tabBarIcon: ({ color, size }) => {
          const name =
            route.name === 'Home'
              ? 'home-outline'
              : route.name === 'Observe'
                ? 'camera-outline'
                : 'person-outline';
          return <Ionicons name={name} size={size} color={color} />;
        },
      })}
    >
      <Tabs.Screen name="Home" component={HomeScreen} />
      <Tabs.Screen
        name="Observe"
        component={CaptureScreen}
        options={{ tabBarLabel: 'Observe' }}
      />
      <Tabs.Screen
        name="Me"
        component={HistoryScreen}
        options={{ tabBarLabel: 'Me' }}
      />
    </Tabs.Navigator>
  );
}

const navTheme = {
  ...DefaultTheme,
  dark: false,
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

  // The title's typeface. Deliberately not awaited: `useFonts` reports an
  // error as well as a loading state, and a front page that will not render
  // because a font did not arrive is worse than a title set in the platform
  // serif. `AppHeader` names Fraunces and React Native falls back on its own.
  useFonts({ Fraunces_600SemiBold, Fraunces_300Light_Italic });

  if (decision === null) {
    return (
      <SafeAreaProvider>
        <StatusBar style="dark" />
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
      <StatusBar style="dark" />
      <NavigationContainer theme={navTheme}>
        <Stack.Navigator
          initialRouteName={decision === 'allow' ? 'Main' : 'Consent'}
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
            name="Main"
            component={MainTabs}
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
