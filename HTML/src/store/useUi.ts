/* Per-viewer conveniences: sidebar state and folded navigation groups. Kept apart from the demo world, so resetting
   the demo does not undo them. */
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { safeStorage } from "./safeStorage";

interface UiState {
  sidebarCollapsed: boolean;
  foldedGroups: string[];
  mobileNavOpen: boolean;
  paletteOpen: boolean;
  toggleSidebar: () => void;
  toggleGroup: (group: string) => void;
  setMobileNav: (open: boolean) => void;
  setPalette: (open: boolean) => void;
}

export const useUi = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      foldedGroups: [],
      mobileNavOpen: false,
      paletteOpen: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      toggleGroup: (group) => set((s) => ({ foldedGroups: s.foldedGroups.includes(group) ? s.foldedGroups.filter((g) => g !== group) : [...s.foldedGroups, group] })),
      setMobileNav: (open) => set({ mobileNavOpen: open }),
      setPalette: (open) => set({ paletteOpen: open }),
    }),
    {
      name: "agentra-command-center-ui",
      storage: createJSONStorage(() => safeStorage),
      partialize: (s) => ({ sidebarCollapsed: s.sidebarCollapsed, foldedGroups: s.foldedGroups }),
    },
  ),
);
