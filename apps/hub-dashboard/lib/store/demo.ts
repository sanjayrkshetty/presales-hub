import { create } from "zustand";
import { useRealtimeStore } from "./realtime";
import { useNotificationStore } from "./notifications";

interface DemoStore {
  isDemoMode: boolean;
  resetCount: number;
  setDemoMode: (v: boolean) => void;
  demoReset:   () => void;
}

export const useDemoStore = create<DemoStore>((set) => ({
  isDemoMode: false,
  resetCount: 0,
  setDemoMode: (v) => set({ isDemoMode: v }),
  demoReset: () => {
    useRealtimeStore.getState().clearLog();
    useNotificationStore.getState().markAllRead();
    set((s) => ({ resetCount: s.resetCount + 1 }));
  },
}));
