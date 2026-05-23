import { create } from "zustand";

export type ToastType = "info" | "success" | "warn" | "danger";

export interface Toast {
  id:      string;
  type:    ToastType;
  title:   string;
  message?: string;
}

interface ToastStore {
  toasts: Toast[];
  add:    (t: Omit<Toast, "id">) => void;
  remove: (id: string) => void;
}

let _seq = 0;

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],

  add: (t) => {
    const id = `toast-${++_seq}`;
    set((s) => ({ toasts: [...s.toasts, { ...t, id }].slice(-5) }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) }));
    }, 4500);
  },

  remove: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

// Convenience helpers
export const toast = {
  success: (title: string, message?: string) =>
    useToastStore.getState().add({ type: "success", title, message }),
  info: (title: string, message?: string) =>
    useToastStore.getState().add({ type: "info", title, message }),
  warn: (title: string, message?: string) =>
    useToastStore.getState().add({ type: "warn", title, message }),
  danger: (title: string, message?: string) =>
    useToastStore.getState().add({ type: "danger", title, message }),
};
