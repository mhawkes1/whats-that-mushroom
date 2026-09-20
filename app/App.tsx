import React from 'react';
import { NavigationContainer, DefaultTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { CaptureScreen } from './src/screens/CaptureScreen';
import { FieldNotesScreen } from './src/screens/FieldNotesScreen';
import { ResultScreen } from './src/screens/ResultScreen';
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

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      <NavigationContainer theme={navTheme}>
        <Stack.Navigator
          screenOptions={{
            headerStyle: { backgroundColor: theme.colour.surface },
            headerTintColor: theme.colour.text,
            contentStyle: { backgroundColor: theme.colour.background },
          }}
        >
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
        </Stack.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
