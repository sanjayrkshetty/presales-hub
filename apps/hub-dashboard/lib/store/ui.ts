"use client";
import { create } from "zustand";

interface UIStore {
  sidebarCollapsed:   boolean;
  copilotOpen:        boolean;
  commandPaletteOpen: boolean;
  selectedProposalId: string | null;
  activePanel:        string | null;

  toggleSidebar:        () => void;
  setSidebarCollapsed:  (v: boolean) => void;
  toggleCopilot:        () => void;
  setCopilotOpen:       (v: boolean) => void;
  toggleCommandPalette: () => void;
  setCommandPaletteOpen:(v: boolean) => void;
  setSelectedProposal:  (id: string | null) => void;
  setActivePanel:       (panel: string | null) => void;
}

export const useUIStore = create<UIStore>((set) => ({
  sidebarCollapsed:   false,
  copilotOpen:        false,
  commandPaletteOpen: false,
  selectedProposalId: null,
  activePanel:        null,

  toggleSidebar:        () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarCollapsed:  (v) => set({ sidebarCollapsed: v }),
  toggleCopilot:        () => set((s) => ({ copilotOpen: !s.copilotOpen })),
  setCopilotOpen:       (v) => set({ copilotOpen: v }),
  toggleCommandPalette: () => set((s) => ({ commandPaletteOpen: !s.commandPaletteOpen })),
  setCommandPaletteOpen:(v) => set({ commandPaletteOpen: v }),
  setSelectedProposal:  (id) => set({ selectedProposalId: id }),
  setActivePanel:       (panel) => set({ activePanel: panel }),
}));
