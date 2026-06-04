import client from './client'

export interface AuthUser {
  email:    string
  name:     string
  is_admin?: boolean
}

export interface AuthResponse {
  token:    string
  email:    string
  name:     string
  is_admin: boolean
}

const TOKEN_KEY = 'insightsai_token'
const USER_KEY = 'insightsai_user'

// ── Token helpers ─────────────────────────────────────────────────────────

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function getStoredUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try { return JSON.parse(raw) as AuthUser } catch { return null }
}

export function storeSession(token: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  // Remove legacy name-only key if present
  localStorage.removeItem('insightsai_username')
}

// ── API calls ─────────────────────────────────────────────────────────────

export async function signup(name: string, email: string, password: string): Promise<AuthUser> {
  const { data } = await client.post<AuthResponse>('/auth/signup', { name, email, password })
  const user: AuthUser = { email: data.email, name: data.name, is_admin: data.is_admin }
  storeSession(data.token, user)
  return user
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const { data } = await client.post<AuthResponse>('/auth/login', { email, password })
  const user: AuthUser = { email: data.email, name: data.name, is_admin: data.is_admin }
  storeSession(data.token, user)
  return user
}

export async function logout(): Promise<void> {
  const token = getStoredToken()
  if (token) {
    try {
      await client.post('/auth/logout', {}, {
        headers: { Authorization: `Bearer ${token}` },
      })
    } catch { /* ignore server errors on logout */ }
  }
  clearSession()
}

export interface UpdateCredentialsPayload {
  current_password: string
  name?:            string
  email?:           string
  new_password?:    string
}

export async function updateCredentials(payload: UpdateCredentialsPayload): Promise<void> {
  const token = getStoredToken()
  await client.patch('/auth/me', payload, {
    headers: { Authorization: `Bearer ${token}` },
  })
  // Token is invalidated server-side; clear local session too
  clearSession()
}

export async function getCurrentUser(): Promise<AuthUser | null> {
  const token = getStoredToken()
  if (!token) return null
  try {
    const { data } = await client.get<AuthUser>('/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    })
    // Refresh stored user to pick up any is_admin changes
    storeSession(token, data)
    return data
  } catch {
    clearSession()
    return null
  }
}
