/**
 * Theme preference store.
 *
 * Persists the user's light/dark theme selection to localStorage so the chosen
 * theme is reapplied on subsequent visits (Req 12.27). Switching is applied
 * immediately without a page reload (Req 12.28).
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
export const useThemeStore = create()(persist((set) => ({
    mode: 'light',
    setMode: (mode) => set({ mode }),
    toggleMode: () => set((state) => ({ mode: state.mode === 'light' ? 'dark' : 'light' })),
}), {
    name: 'mdaa-theme-preference',
}));
