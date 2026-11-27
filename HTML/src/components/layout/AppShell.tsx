import { Outlet } from "react-router";
import { CommandPalette } from "./CommandPalette";
import { MobileNav, Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

/** Sidebar, top bar and the page. */
export function AppShell() {
  return (
    <div className="flex min-h-screen bg-bg">
      <a href="#main" className="sr-only rounded-lg bg-primary px-3 py-2 text-primary-fg focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[70]">
        Skip to content
      </a>
      <Sidebar />
      <MobileNav />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-5 outline-none sm:px-6">
          <Outlet />
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}
