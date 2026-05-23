"use client";
import { create } from "zustand";

export interface Notification {
  id:         string;
  type:       "info" | "warn" | "danger" | "success";
  title:      string;
  message:    string;
  read:       boolean;
  created_at: string;
  proposal_id?: string;
}

interface NotificationStore {
  notifications: Notification[];
  unreadCount:   number;

  addNotification: (n: Omit<Notification, "id" | "read" | "created_at">) => void;
  markRead:        (id: string) => void;
  markAllRead:     () => void;
  dismiss:         (id: string) => void;
}

let _seq = 0;

export const useNotificationStore = create<NotificationStore>((set) => ({
  notifications: [],
  unreadCount:   0,

  addNotification: (n) =>
    set((s) => {
      const note: Notification = { ...n, id: `n${++_seq}`, read: false, created_at: new Date().toISOString() };
      const notifications = [note, ...s.notifications].slice(0, 50);
      return { notifications, unreadCount: notifications.filter((x) => !x.read).length };
    }),

  markRead: (id) =>
    set((s) => {
      const notifications = s.notifications.map((n) => n.id === id ? { ...n, read: true } : n);
      return { notifications, unreadCount: notifications.filter((x) => !x.read).length };
    }),

  markAllRead: () =>
    set((s) => ({
      notifications: s.notifications.map((n) => ({ ...n, read: true })),
      unreadCount: 0,
    })),

  dismiss: (id) =>
    set((s) => {
      const notifications = s.notifications.filter((n) => n.id !== id);
      return { notifications, unreadCount: notifications.filter((x) => !x.read).length };
    }),
}));
