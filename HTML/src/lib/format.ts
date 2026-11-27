/* Formatting for display. Times are shown in UAE time (Gulf Standard Time) and relative to the simulated clock. */

const TIME_ZONE = "Asia/Dubai";
const time = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: TIME_ZONE });
const date = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: TIME_ZONE });
const dateYear = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: TIME_ZONE });

export function formatTime(iso: string): string {
  return time.format(new Date(iso));
}

export function formatDate(iso: string, withYear = false): string {
  return (withYear ? dateYear : date).format(new Date(iso));
}

export function formatDateTime(iso: string): string {
  return `${formatDate(iso)}, ${formatTime(iso)}`;
}

/** "just now", "12 min ago", "3 h ago", "2 days ago"; "in 2 days" for the future. */
export function relative(iso: string, now: string): string {
  const seconds = Math.round((Date.parse(now) - Date.parse(iso)) / 1000);
  const future = seconds < 0;
  const s = Math.abs(seconds);
  const text = s < 60 ? "just now" : s < 3600 ? `${Math.round(s / 60)} min` : s < 86_400 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 86_400)} day${Math.round(s / 86_400) === 1 ? "" : "s"}`;
  if (text === "just now") return text;
  return future ? `in ${text}` : `${text} ago`;
}

export function duration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s`;
  return `${Math.floor(seconds / 3600)}h ${String(Math.floor((seconds % 3600) / 60)).padStart(2, "0")}m`;
}

export function aed(amount: number): string {
  return amount >= 1_000_000 ? `AED ${(amount / 1_000_000).toFixed(2)}M` : `AED ${Math.round(amount / 1000)}K`;
}

export function number(value: number): string {
  return new Intl.NumberFormat("en-GB").format(value);
}

export function usd(value: number): string {
  return `$${value.toFixed(2)}`;
}
