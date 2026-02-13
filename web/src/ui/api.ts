export type Account = {
  id: number
  label: string
  auth_method: string
  status: string
  last_check_at?: string | null
  last_ok_at?: string | null
  last_error?: string | null
}

export type LogsItem = {
  ts: number
  source: string
  title: string
  year?: number | null
  tmdb_id?: number | null
  tvdb_id?: number | null
  removed: number
  scanned_accounts: number
  details: string[]
}


function authHeaders() {
  const token = localStorage.getItem('removarr_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function jfetch(path: string, init?: RequestInit) {
  const headers = { ...(init?.headers || {}), ...authHeaders() }
  const r = await fetch(path, { credentials: 'include', ...init, headers })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t)
  }
  return r.json()
}

export async function health() {
  const r = await fetch('/health')
  return r.json()
}

export async function authStatus(): Promise<{ has_admin: boolean }> {
  return jfetch('/api/auth/status')
}

export async function setupAdmin(username: string, password: string) {
  return jfetch('/api/auth/setup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
}

export async function login(username: string, password: string) {
  const res = await jfetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (res?.token) localStorage.setItem('removarr_token', res.token)
  return res
}

export async function logout() {
  localStorage.removeItem('removarr_token')
  return jfetch('/api/auth/logout', { method: 'POST' })
}

export async function info() {
  return jfetch('/api/info')
}

export async function listAccounts(): Promise<Account[]> {
  return jfetch('/api/accounts')
}

export async function addAccount(label: string, plex_token: string): Promise<Account> {
  return jfetch('/api/accounts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label, plex_token }),
  })
}

export async function deleteAccount(id: number): Promise<void> {
  await jfetch(`/api/accounts/${id}`, { method: 'DELETE' })
}

export async function logs(): Promise<{ items: LogsItem[] }> {
  return jfetch('/api/logs')
}

export async function oauthStart(): Promise<{ flow_id: string; url: string }> {
  return jfetch('/api/plex/oauth/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) })
}

export async function oauthStatus(flow_id: string): Promise<{ flow_id: string; status: string; message?: string; account_id?: number; label?: string }> {
  return jfetch(`/api/plex/oauth/status/${encodeURIComponent(flow_id)}`)
}
