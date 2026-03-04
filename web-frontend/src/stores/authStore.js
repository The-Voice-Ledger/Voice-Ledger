import { create } from 'zustand'

/**
 * Auth store - JWT token + user info persisted to localStorage.
 */
const useAuthStore = create((set) => ({
  token: localStorage.getItem('vl_token') || null,
  user: JSON.parse(localStorage.getItem('vl_user') || 'null'),
  isAuthenticated: !!localStorage.getItem('vl_token'),

  login: (token, user) => {
    localStorage.setItem('vl_token', token)
    localStorage.setItem('vl_user', JSON.stringify(user))
    set({ token, user, isAuthenticated: true })
  },

  logout: () => {
    localStorage.removeItem('vl_token')
    localStorage.removeItem('vl_user')
    set({ token: null, user: null, isAuthenticated: false })
  },
}))

// Listen for auth-expired events (from api client)
if (typeof window !== 'undefined') {
  window.addEventListener('vl:auth-expired', () => {
    useAuthStore.getState().logout()
  })
}

export default useAuthStore
