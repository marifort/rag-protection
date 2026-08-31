import '@testing-library/jest-dom/vitest';
import { beforeEach } from 'vitest';

function createMemoryStorage(): Storage {
  const store = new Map<string, string>();
  return {
    get length() {
      return store.size;
    },
    clear: () => {
      store.clear();
    },
    getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => {
      store.delete(key);
    },
    setItem: (key: string, value: string) => {
      store.set(key, String(value));
    },
  };
}

const localStore = createMemoryStorage();
const sessionStore = createMemoryStorage();

Object.defineProperty(window, 'localStorage', {
  configurable: true,
  value: localStore,
});

Object.defineProperty(window, 'sessionStorage', {
  configurable: true,
  value: sessionStore,
});

beforeEach(() => {
  localStore.clear();
  sessionStore.clear();
});
