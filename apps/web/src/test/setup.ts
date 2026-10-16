import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Node 25+ has a built-in localStorage that is undefined without --localstorage-file and hides jsdom's.
if (!globalThis.localStorage) {
  const store = new Map<string, string>();
  const storage: Storage = {
    getItem: (key) => store.get(key) ?? null,
    setItem: (key, value) => void store.set(key, String(value)),
    removeItem: (key) => void store.delete(key),
    clear: () => store.clear(),
    key: (index) => [...store.keys()][index] ?? null,
    get length() {
      return store.size;
    },
  };
  Object.defineProperty(globalThis, "localStorage", { configurable: true, value: storage });
}

afterEach(cleanup);
