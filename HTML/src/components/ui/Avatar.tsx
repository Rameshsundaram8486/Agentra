import { Bot } from "lucide-react";
import { cn } from "./cn";

const PALETTE = ["bg-primary-soft text-primary-strong", "bg-cyan-soft text-cyan", "bg-violet-soft text-violet", "bg-success-soft text-success", "bg-warning-soft text-warning"];

function hash(text: string): number {
  return text.split("").reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
}

/** Initials for people; a robot mark for agents, so the two are never confused. */
export function Avatar({ name, agent, size = "md", className }: { name: string; agent?: boolean; size?: "sm" | "md" | "lg"; className?: string }) {
  const dims = { sm: "size-6 text-2xs", md: "size-8 text-xs", lg: "size-11 text-sm" }[size];
  const initials = name.split(/\s+/).filter((w) => /^[A-Za-z]/.test(w)).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("");
  return (
    <span aria-hidden className={cn("grid shrink-0 place-items-center font-semibold", agent ? "rounded-lg" : "rounded-full", dims, PALETTE[hash(name) % PALETTE.length], className)}>
      {agent ? <Bot className={size === "lg" ? "size-5" : "size-4"} /> : initials}
    </span>
  );
}
