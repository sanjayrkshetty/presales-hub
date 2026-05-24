"use client";
import { useState, useEffect, useCallback } from "react";

interface Preferences {
  executiveAutoRefresh:   boolean;
  analyticsTimeRange:     number;
  sidebarCollapsed:       boolean;
  executivePresentMode:   boolean;
}

const DEFAULTS: Preferences = {
  executiveAutoRefresh:  true,
  analyticsTimeRange:    30,
  sidebarCollapsed:      false,
  executivePresentMode:  false,
};

const KEY = "hub_preferences";

function load(): Preferences {
  if (typeof window === "undefined") return DEFAULTS;
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : DEFAULTS;
  } catch {
    return DEFAULTS;
  }
}

export function usePreferences() {
  const [prefs, setPrefs] = useState<Preferences>(DEFAULTS);

  useEffect(() => {
    setPrefs(load());
  }, []);

  const update = useCallback((patch: Partial<Preferences>) => {
    setPrefs((prev) => {
      const next = { ...prev, ...patch };
      try {
        localStorage.setItem(KEY, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  return { prefs, update };
}
