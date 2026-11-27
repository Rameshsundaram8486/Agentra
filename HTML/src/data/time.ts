/* The demo's own clock. Seed data is placed relative to DEMO_START, so the story reads the same whenever the demo
   is opened. Shown in Gulf Standard Time (UTC+4). */

export const DEMO_START = Date.parse("2026-11-26T06:00:00Z"); // 10:00 in the UAE

const HOUR = 3_600_000;

/** Simulated seconds per simulation tick (one real second at 1x speed). */
export const TICK_SECONDS = 20;

/** An ISO time `hours` from the demo start (negative is in the past). */
export function at(hours: number): string {
  return new Date(DEMO_START + hours * HOUR).toISOString();
}

/** An ISO time `days` from the demo start, at 09:00 UAE time. */
export function day(days: number): string {
  const date = new Date(DEMO_START + days * 24 * HOUR);
  date.setUTCHours(5, 0, 0, 0);
  return date.toISOString();
}

export function addSeconds(iso: string, seconds: number): string {
  return new Date(Date.parse(iso) + seconds * 1000).toISOString();
}

export function secondsBetween(from: string, to: string): number {
  return Math.max(0, Math.round((Date.parse(to) - Date.parse(from)) / 1000));
}
