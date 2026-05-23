import { create } from "zustand";

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  tenant_id: string | null;
  roles: string[];
  permissions: string[];
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  isLoading: boolean;
  setSession: (user: AuthUser, accessToken: string) => void;
  clearSession: () => void;
  setLoading: (v: boolean) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user:        null,
  accessToken: null,
  isLoading:   true,
  setSession:  (user, accessToken) => set({ user, accessToken, isLoading: false }),
  clearSession: ()                 => set({ user: null, accessToken: null, isLoading: false }),
  setLoading:  (v)                 => set({ isLoading: v }),
}));
