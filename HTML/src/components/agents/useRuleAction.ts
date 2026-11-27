import { useState } from "react";
import { DemoRuleError } from "@/store/actions";

/** Runs a command and keeps the rule it broke (if any) to show beside the control. */
export function useRuleAction(): { error: string | null; done: string | null; run: (action: () => void, success?: string) => void; clear: () => void } {
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  return {
    error,
    done,
    run: (action, success) => {
      try {
        action();
        setError(null);
        setDone(success ?? null);
      } catch (failure) {
        setDone(null);
        setError(failure instanceof DemoRuleError ? failure.message : String(failure));
      }
    },
    clear: () => {
      setError(null);
      setDone(null);
    },
  };
}
