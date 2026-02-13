# Removarr (Fullstack)

Self-hosted service that removes items from **Plex Watchlists** when **Radarr/Sonarr** report that an item is **imported** (i.e., present in Sonarr/Radarr library).

Includes a built-in **web UI** (SPA) to configure everything.

## Key behavior

- Webhook events are **processed only** when `eventType == "Download"` (import done).  
  Other events (e.g. `Grab`) are ignored.
- Plex accounts can be linked via:
  - **Plex OAuth / PIN flow** (recommended) — no manual token handling
  - **Manual token** (fallback)
- Account link **status**:
  - Verified **once per day** in the background
  - Also flips to **INVALID** immediately if Removarr starts receiving auth errors during normal operations

## First-run admin setup

On the first run, open the UI and create the **admin account (username + password)**.
After that, you must login to manage settings.

## Run with Docker

See `docker-compose.yml.example`.

### Required env vars

- `REMOVARR_SECRET_KEY` (required) Fernet key used to encrypt Plex tokens at rest  
  Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

### Configure Radarr/Sonarr webhooks

- URL:
  - `http://removarr:8765/webhook/radarr`
  - `http://removarr:8765/webhook/sonarr`
- Header:
  - `X-Removarr-Webhook-Token: <REMOVARR_WEBHOOK_TOKEN>`

## License
MIT


### Fixes
- Session expiry check compares datetimes as naive UTC to avoid SQLite tz mismatch.
