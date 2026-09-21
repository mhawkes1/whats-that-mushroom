import { defineConfig } from 'vitest/config';
import { resolve } from 'node:path';

/**
 * Unit tests for the client's pure logic.
 *
 * Only modules that do not touch React Native's renderer are covered here:
 * the storage layers and the rules around them, where a mistake is silent
 * rather than visible. AsyncStorage is aliased to an in-memory double so
 * those rules can be exercised without a device.
 */
export default defineConfig({
  resolve: {
    alias: {
      '@react-native-async-storage/async-storage': resolve(
        __dirname,
        'test/asyncStorageDouble.ts',
      ),
    },
  },
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node',
  },
});
