import { useEffect, type ReactNode } from "react";
import { TooltipProvider } from "@/components/ui/Overlays";
import { useDemo } from "@/store/useDemo";

/** Applies the theme to <html>, so every token switches at once. A ?theme=light or ?theme=dark link sets it. */
function ThemeSync() {
  const theme = useDemo((s) => s.theme);
  const setTheme = useDemo((s) => s.setTheme);
  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("theme");
    if (requested === "light" || requested === "dark") setTheme(requested);
  }, [setTheme]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  return null;
}

/** Drives the simulation: one tick a second while it runs (the speed sets how many ticks each second covers). */
function SimulationClock() {
  const tick = useDemo((s) => s.tick);
  useEffect(() => {
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [tick]);
  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  return (
    <TooltipProvider>
      <ThemeSync />
      <SimulationClock />
      {children}
    </TooltipProvider>
  );
}
