import type { ComponentType } from "react";
import { HashRouter, Route, Routes } from "react-router";
import { AppShell } from "@/components/layout/AppShell";
import { CommandCenter } from "@/pages/CommandCenter";
import { Gallery } from "@/pages/Gallery";
import { Placeholder } from "@/pages/Placeholder";
import { NAV_ITEMS } from "./navigation";
import { Providers } from "./providers";

/** Built pages by navigation id; the rest show their placeholder until their stage. */
const PAGES: Record<string, ComponentType> = {
  command: CommandCenter,
};

// Hash routes, so the built demo works from any static host without server rewrites. Every navigation item has a
// route; pages not built yet show what they will contain (pages/Placeholder.tsx).
export function App() {
  return (
    <Providers>
      <HashRouter>
        <Routes>
          <Route element={<AppShell />}>
            {NAV_ITEMS.map((item) => {
              const Page = PAGES[item.id];
              return <Route key={item.id} path={item.path} element={Page ? <Page /> : <Placeholder item={item} />} />;
            })}
            <Route path="/projects/:projectId" element={<Placeholder />} />
            <Route path="/design-system" element={<Gallery />} />
            <Route path="*" element={<Placeholder />} />
          </Route>
        </Routes>
      </HashRouter>
    </Providers>
  );
}
