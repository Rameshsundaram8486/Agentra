/* Global search (Ctrl+K or Cmd+K): pages, projects, agents, decisions and documents. Arrow keys move, Enter opens. */
import { useEffect, useMemo, useRef, useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Bot, FileText, FolderKanban, Palette, Scale, Search, type LucideIcon } from "lucide-react";
import { useNavigate } from "react-router";
import { NAV_ITEMS } from "@/app/navigation";
import { cn } from "@/components/ui/cn";
import { byId } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";
import { useUi } from "@/store/useUi";

interface Result {
  id: string;
  group: string;
  label: string;
  hint: string;
  icon: LucideIcon;
  path: string;
}

export function CommandPalette() {
  const open = useUi((s) => s.paletteOpen);
  const setOpen = useUi((s) => s.setPalette);
  const world = useDemo((s) => s.world);
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const list = useRef<HTMLUListElement>(null);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(!useUi.getState().paletteOpen);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setOpen]);

  const all = useMemo<Result[]>(() => [
    ...NAV_ITEMS.map((i) => ({ id: `page-${i.id}`, group: "Pages", label: i.label, hint: i.preview ? "Preview" : i.description, icon: i.icon, path: i.path })),
    { id: "page-design", group: "Pages", label: "Design system", hint: "Tokens, components and status vocabulary", icon: Palette, path: "/design-system" },
    ...world.projects.map((p) => ({ id: p.id, group: "Projects", label: p.name, hint: `${p.code} · ${byId(world.customers, p.customerId)?.name}`, icon: FolderKanban, path: `/projects/${p.id}` })),
    ...world.agents.map((a) => ({ id: a.id, group: "Agents", label: a.name, hint: world.agentTypes.find((t) => t.key === a.typeKey)?.description ?? "", icon: Bot, path: `/agents?agent=${a.id}` })),
    ...world.decisions.map((d) => ({ id: d.id, group: "Decisions", label: `${d.code} ${d.title}`, hint: byId(world.projects, d.projectId)?.name ?? "", icon: Scale, path: `/decisions?id=${d.id}` })),
    ...world.artifacts.map((a) => ({ id: a.id, group: "Documents", label: a.title, hint: byId(world.projects, a.projectId)?.name ?? "", icon: FileText, path: `/knowledge?doc=${a.id}` })),
  ], [world]);

  const results = useMemo(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    const matching = words.length ? all.filter((r) => words.every((w) => `${r.label} ${r.hint} ${r.group}`.toLowerCase().includes(w))) : all.filter((r) => r.group === "Pages");
    const groups = new Map<string, Result[]>();
    for (const r of matching) groups.set(r.group, [...(groups.get(r.group) ?? []), r].slice(0, 6));
    return [...groups.values()].flat();
  }, [all, query]);

  useEffect(() => setActive(0), [query, open]);
  useEffect(() => {
    list.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  function go(result: Result | undefined) {
    if (!result) return;
    setOpen(false);
    setQuery("");
    navigate(result.path);
  }

  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <DialogPrimitive.Content className="fixed top-[12vh] left-1/2 z-50 w-[min(640px,calc(100vw-24px))] -translate-x-1/2 overflow-hidden rounded-xl border border-line-strong bg-surface shadow-panel outline-none">
          <DialogPrimitive.Title className="sr-only">Search</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">Search pages, projects, agents, decisions and documents</DialogPrimitive.Description>
          <div className="flex items-center gap-2.5 border-b border-line px-4">
            <Search className="size-4 text-fg-subtle" aria-hidden />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, results.length - 1)); }
                if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
                if (e.key === "Enter") { e.preventDefault(); go(results[active]); }
              }}
              placeholder="Search projects, agents, decisions, documents, pages"
              aria-label="Search"
              aria-controls="palette-results"
              aria-activedescendant={results[active] ? `palette-${results[active].id}` : undefined}
              className="h-12 flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-fg-subtle"
            />
            <kbd className="rounded border border-line px-1.5 text-2xs text-fg-subtle">Esc</kbd>
          </div>
          <ul id="palette-results" ref={list} role="listbox" className="max-h-[56vh] overflow-y-auto p-1.5">
            {results.length === 0 && <li className="px-3 py-8 text-center text-[13px] text-fg-muted">Nothing matches "{query}"</li>}
            {results.map((r, index) => {
              const Icon = r.icon;
              const first = index === 0 || results[index - 1]!.group !== r.group;
              return (
                <li key={r.id} role="presentation">
                  {first && <div className="px-2.5 pt-2 pb-1 text-2xs font-semibold tracking-wide text-fg-subtle uppercase">{r.group}</div>}
                  <div
                    id={`palette-${r.id}`}
                    role="option"
                    aria-selected={index === active}
                    data-index={index}
                    onMouseMove={() => setActive(index)}
                    onClick={() => go(r)}
                    className={cn("flex cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2", index === active && "bg-surface-2")}
                  >
                    <Icon className="size-4 shrink-0 text-fg-subtle" aria-hidden />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[13px] text-fg">{r.label}</span>
                      <span className="block truncate text-2xs text-fg-subtle">{r.hint}</span>
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
