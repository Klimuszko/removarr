import React, { useEffect, useState } from 'react'
import {
  addAccount, deleteAccount, health, info, listAccounts, logs,
  type Account, type LogsItem, authStatus, setupAdmin, login, logout,
  oauthStart, oauthStatus, authPing
} from './api'

function tsToLocal(ts: number) {
  const d = new Date(ts * 1000)
  return d.toLocaleString()
}

function isoToLocal(iso?: string | null) {
  if (!iso) return '-'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? '-' : d.toLocaleString()
}

export default function App() {
  const [healthState, setHealthState] = useState<any>(null)
  const [infoState, setInfoState] = useState<any>(null)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [logItems, setLogItems] = useState<LogsItem[]>([])

  const [hasAdmin, setHasAdmin] = useState<boolean | null>(null)
  const [authed, setAuthed] = useState<boolean>(false)

  const [setupUser, setSetupUser] = useState('')
  const [setupPass, setSetupPass] = useState('')
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')

  const [label, setLabel] = useState('')
  const [plexToken, setPlexToken] = useState('')
  const [err, setErr] = useState<string>('')

  const [oauthFlow, setOauthFlow] = useState<{ flow_id: string; url: string } | null>(null)
  const [oauthMsg, setOauthMsg] = useState<string>('')

  async function refreshHealth() {
    try { setHealthState(await health()) } catch (e: any) { setErr(String(e?.message || e)) }
  }
  async function refreshAuthStatus() {
    try { setHasAdmin((await authStatus()).has_admin) } catch (e: any) { setErr(String(e?.message || e)) }
  }

  async function refreshProtected() {
    try {
      setInfoState(await info())
      setAccounts(await listAccounts())
      setLogItems((await logs()).items)
      setAuthed(true)
    }
    catch (e: any) {
      setAuthed(false)
      setErr(String(e?.message || e))
    }
  }

  useEffect(() => {
    refreshHealth()
    refreshAuthStatus()
  }, [])

  useEffect(() => {
    if (hasAdmin === true) refreshProtected()
  }, [hasAdmin])

  useEffect(() => {
    const t = setInterval(() => { if (authed) refreshProtected() }, 4000)
    return () => clearInterval(t)
  }, [authed])

  async function onSetup() {
    setErr('')
    try {
      if (setupUser.trim().length < 3) { setErr('Username min 3 znaki.'); return }
      if (setupPass.trim().length < 8) { setErr('Hasło min 8 znaków.'); return }
      await setupAdmin(setupUser.trim(), setupPass.trim())
      await refreshAuthStatus()
      await login(setupUser.trim(), setupPass.trim())
      setSetupUser(''); setSetupPass('')
      await refreshProtected()
    } catch (e: any) {
      setErr(String(e?.message || e))
    }
  }

  async function onLogin() {
  setErr('')
  try {
    await login(loginUser.trim(), loginPass)
    setLoginPass('')
    await authPing()
    await refreshProtected()
  } catch (e: any) {
    setErr(String(e?.message || 'Błędny login lub problem z autoryzacją.'))
  }
}

async function onLogout() {
    setErr('')
    try {
      await logout()
      localStorage.removeItem('removarr_token')
      setAuthed(false)
      setInfoState(null)
      setAccounts([])
      setLogItems([])
    } catch (e: any) {
      setErr(String(e?.message || e))
    }
  }

  async function onAddAccount() {
    setErr('')
    try {
      if (!label.trim() || !plexToken.trim()) { setErr('Podaj label i Plex token.'); return }
      await addAccount(label.trim(), plexToken.trim())
      setLabel('')
      setPlexToken('')
      await refreshProtected()
    } catch (e: any) {
      setErr(String(e?.message || e))
    }
  }

  async function onDelete(id: number) {
    setErr('')
    try { await deleteAccount(id); await refreshProtected() } catch (e: any) { setErr(String(e?.message || e)) }
  }

  async function onOauthConnect() {
    setErr('')
    setOauthMsg('')
    try {
      const f = await oauthStart()
      setOauthFlow(f)
      window.open(f.url, '_blank', 'noopener,noreferrer')
      setOauthMsg('Otworzyłem okno logowania Plex. Po zalogowaniu wróć tutaj — Removarr sam doda konto.')
    } catch (e: any) {
      setErr(String(e?.message || e))
    }
  }

  // Poll OAuth flow status
  useEffect(() => {
    if (!oauthFlow) return
    let alive = true
    const poll = async () => {
      try {
        const st = await oauthStatus(oauthFlow.flow_id)
        if (!alive) return
        if (st.status === 'pending') {
          setOauthMsg('Czekam na autoryzację w Plex…')
          setTimeout(poll, 1200)
        } else if (st.status === 'ok') {
          setOauthMsg(`Połączono: ${st.label} (accountId=${st.account_id})`)
          setOauthFlow(null)
          await refreshProtected()
        } else {
          setOauthMsg(st.message || `OAuth: ${st.status}`)
          setOauthFlow(null)
        }
      } catch (e: any) {
        if (!alive) return
        setOauthMsg(String(e?.message || e))
        setOauthFlow(null)
      }
    }
    poll()
    return () => { alive = false }
  }, [oauthFlow])

  const webhookHeader = infoState?.webhook?.header || 'X-Removarr-Webhook-Token'
  const radarrPath = infoState?.webhook?.radarr_path || '/webhook/radarr'
  const sonarrPath = infoState?.webhook?.sonarr_path || '/webhook/sonarr'
  const acceptedEvent = infoState?.webhook?.accepted_eventType || 'Download'

  const statusDot = (s: string) => {
    if (s === 'ok') return 'ok'
    if (s === 'invalid') return 'bad'
    return ''
  }

  return (
    <div className="container">
      <div className="header">
        <div>
          <div className="h1">Removarr</div>
          <div className="small">Remove from Plex Watchlist when Radarr/Sonarr IMPORT (eventType=Download).</div>
        </div>
        <div className="row">
          <span className="badge">
            <span className={"dot " + (healthState?.ok ? "ok" : "bad")}></span>
            Health: {healthState?.ok ? "OK" : "?"}
          </span>
          <span className="badge">
            Verify in Plex: {String(healthState?.verify_in_plex ?? '?')}
          </span>
          {authed ? <button className="danger" onClick={onLogout}>Wyloguj</button> : null}
        </div>
      </div>

      {err ? <div className="card" style={{borderColor: 'rgba(255,92,92,0.35)'}}><b>Błąd:</b> <span className="mono">{err}</span></div> : null}

      {hasAdmin === false ? (
        <div className="card">
          <div className="cardTitle">Pierwsze uruchomienie — utwórz konto admina</div>
          <div className="small">Konto admina tworzy się tylko raz. Potem używasz logowania.</div>
          <div style={{height: 10}}></div>
          <div className="col">
            <input placeholder="Username" value={setupUser} onChange={e => setSetupUser(e.target.value)} />
            <input type="password" placeholder="Hasło (min 8 znaków)" value={setupPass} onChange={e => setSetupPass(e.target.value)} />
            <button onClick={onSetup}>Utwórz admina</button>
          </div>
        </div>
      ) : null}

      {hasAdmin === true && !authed ? (
        <div className="card">
          <div className="cardTitle">Logowanie</div>
          <div className="small">Zaloguj się kontem admina, aby zarządzać Removarr.</div>
          <div style={{height: 10}}></div>
          <div className="col">
            <input placeholder="Username" value={loginUser} onChange={e => setLoginUser(e.target.value)} />
            <input type="password" placeholder="Hasło" value={loginPass} onChange={e => setLoginPass(e.target.value)} />
            <button onClick={onLogin}>Zaloguj</button>
          </div>
        </div>
      ) : null}

      {authed ? (
        <div className="grid">
          <div className="col">
            <div className="card">
              <div className="cardTitle">Webhook endpoints</div>
              <div className="small">Radarr/Sonarr webhook musi wysyłać <span className="mono">eventType={acceptedEvent}</span> — inne eventy są ignorowane.</div>
              <div style={{height: 10}}></div>
              <div className="col">
                <div>
                  <div className="small">Radarr URL</div>
                  <div className="mono">{location.origin}{radarrPath}</div>
                </div>
                <div>
                  <div className="small">Sonarr URL</div>
                  <div className="mono">{location.origin}{sonarrPath}</div>
                </div>
                <div>
                  <div className="small">Wymagany nagłówek</div>
                  <div className="mono">{webhookHeader}: &lt;REMOVARR_WEBHOOK_TOKEN&gt;</div>
                </div>
              </div>
            </div>

            <div className="card">
              <div className="cardTitle">Połącz konto Plex</div>
              <div className="small">Opcja zalecana: Plex OAuth (nie wklejasz tokena). Po połączeniu konto zostanie dodane automatycznie.</div>
              <div style={{height: 10}}></div>
              <button onClick={onOauthConnect}>Connect with Plex</button>
              {oauthMsg ? <div className="footerNote">{oauthMsg}</div> : null}
            </div>

            <div className="card">
              <div className="cardTitle">Dodaj konto Plex ręcznie</div>
              <div className="small">Fallback: wklej token. Removarr sprawdzi token od razu.</div>
              <div style={{height: 10}}></div>
              <div className="col">
                <input placeholder="Label (np. Kuba)" value={label} onChange={e => setLabel(e.target.value)} />
                <input className="mono" placeholder="Plex token (X-Plex-Token)" value={plexToken} onChange={e => setPlexToken(e.target.value)} />
                <button onClick={onAddAccount}>Dodaj</button>
              </div>
            </div>
          </div>

          <div className="col">
            <div className="card">
              <div className="cardTitle">Konta Plex</div>
              <div className="small">Status jest sprawdzany raz dziennie + natychmiast, jeśli polecą błędy przy usuwaniu.</div>
              <div style={{height: 10}}></div>
              <table className="table">
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Label</th>
                    <th>Method</th>
                    <th>Last check</th>
                    <th>Error</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.length === 0 ? (
                    <tr><td colSpan={6} className="small">Brak kont. Dodaj po lewej.</td></tr>
                  ) : accounts.map(a => (
                    <tr key={a.id}>
                      <td>
                        <span className="badge">
                          <span className={"dot " + statusDot(a.status)}></span>
                          <span className="mono">{a.status}</span>
                        </span>
                      </td>
                      <td>{a.label}<div className="small mono">id:{a.id}</div></td>
                      <td className="mono">{a.auth_method}</td>
                      <td className="mono">{isoToLocal(a.last_check_at)}</td>
                      <td className="small mono">{a.last_error ? a.last_error.slice(0, 80) : '-'}</td>
                      <td style={{textAlign:'right'}}>
                        <button className="danger" onClick={() => onDelete(a.id)}>Usuń</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="card">
              <div className="cardTitle">Ostatnie webhooki</div>
              <div className="small">Eventy inne niż <span className="mono">{acceptedEvent}</span> będą widoczne jako „Ignored”.</div>
              <div style={{height: 10}}></div>
              <table className="table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Source</th>
                    <th>Title</th>
                    <th>Removed</th>
                  </tr>
                </thead>
                <tbody>
                  {logItems.length === 0 ? (
                    <tr><td colSpan={4} className="small">Brak logów. Wyślij testowy webhook z Radarr/Sonarr.</td></tr>
                  ) : logItems.slice(0, 12).map((x, idx) => (
                    <tr key={idx}>
                      <td className="mono">{tsToLocal(x.ts)}</td>
                      <td className="mono">{x.source}</td>
                      <td>
                        <div>{x.title} {x.year ? <span className="small">({x.year})</span> : null}</div>
                        <div className="small mono">
                          {x.tmdb_id ? `tmdb:${x.tmdb_id} ` : ''}{x.tvdb_id ? `tvdb:${x.tvdb_id}` : ''}
                        </div>
                      </td>
                      <td className="mono">{x.removed}/{x.scanned_accounts}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {logItems.length > 0 ? (
                <div className="footerNote">
                  Szczegóły (ostatni):<br/>
                  <div className="mono" style={{whiteSpace:'pre-wrap'}}>{(logItems[0].details || []).join("\n")}</div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
