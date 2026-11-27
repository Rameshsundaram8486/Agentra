import type { StateStorage } from "zustand/middleware";

/** localStorage that never throws (private windows, blocked storage): the demo then simply does not persist. */
export const safeStorage: StateStorage = {
  getItem: (name) => {
    try {
      return localStorage.getItem(name);
    } catch {
      return null;
    }
  },
  setItem: (name, value) => {
    try {
      localStorage.setItem(name, value);
    } catch {
      /* not persisted */
    }
  },
  removeItem: (name) => {
    try {
      localStorage.removeItem(name);
    } catch {
      /* nothing to remove */
    }
  },
};
