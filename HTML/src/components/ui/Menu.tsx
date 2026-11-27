/* Dropdown menus and popovers on Radix primitives (keyboard navigation, focus return, Escape to close). */
import type { ReactNode } from "react";
import * as DropdownPrimitive from "@radix-ui/react-dropdown-menu";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import { Check, type LucideIcon } from "lucide-react";
import { cn } from "./cn";

const SURFACE = "z-50 rounded-xl border border-line-strong bg-surface p-1 shadow-panel outline-none";

export function Menu({ trigger, children, align = "end", label }: { trigger: ReactNode; children: ReactNode; align?: "start" | "end"; label?: string }) {
  return (
    <DropdownPrimitive.Root>
      <DropdownPrimitive.Trigger asChild>{trigger}</DropdownPrimitive.Trigger>
      <DropdownPrimitive.Portal>
        <DropdownPrimitive.Content align={align} sideOffset={6} aria-label={label} className={cn(SURFACE, "min-w-56")}>
          {children}
        </DropdownPrimitive.Content>
      </DropdownPrimitive.Portal>
    </DropdownPrimitive.Root>
  );
}

export function MenuLabel({ children }: { children: ReactNode }) {
  return <DropdownPrimitive.Label className="px-2.5 pt-1.5 pb-1 text-2xs font-semibold tracking-wide text-fg-subtle uppercase">{children}</DropdownPrimitive.Label>;
}

export function MenuSeparator() {
  return <DropdownPrimitive.Separator className="my-1 h-px bg-line" />;
}

export function MenuItem({ children, onSelect, icon: Icon, checked, disabled, hint }: { children: ReactNode; onSelect?: () => void; icon?: LucideIcon; checked?: boolean; disabled?: boolean; hint?: ReactNode }) {
  return (
    <DropdownPrimitive.Item
      disabled={disabled}
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] text-fg outline-none select-none data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50 data-[highlighted]:bg-surface-2"
    >
      {Icon && <Icon className="size-4 shrink-0 text-fg-subtle" aria-hidden />}
      <span className="min-w-0 flex-1">
        <span className="block truncate">{children}</span>
        {hint && <span className="block truncate text-2xs text-fg-subtle">{hint}</span>}
      </span>
      {checked && <Check className="size-4 text-primary-strong" aria-label="Selected" />}
    </DropdownPrimitive.Item>
  );
}

export function Popover({ trigger, children, align = "end", width = "w-80", label }: { trigger: ReactNode; children: ReactNode; align?: "start" | "center" | "end"; width?: string; label: string }) {
  return (
    <PopoverPrimitive.Root>
      <PopoverPrimitive.Trigger asChild>{trigger}</PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content align={align} sideOffset={6} aria-label={label} className={cn(SURFACE, "p-0", width)}>
          {children}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}

export const PopoverClose = PopoverPrimitive.Close;
