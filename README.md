# Removarr

Removarr is a self-hosted service that removes items from **Plex Watchlists** once **Sonarr/Radarr** report a **successful import** (`eventType=Download`). It’s designed for shared Plex libraries where multiple Plex accounts add to Watchlist and you want entries to disappear automatically after the item is actually in your library.

✅ Web UI included  
✅ First-run admin setup (username + password)  
✅ Add Plex accounts via **Plex OAuth** or **manual token**  
✅ Daily account status checks + instant invalidation on auth errors  
✅ Docker / GHCR friendly

---

## How it works

- Sonarr/Radarr sends a webhook when an item is **imported** (not when download starts).
- Removarr checks all linked Plex accounts and removes the matching item from their Watchlists.
- If a Plex token becomes invalid, Removarr marks the account as `invalid` (visible in UI).

---

## Quick start (Docker)

### 1) Required env vars

- `REMOVARR_SECRET_KEY` — encrypts stored Plex tokens (Fernet key)
- `REMOVARR_WEBHOOK_TOKEN` — protects webhook endpoints
- `REMOVARR_DB_URL` — database url (SQLite by default)

Generate your own Fernet key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
