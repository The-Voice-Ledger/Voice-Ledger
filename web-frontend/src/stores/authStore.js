import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/**
 * Auth store - JWT token + user info persisted to localStorage.
 */
const useAuthStore = create(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isAuthenticated: false,

      login: (token, user) => {
        console.log('🔍 AuthStore.login called:', { token: token?.substring(0, 20) + '...', user })
        set({ token, user, isAuthenticated: true })
      },

      logout: () => {
        console.log('🔍 AuthStore.logout called')
        set({ token: null, user: null, isAuthenticated: false })
      },

      // Debug method to check current state
      debugState: () => {
        const state = get()
        console.log('🔍 AuthStore current state:', {
          token: state.token ? state.token.substring(0, 20) + '...' : null,
          user: state.user,
          isAuthenticated: state.isAuthenticated
        })
        return state
      },

      // Force sync from localStorage (for Railway deployment)
      syncFromStorage: () => {
        console.log('🔍 AuthStore.syncFromStorage called')
        // Zustand persist handles this automatically, but we can trigger rehydration
        const persistedState = localStorage.getItem('voice-ledger-auth')
        if (persistedState) {
          try {
            const parsed = JSON.parse(persistedState)
            console.log('🔍 AuthStore.syncFromStorage - parsed from localStorage:', {
              token: parsed.state?.token ? parsed.state.token.substring(0, 20) + '...' : null,
              user: parsed.state?.user,
              isAuthenticated: parsed.state?.isAuthenticated
            })
            set({
              token: parsed.state?.token || null,
              user: parsed.state?.user || null,
              isAuthenticated: parsed.state?.isAuthenticated || false
            })
          } catch (error) {
            console.error('🔍 AuthStore.syncFromStorage - error parsing:', error)
          }
        }
      },
    }),
    {
      name: 'voice-ledger-auth',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        console.log('🔍 AuthStore rehydrated from localStorage:', {
          token: state?.token ? state.token.substring(0, 20) + '...' : null,
          user: state?.user,
          isAuthenticated: state?.isAuthenticated
        })
      },
    }
  )
)

export default useAuthStore
