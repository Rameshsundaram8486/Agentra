/* The left navigation: eight groups that fold, the current page highlighted, live counts, and "Preview" on pages
   outside the MVP. It collapses to icons (with tooltips) on wide screens and slides in from the left on narrow ones. */
import { useEffect, useRef } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ChevronDown, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { NavLink, useLocation } from "react-router";
import { NAVIGATION, NAV_ITEMS, type NavItem } from "@/app/navigation";
import { CountBadge, Tag } from "@/components/ui/Badge";
import { cn } from "@/components/ui/cn";
import { Tooltip } from "@/components/ui/Overlays";
import { useDemo } from "@/store/useDemo";
import { useUi } from "@/store/useUi";

function Brand({ collapsed }: { collapsed: boolean }) {
  return (
    <div className={cn("flex h-14 shrink-0 items-center gap-2.5 border-b border-line", collapsed ? "justify-center px-0" : "px-4")}>
      <img src="/agentra.svg" alt="" className="size-7" />
      {!collapsed && (
        <div className="min-w-0 leading-tight">
          <div className="text-[15px] font-semibold tracking-tight">Agentra</div>
          <div className="truncate text-2xs text-fg-subtle">A company run by agents</div>
        </div>
      )}
    </div>
  );
}

function Item({ item, collapsed, onNavigate }: { item: NavItem; collapsed: boolean; onNavigate?: () => void }) {
  const world = useDemo((s) => s.world);
  const role = useDemo((s) => s.role);
  const count = item.count?.(world, role) ?? null;
  const Icon = item.icon;
  const link = (
    <NavLink
      to={item.path}
      end={item.path === "/" || NAV_ITEMS.some((other) => other.path.startsWith(`${item.path}/`))} // a parent path is active only on itself
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "group relative flex h-8 items-center gap-2.5 rounded-lg text-[13px] transition-colors",
          collapsed ? "justify-center px-0" : "px-2.5",
          isActive ? "bg-primary-soft font-medium text-fg" : "text-fg-muted hover:bg-surface-2 hover:text-fg",
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && <span aria-hidden className="absolute top-1.5 bottom-1.5 left-0 w-0.5 rounded-full bg-primary" />}
          <Icon className={cn("size-4 shrink-0", isActive ? "text-primary-strong" : "text-fg-subtle group-hover:text-fg-muted")} aria-hidden />
          {!collapsed && <span className="min-w-0 flex-1 truncate">{item.label}</span>}
          {!collapsed && item.preview && <Tag className="h-4 px-1 text-[10px]">Preview</Tag>}
          {count && count.value > 0 && (collapsed ? <span aria-hidden className="absolute top-1 right-1.5 size-1.5 rounded-full bg-primary" /> : <CountBadge count={count.value} tone={count.tone} label={`${count.value} ${count.label}`} />)}
        </>
      )}
    </NavLink>
  );
  if (!collapsed) return link;
  return (
    <Tooltip side="right" content={<span>{item.label}{item.preview ? " (Preview)" : ""}{count && count.value > 0 ? `: ${count.value} ${count.label}` : ""}</span>}>
      {link}
    </Tooltip>
  );
}

function Navigation({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const folded = useUi((s) => s.foldedGroups);
  const toggleGroup = useUi((s) => s.toggleGroup);
  const { pathname } = useLocation();
  const nav = useRef<HTMLElement>(null);
  useEffect(() => {
    // Keep the current page's item in view (it can sit below the fold, e.g. Administration).
    nav.current?.querySelector('[aria-current="page"]')?.scrollIntoView?.({ block: "nearest" });
  }, [pathname]);
  return (
    <nav ref={nav} aria-label="Main" className="min-h-0 flex-1 space-y-3 overflow-y-auto px-2.5 py-3">
      {NAVIGATION.map((group) => {
        const open = collapsed || !folded.includes(group.id);
        return (
          <div key={group.id}>
            {collapsed ? (
              <div aria-hidden className="mx-2 mb-1.5 h-px bg-line first:hidden" />
            ) : (
              <button
                type="button"
                aria-expanded={open}
                onClick={() => toggleGroup(group.id)}
                className="mb-0.5 flex w-full items-center justify-between rounded-md px-2.5 py-1 text-2xs font-semibold tracking-wider text-fg-subtle uppercase hover:text-fg-muted"
              >
                {group.label}
                <ChevronDown className={cn("size-3.5 transition-transform", !open && "-rotate-90")} aria-hidden />
              </button>
            )}
            {open && (
              <ul className="space-y-0.5">
                {group.items.map((item) => (
                  <li key={item.id}>
                    <Item item={item} collapsed={collapsed} onNavigate={onNavigate} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </nav>
  );
}

/** The sidebar on wide screens. */
export function Sidebar() {
  const collapsed = useUi((s) => s.sidebarCollapsed);
  const toggle = useUi((s) => s.toggleSidebar);
  return (
    <aside className={cn("sticky top-0 hidden h-screen shrink-0 flex-col border-r border-line bg-shell transition-[width] duration-200 lg:flex", collapsed ? "w-16" : "w-[248px]")}>
      <Brand collapsed={collapsed} />
      <Navigation collapsed={collapsed} />
      <div className={cn("flex shrink-0 items-center border-t border-line p-2.5", collapsed ? "justify-center" : "justify-between")}>
        {!collapsed && <span className="pl-1.5 text-2xs text-fg-subtle">Demo · simulated data</span>}
        <Tooltip side="right" content={collapsed ? "Expand the sidebar" : "Collapse the sidebar"}>
          <button type="button" onClick={toggle} aria-label={collapsed ? "Expand the sidebar" : "Collapse the sidebar"} className="grid size-8 place-items-center rounded-lg text-fg-subtle hover:bg-surface-2 hover:text-fg">
            {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
          </button>
        </Tooltip>
      </div>
    </aside>
  );
}

/** The same navigation as a slide-in panel on narrow screens. */
export function MobileNav() {
  const open = useUi((s) => s.mobileNavOpen);
  const setOpen = useUi((s) => s.setMobileNav);
  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/50 lg:hidden" />
        <DialogPrimitive.Content className="fixed inset-y-0 left-0 z-50 flex w-[272px] flex-col border-r border-line bg-shell outline-none lg:hidden">
          <DialogPrimitive.Title className="sr-only">Navigation</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">Agentra sections</DialogPrimitive.Description>
          <Brand collapsed={false} />
          <Navigation collapsed={false} onNavigate={() => setOpen(false)} />
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
