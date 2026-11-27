/* The top bar: search, workspace, platform status, the demo controls, approvals for the current role,
   notifications, theme and the role switcher. Everything that is simulated says so. */
import { useState } from "react";
import {
  Bell, Building, CheckCheck, ChevronDown, Command, Inbox, Menu as MenuIcon, Moon, Pause, Play, Presentation, RotateCcw, Search, Sun, UserRound,
} from "lucide-react";
import { Link, useNavigate } from "react-router";
import { Avatar } from "@/components/ui/Avatar";
import { GUIDE_STEPS } from "@/data/presenterGuide";
import { CountBadge, Dot, Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import { Menu, MenuItem, MenuLabel, MenuSeparator, Popover, PopoverClose } from "@/components/ui/Menu";
import { Tooltip } from "@/components/ui/Overlays";
import { Segmented } from "@/components/ui/Tabs";
import type { Tone } from "@/components/ui/status";
import { formatDateTime, relative } from "@/lib/format";
import { useDataService } from "@/services/dataService";
import { ROLE_LABELS } from "@/store/actions";
import { actorName, byId, isOpenDecision, unreadNotifications } from "@/store/selectors";
import { ROLE_PEOPLE, useDemo } from "@/store/useDemo";
import { useUi } from "@/store/useUi";
import { scenarioProgress } from "@/simulation/engine";
import type { Role, World } from "@/types";

const SEVERITY_TONE: Record<string, Tone> = { info: "primary", success: "success", warning: "warning", critical: "danger" };
const MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.userAgent);

function SearchButton() {
  const setPalette = useUi((s) => s.setPalette);
  return (
    <button
      type="button"
      onClick={() => setPalette(true)}
      aria-label="Search projects, agents and decisions"
      className="flex h-9 w-9 shrink-0 items-center justify-center gap-2 rounded-lg border border-line bg-surface text-[13px] text-fg-subtle transition-colors hover:border-line-strong sm:w-auto sm:min-w-0 sm:flex-1 sm:justify-start sm:px-3 md:max-w-md"
    >
      <Search className="size-4 shrink-0" aria-hidden />
      <span className="hidden truncate sm:inline">Search projects, agents, decisions</span>
      <kbd className="ml-auto hidden items-center gap-0.5 rounded border border-line px-1.5 text-2xs text-fg-subtle sm:inline-flex">
        {MAC ? <Command className="size-3" aria-label="Command" /> : "Ctrl "}K
      </kbd>
    </button>
  );
}

function Workspace() {
  return (
    <Menu
      label="Workspace"
      align="start"
      trigger={
        <button type="button" className="hidden h-9 items-center gap-2 rounded-lg px-2.5 text-[13px] text-fg-muted hover:bg-surface-2 hover:text-fg xl:inline-flex">
          <Building className="size-4" aria-hidden />
          Agentra UAE
          <ChevronDown className="size-3.5" aria-hidden />
        </button>
      }
    >
      <MenuLabel>Workspace</MenuLabel>
      <MenuItem icon={Building} checked hint="Dubai · 7 projects">Agentra UAE</MenuItem>
      <MenuItem icon={Building} disabled hint="Planned: international markets">Agentra International</MenuItem>
    </Menu>
  );
}

function integrationSummary(world: World): string {
  const live = world.integrations.filter((i) => i.status === "connected" || i.status === "warning").length;
  const attention = world.integrations.filter((i) => i.status === "warning").length;
  const planned = world.integrations.filter((i) => i.status === "planned").length;
  return `${live} connected${attention ? ` (${attention} needs attention)` : ""}, ${planned} planned`;
}

function SystemStatus() {
  const world = useDemo((s) => s.world);
  const working = world.agents.filter((a) => a.status === "working").length;
  const rows: [string, string, Tone][] = [
    ["Workflow engine", "Operational", "success"],
    ["Agent workers", `${working} of ${world.agents.length} agents working`, "success"],
    ["Model gateway", "Claude API, claude-opus-5-5", "success"],
    ["Sandbox VMs", "Simulated in this demo", "warning"],
    ["Integrations", integrationSummary(world), world.integrations.some((i) => i.status === "warning") ? "warning" : "success"],
  ];
  return (
    <Popover
      label="Platform status"
      width="w-80"
      trigger={
        <button type="button" className="hidden h-9 items-center gap-2 rounded-lg px-2.5 text-[13px] text-fg-muted hover:bg-surface-2 hover:text-fg md:inline-flex">
          <Dot tone="success" />
          Operational
        </button>
      }
    >
      <div className="border-b border-line px-4 py-3">
        <p className="text-sm font-semibold">Platform status</p>
        <p className="text-xs text-fg-subtle">Simulated: this demo is not connected to the Agentra backend.</p>
      </div>
      <ul className="divide-y divide-line">
        {rows.map(([name, detail, tone]) => (
          <li key={name} className="flex items-center gap-2.5 px-4 py-2.5">
            <Dot tone={tone} />
            <span className="flex-1 text-[13px]">{name}</span>
            <span className="text-xs text-fg-muted">{detail}</span>
          </li>
        ))}
      </ul>
    </Popover>
  );
}

function DemoControls() {
  const world = useDemo((s) => s.world);
  const { startSimulation, pauseSimulation, setSpeed, reset } = useDemo();
  const [confirmReset, setConfirmReset] = useState(false);
  const progress = scenarioProgress(world);
  const running = world.sim.running;
  return (
    <Popover
      label="Demo controls"
      width="w-[300px]"
      trigger={
        <button
          type="button"
          aria-label={running ? "Simulation live: open demo controls" : "Simulation paused: open demo controls"}
          className={cn("inline-flex h-9 items-center gap-2 rounded-lg border px-2.5 text-xs font-semibold tracking-wide", running ? "border-success/40 bg-success-soft text-success" : "border-line text-fg-muted hover:bg-surface-2")}
        >
          <Dot tone={running ? "success" : "neutral"} pulse={running} />
          <span className="hidden sm:inline">{running ? "LIVE" : "PAUSED"}</span>
        </button>
      }
    >
      <div className="space-y-3 p-4">
        <div>
          <p className="text-sm font-semibold">Demo mode</p>
          <p className="text-xs text-fg-subtle">A scripted, simulated story. Nothing runs in the Agentra backend.</p>
        </div>
        <div className="flex items-center gap-2">
          {running ? (
            <Button size="sm" icon={Pause} onClick={pauseSimulation}>Pause simulation</Button>
          ) : (
            <Button size="sm" variant="primary" icon={Play} onClick={startSimulation}>Start simulation</Button>
          )}
          <Segmented label="Simulation speed" value={String(world.sim.speed) as "1" | "2" | "5"} onChange={(v) => setSpeed(Number(v) as 1 | 2 | 5)} options={[{ value: "1", label: "1x" }, { value: "2", label: "2x" }, { value: "5", label: "5x" }]} />
        </div>
        <dl className="space-y-1 text-xs">
          <div className="flex justify-between"><dt className="text-fg-subtle">Simulated time</dt><dd className="tabular">{formatDateTime(world.now)}</dd></div>
          <div className="flex justify-between"><dt className="text-fg-subtle">Script</dt><dd className="tabular">{progress.fired} of {progress.total} events</dd></div>
          <div className="flex justify-between"><dt className="text-fg-subtle">Waiting for people or work</dt><dd className="tabular">{progress.waiting}</dd></div>
        </dl>
        <PopoverClose asChild>
          <Link to="/guide" className="flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-[13px] hover:bg-surface-2">
            <Presentation className="size-4 text-fg-subtle" aria-hidden />
            <span className="flex-1">Presenter guide</span>
            <span className="text-2xs text-fg-subtle">{GUIDE_STEPS.length} steps, {GUIDE_STEPS.reduce((s, step) => s + step.minutes, 0)} min</span>
          </Link>
        </PopoverClose>
        <div className="border-t border-line pt-3">
          {confirmReset ? (
            <div className="space-y-2">
              <p className="text-xs text-fg-muted">Reset every project, decision and agent to the start of the story?</p>
              <div className="flex gap-2">
                <PopoverClose asChild>
                  <Button size="sm" variant="danger" icon={RotateCcw} onClick={() => { reset(); setConfirmReset(false); }}>Reset demo data</Button>
                </PopoverClose>
                <Button size="sm" variant="ghost" onClick={() => setConfirmReset(false)}>Keep</Button>
              </div>
            </div>
          ) : (
            <Button size="sm" variant="ghost" icon={RotateCcw} onClick={() => setConfirmReset(true)}>Reset demo data</Button>
          )}
        </div>
      </div>
    </Popover>
  );
}

/** Decisions (approvals, recommendations, escalations) the viewer's role can make; the same count as the Decision Center. */
function WaitingForYou() {
  const world = useDemo((s) => s.world);
  const role = useDemo((s) => s.role);
  const navigate = useNavigate();
  const count = world.decisions.filter((d) => isOpenDecision(d) && d.allowedRoles.includes(role)).length;
  return (
    <Tooltip content={`${count} decision${count === 1 ? "" : "s"} waiting for a ${ROLE_LABELS[role].toLowerCase()}`}>
      <button type="button" onClick={() => navigate("/decisions")} aria-label={`Decisions waiting for you: ${count}`} className="relative grid size-9 place-items-center rounded-lg text-fg-muted hover:bg-surface-2 hover:text-fg">
        <Inbox className="size-[18px]" aria-hidden />
        {count > 0 && <span className="absolute -top-0.5 -right-0.5"><CountBadge count={count} tone="violet" /></span>}
      </button>
    </Tooltip>
  );
}

function Notifications() {
  const world = useDemo((s) => s.world);
  const data = useDataService();
  const navigate = useNavigate();
  const unread = unreadNotifications(world);
  return (
    <Popover
      label="Notifications"
      width="w-[360px]"
      trigger={
        <button type="button" aria-label={`Notifications: ${unread} unread`} className="relative grid size-9 place-items-center rounded-lg text-fg-muted hover:bg-surface-2 hover:text-fg">
          <Bell className="size-[18px]" aria-hidden />
          {unread > 0 && <span className="absolute -top-0.5 -right-0.5"><CountBadge count={unread} tone="danger" /></span>}
        </button>
      }
    >
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <p className="text-sm font-semibold">Notifications</p>
        <Button size="sm" variant="ghost" icon={CheckCheck} disabled={unread === 0} onClick={() => data.markNotificationsRead()}>Mark all read</Button>
      </div>
      <ul className="max-h-[420px] divide-y divide-line overflow-y-auto">
        {world.notifications.map((n) => (
          <li key={n.id}>
            <PopoverClose asChild>
              <button
                type="button"
                onClick={() => {
                  data.markNotificationsRead([n.id]);
                  if (n.link) navigate(n.link);
                }}
                className="flex w-full gap-2.5 px-4 py-2.5 text-left hover:bg-surface-2"
              >
                <Dot tone={SEVERITY_TONE[n.severity] ?? "primary"} className={cn("mt-1.5", n.read && "opacity-30")} />
                <span className="min-w-0 flex-1">
                  <span className={cn("block text-[13px]", n.read ? "text-fg-muted" : "font-medium text-fg")}>{n.title}</span>
                  <span className="block text-xs text-fg-subtle">{n.body}</span>
                  <span className="block text-2xs text-fg-subtle">{relative(n.at, world.now)}</span>
                </span>
              </button>
            </PopoverClose>
          </li>
        ))}
      </ul>
    </Popover>
  );
}

function ThemeToggle() {
  const theme = useDemo((s) => s.theme);
  const setTheme = useDemo((s) => s.setTheme);
  const next = theme === "dark" ? "light" : "dark";
  return (
    <Tooltip content={`Switch to the ${next} theme`}>
      <button type="button" onClick={() => setTheme(next)} aria-label={`Switch to the ${next} theme`} className="grid size-9 place-items-center rounded-lg text-fg-muted hover:bg-surface-2 hover:text-fg">
        {theme === "dark" ? <Sun className="size-[18px]" /> : <Moon className="size-[18px]" />}
      </button>
    </Tooltip>
  );
}

function Profile() {
  const world = useDemo((s) => s.world);
  const role = useDemo((s) => s.role);
  const setRole = useDemo((s) => s.setRole);
  const person = byId(world.people, ROLE_PEOPLE[role])!;
  return (
    <Menu
      label="Acting as"
      trigger={
        <button type="button" aria-label={`Acting as ${person.name}, ${ROLE_LABELS[role].toLowerCase()}. Switch role`} className="flex h-9 items-center gap-2 rounded-lg pr-1.5 pl-1 hover:bg-surface-2">
          <Avatar name={person.name} size="sm" />
          <span className="hidden text-left leading-tight lg:block">
            <span className="block text-[13px] font-medium">{person.name}</span>
            <span className="block text-2xs text-fg-subtle">{ROLE_LABELS[role]}</span>
          </span>
          <ChevronDown className="size-3.5 text-fg-subtle" aria-hidden />
        </button>
      }
    >
      <MenuLabel>Act as (demo)</MenuLabel>
      {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
        <MenuItem key={r} icon={UserRound} checked={r === role} hint={actorName(world, ROLE_PEOPLE[r])} onSelect={() => setRole(r)}>
          {ROLE_LABELS[r]}
        </MenuItem>
      ))}
      <MenuSeparator />
      <p className="px-2.5 py-1.5 text-2xs text-fg-subtle">Switching roles shows what each person may approve. Agents never approve.</p>
    </Menu>
  );
}

export function TopBar() {
  const setMobileNav = useUi((s) => s.setMobileNav);
  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 border-b border-line bg-shell/95 px-3 backdrop-blur sm:px-4">
      <button type="button" onClick={() => setMobileNav(true)} aria-label="Open navigation" className="grid size-9 place-items-center rounded-lg text-fg-muted hover:bg-surface-2 lg:hidden">
        <MenuIcon className="size-5" />
      </button>
      <SearchButton />
      <Workspace />
      <div className="ml-auto flex items-center gap-1">
        <span className="hidden sm:inline-flex"><Tag tone="warning" title="Everything shown is simulated; nothing is connected to the Agentra backend">Demo · simulated</Tag></span>
        <SystemStatus />
        <DemoControls />
        <WaitingForYou />
        <Notifications />
        <ThemeToggle />
        <Profile />
      </div>
    </header>
  );
}
