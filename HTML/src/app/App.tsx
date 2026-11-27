import { lazy, Suspense, type ComponentType, type LazyExoticComponent } from "react";
import { HashRouter, Route, Routes } from "react-router";
import { AppShell } from "@/components/layout/AppShell";
import { Skeleton } from "@/components/ui/States";
import { CommandCenter } from "@/pages/CommandCenter";
import { Placeholder } from "@/pages/Placeholder";
import { NAV_ITEMS } from "./navigation";
import { Providers } from "./providers";

const named = <K extends string>(load: () => Promise<Record<K, ComponentType>>, name: K) => lazy(() => load().then((m) => ({ default: m[name] })));

// Pages other than the Command Center load when first opened, so the first screen loads quickly.
const LiveOperations = named(() => import("@/pages/LiveOperations"), "LiveOperations");
const AgentControlCenter = named(() => import("@/pages/Agents"), "AgentControlCenter");
const AgentDirectory = named(() => import("@/pages/Agents"), "AgentDirectory");
const ExecutionHistory = named(() => import("@/pages/Agents"), "ExecutionHistory");
const Gallery = named(() => import("@/pages/Gallery"), "Gallery");

/** Built pages by navigation id; the rest show their placeholder until their stage. */
const PAGES: Record<string, ComponentType | LazyExoticComponent<ComponentType>> = {
  command: CommandCenter,
  operations: LiveOperations,
  agents: AgentControlCenter,
  directory: AgentDirectory,
  history: ExecutionHistory,
};

function Loading() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-8 w-72" />
      <Skeleton className="h-4 w-[28rem] max-w-full" />
      <div className="grid gap-4 md:grid-cols-3"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>
      <Skeleton className="h-80" />
    </div>
  );
}

// Hash routes, so the built demo works from any static host without server rewrites. Every navigation item has a
// route; pages not built yet show what they will contain (pages/Placeholder.tsx).
export function App() {
  return (
    <Providers>
      <HashRouter>
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route element={<AppShell />}>
              {NAV_ITEMS.map((item) => {
                const Page = PAGES[item.id];
                return <Route key={item.id} path={item.path} element={Page ? <Suspense fallback={<Loading />}><Page /></Suspense> : <Placeholder item={item} />} />;
              })}
              <Route path="/projects/:projectId" element={<Placeholder />} />
              <Route path="/design-system" element={<Suspense fallback={<Loading />}><Gallery /></Suspense>} />
              <Route path="*" element={<Placeholder />} />
            </Route>
          </Routes>
        </Suspense>
      </HashRouter>
    </Providers>
  );
}
