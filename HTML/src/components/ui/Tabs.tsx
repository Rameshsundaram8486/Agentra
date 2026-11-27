import type { ReactNode } from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cn } from "./cn";

export interface TabItem {
  value: string;
  label: ReactNode;
  count?: number;
}

/** Underlined tabs (keyboard: arrow keys move between tabs). Content goes in <TabPanel> children. */
export function Tabs({ items, value, onValueChange, children, className }: { items: TabItem[]; value: string; onValueChange: (value: string) => void; children: ReactNode; className?: string }) {
  return (
    <TabsPrimitive.Root value={value} onValueChange={onValueChange} className={cn("flex min-w-0 flex-col", className)}>
      <TabsPrimitive.List className="flex gap-1 overflow-x-auto border-b border-line" aria-label="Sections">
        {items.map((item) => (
          <TabsPrimitive.Trigger
            key={item.value}
            value={item.value}
            className="relative -mb-px inline-flex h-10 shrink-0 items-center gap-1.5 border-b-2 border-transparent px-3 text-[13px] font-medium text-fg-muted transition-colors hover:text-fg data-[state=active]:border-primary data-[state=active]:text-fg"
          >
            {item.label}
            {item.count !== undefined && <span className="rounded-full bg-surface-2 px-1.5 text-2xs text-fg-muted tabular">{item.count}</span>}
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>
      {children}
    </TabsPrimitive.Root>
  );
}

export function TabPanel({ value, children, className }: { value: string; children: ReactNode; className?: string }) {
  return (
    <TabsPrimitive.Content value={value} className={cn("pt-4 outline-none", className)}>
      {children}
    </TabsPrimitive.Content>
  );
}

/** A compact segmented control (view modes, speed, filters). */
export function Segmented<T extends string>({ options, value, onChange, label }: { options: { value: T; label: ReactNode }[]; value: T; onChange: (value: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border border-line bg-surface-2 p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          onClick={() => onChange(option.value)}
          className={cn(
            "inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium transition-colors",
            value === option.value ? "bg-surface-3 text-fg shadow-sm" : "text-fg-muted hover:text-fg",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
