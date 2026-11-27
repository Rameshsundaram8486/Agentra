/* Drawer, dialog and tooltip, on Radix primitives for focus handling, Escape to close and screen-reader labels. */
import type { ReactNode } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { X } from "lucide-react";
import { Button } from "./Button";
import { cn } from "./cn";

interface OverlayProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}

/** A side panel for details (an execution, an agent, a decision). */
export function Drawer({ open, onOpenChange, title, description, children, footer, width = "w-[min(560px,100vw)]" }: OverlayProps & { width?: string }) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[1px]" />
        <DialogPrimitive.Content className={cn("fixed inset-y-0 right-0 z-50 flex flex-col border-l border-line bg-surface shadow-panel outline-none", width)}>
          <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
            <div className="min-w-0">
              <DialogPrimitive.Title className="text-base font-semibold text-fg">{title}</DialogPrimitive.Title>
              {description ? (
                <DialogPrimitive.Description className="mt-0.5 text-[13px] text-fg-muted">{description}</DialogPrimitive.Description>
              ) : (
                <DialogPrimitive.Description className="sr-only">Details</DialogPrimitive.Description>
              )}
            </div>
            <DialogPrimitive.Close asChild>
              <Button variant="ghost" size="sm" iconOnly icon={X} aria-label="Close" />
            </DialogPrimitive.Close>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
          {footer && <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-line px-5 py-3">{footer}</footer>}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/** A centred dialog for focused tasks (confirmations, short forms). */
export function Dialog({ open, onOpenChange, title, description, children, footer }: OverlayProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <DialogPrimitive.Content className="fixed top-1/2 left-1/2 z-50 flex max-h-[85vh] w-[min(520px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 flex-col rounded-[var(--radius-panel)] border border-line bg-surface shadow-panel outline-none">
          <header className="flex items-start justify-between gap-3 px-5 pt-4 pb-2">
            <div>
              <DialogPrimitive.Title className="text-base font-semibold text-fg">{title}</DialogPrimitive.Title>
              {description ? (
                <DialogPrimitive.Description className="mt-0.5 text-[13px] text-fg-muted">{description}</DialogPrimitive.Description>
              ) : (
                <DialogPrimitive.Description className="sr-only">Dialog</DialogPrimitive.Description>
              )}
            </div>
            <DialogPrimitive.Close asChild>
              <Button variant="ghost" size="sm" iconOnly icon={X} aria-label="Close" />
            </DialogPrimitive.Close>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-2">{children}</div>
          {footer && <footer className="flex flex-wrap items-center justify-end gap-2 px-5 pt-2 pb-4">{footer}</footer>}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

export const TooltipProvider = TooltipPrimitive.Provider;

/** Contextual help on hover and keyboard focus. */
export function Tooltip({ content, children, side = "top" }: { content: ReactNode; children: ReactNode; side?: "top" | "right" | "bottom" | "left" }) {
  return (
    <TooltipPrimitive.Root delayDuration={250}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content side={side} sideOffset={6} className="z-[60] max-w-72 rounded-md border border-line-strong bg-surface-3 px-2.5 py-1.5 text-xs text-fg shadow-panel">
          {content}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
