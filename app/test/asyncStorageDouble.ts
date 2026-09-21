/**
 * An in-memory stand-in for AsyncStorage.
 *
 * The real one is a native module and cannot load outside a device, but the
 * behaviour worth testing is not the native call -- it is what the log does
 * around it: capping, replacing an entry in place, and surviving a read that
 * comes back as rubbish or a write that refuses. So the double is a real
 * store, and the failure modes are switched on explicitly.
 */

const store = new Map<string, string>();

export const control = {
  failReads: false,
  failWrites: false,
  reset(): void {
    store.clear();
    control.failReads = false;
    control.failWrites = false;
  },
  /** Put something the log did not write, to test the read path. */
  seed(key: string, raw: string): void {
    store.set(key, raw);
  },
  raw(key: string): string | undefined {
    return store.get(key);
  },
};

export default {
  async getItem(key: string): Promise<string | null> {
    if (control.failReads) throw new Error('storage unavailable');
    return store.get(key) ?? null;
  },
  async setItem(key: string, value: string): Promise<void> {
    if (control.failWrites) throw new Error('storage full');
    store.set(key, value);
  },
  async removeItem(key: string): Promise<void> {
    if (control.failWrites) throw new Error('storage unavailable');
    store.delete(key);
  },
};
