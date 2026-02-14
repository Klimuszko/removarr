from __future__ import annotations

from typing import Optional
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
import asyncio
import secrets

from fastapi import FastAPI, Depends, HTTPException, Header, Request, Response, Cookie
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, update

from .config import settings
from .db import Base, make_engine, make_session_factory
from .models import PlexAccount, AppSetting
from .crypto import Crypto
from .schemas import (
    AccountCreate, AccountOut, WebhookResult, SetupAdmin, LoginReq,
    OAuthStartReq, OAuthStartRes, OAuthStatusRes
)
from .plex_client import PlexOps
from .logring import LogRing, LogItem
from .auth import COOKIE_NAME, has_admin, create_admin, login as do_login, logout as do_logout, validate_session
from .plex_oauth import PlexOAuthManager

engine = make_engine(settings.db_url)
SessionLocal = make_session_factory(engine)
Base.metadata.create_all(bind=engine)

crypto = Crypto(settings.secret_key)
plex_ops = PlexOps(settings.plex_base_url, settings.plex_server_token)
logring = LogRing(maxlen=400)
oauth_mgr = PlexOAuthManager()

STATIC_DIR = Path(__file__).parent / "static"
app = FastAPI(title="Removarr", version="0.4.11")

# ---- DB helpers ----
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def require_auth(
    authorization: Optional[str] = Header(default=None),
    removarr_session: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
):
    # Prefer Bearer token (works even if browser blocks cookies)
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token and validate_session(db, token):
            return

    # Fallback to cookie-based session
    if removarr_session and validate_session(db, removarr_session):
        return

    raise HTTPException(status_code=401, detail="Unauthorized")


def require_webhook(
    x_removarr_webhook_token: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    current = get_setting(db, "webhook_token") or settings.webhook_token
    if x_removarr_webhook_token != current:
        raise HTTPException(status_code=401, detail="Unauthorized (webhook token)")

def _dt_to_iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    try:
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None

def _account_out(a: PlexAccount) -> AccountOut:
    return AccountOut(
        id=a.id,
        label=a.label,
        auth_method=getattr(a, "auth_method", "manual") or "manual",
        status=getattr(a, "status", "unknown") or "unknown",
        last_check_at=_dt_to_iso(getattr(a, "last_check_at", None)),
        last_ok_at=_dt_to_iso(getattr(a, "last_ok_at", None)),
        last_error=getattr(a, "last_error", None),
    )

@app.get("/health")
def health():
    return {"ok": True, "verify_in_plex": settings.verify_in_plex}

def get_setting(db: Session, key: str) -> Optional[str]:
    row = db.execute(select(AppSetting).where(AppSetting.key == key)).scalars().first()
    return row.value if row else None

def set_setting(db: Session, key: str, value: str) -> None:
    row = db.execute(select(AppSetting).where(AppSetting.key == key)).scalars().first()
    if row:
        row.value = value
    else:
        row = AppSetting(key=key, value=value)
        db.add(row)
    db.commit()

# ---- Auth ----
@app.get("/api/auth/status")
def auth_status(db: Session = Depends(get_db)):
    return {"has_admin": has_admin(db)}

@app.post("/api/auth/setup")
def auth_setup(payload: SetupAdmin, db: Session = Depends(get_db)):
    try:
        create_admin(db, payload.username, payload.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "token": token}
@app.post("/api/auth/login")
def auth_login(payload: LoginReq, response: Response, db: Session = Depends(get_db)):
    try:
        token = do_login(db, payload.username, payload.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # set True behind HTTPS reverse proxy
        max_age=60 * 60 * 24 * 30,
        path="/",
    )
    return {"ok": True, "token": token}
@app.post("/api/auth/logout", dependencies=[Depends(require_auth)])
def auth_logout(response: Response, removarr_session: Optional[str] = Cookie(default=None), db: Session = Depends(get_db)):
    if removarr_session:
        do_logout(db, removarr_session)
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True, "token": token}


@app.get("/api/auth/ping", dependencies=[Depends(require_auth)])
def auth_ping():
    return {"ok": True}

# ---- Plex OAuth connect ----
@app.post("/api/plex/oauth/start", response_model=OAuthStartRes, dependencies=[Depends(require_auth)])
def plex_oauth_start(payload: OAuthStartReq):
    flow_id = secrets.token_urlsafe(16)
    url = oauth_mgr.start(flow_id)
    return OAuthStartRes(flow_id=flow_id, url=url)

@app.get("/api/plex/oauth/status/{flow_id}", response_model=OAuthStatusRes, dependencies=[Depends(require_auth)])
def plex_oauth_status(flow_id: str, db: Session = Depends(get_db)):
    status, token = oauth_mgr.poll(flow_id)
    if status == "pending":
        return OAuthStatusRes(flow_id=flow_id, status="pending")
    if status == "expired":
        return OAuthStatusRes(flow_id=flow_id, status="expired", message="Login expired or unknown flow id.")
    if status == "error":
        return OAuthStatusRes(flow_id=flow_id, status="error", message="OAuth polling error.")

    # status == ok => token received
    assert token is not None
    ok, msg = plex_ops.validate_user_token(token)
    if not ok:
        return OAuthStatusRes(flow_id=flow_id, status="error", message=f"Token received but validation failed: {msg}")

    # Use Plex username as default label; if collision, append a suffix.
    label = msg or "PlexUser"
    existing = db.execute(select(PlexAccount).where(PlexAccount.label == label)).scalars().first()
    if existing:
        label = f"{label}-{int(time.time())}"

    acc = PlexAccount(
        label=label,
        token_enc=crypto.encrypt(token),
        auth_method="oauth",
        status="ok",
        last_check_at=datetime.now(timezone.utc),
        last_ok_at=datetime.now(timezone.utc),
        last_error=None,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return OAuthStatusRes(flow_id=flow_id, status="ok", account_id=acc.id, label=acc.label)

# ---- Protected API ----
@app.get("/api/info", dependencies=[Depends(require_auth)])
def info():
    return {
        "webhook": {
            "radarr_path": "/webhook/radarr",
            "sonarr_path": "/webhook/sonarr",
            "header": "X-Removarr-Webhook-Token",
            "recommended_sonarr_event": "On Import Complete",
            "recommended_radarr_event": "On Import Complete",
        },
        "verify_in_plex": settings.verify_in_plex,
        "plex_base_url_set": bool(settings.plex_base_url),
        "plex_server_token_set": bool(settings.plex_server_token),
    }


@app.get("/api/settings/webhook-token", dependencies=[Depends(require_auth)])
def get_webhook_token(db: Session = Depends(get_db)):
    token = get_setting(db, "webhook_token") or settings.webhook_token
    source = "db" if get_setting(db, "webhook_token") else "env"
    return {"token": token, "source": source}

@app.post("/api/settings/webhook-token/regenerate", dependencies=[Depends(require_auth)])
def regenerate_webhook_token(db: Session = Depends(get_db)):
    token = secrets.token_urlsafe(32)
    set_setting(db, "webhook_token", token)
    return {"token": token}

@app.get("/api/logs", dependencies=[Depends(require_auth)])
def logs():
    return {"items": logring.list()}

@app.get("/api/accounts", response_model=list[AccountOut], dependencies=[Depends(require_auth)])
def list_accounts(db: Session = Depends(get_db)):
    rows = db.execute(select(PlexAccount).order_by(PlexAccount.id.asc())).scalars().all()
    return [_account_out(r) for r in rows]

@app.post("/api/accounts", response_model=AccountOut, dependencies=[Depends(require_auth)])
def add_account(payload: AccountCreate, db: Session = Depends(get_db)):
    # Manual token
    ok, msg = plex_ops.validate_user_token(payload.plex_token)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Invalid Plex token: {msg}")

    token_enc = crypto.encrypt(payload.plex_token)
    acc = PlexAccount(
        label=payload.label,
        token_enc=token_enc,
        auth_method="manual",
        status="ok",
        last_check_at=datetime.now(timezone.utc),
        last_ok_at=datetime.now(timezone.utc),
        last_error=None,
    )
    try:
        db.add(acc)
        db.commit()
        db.refresh(acc)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to add account: {e}")
    return _account_out(acc)

@app.delete("/api/accounts/{account_id}", dependencies=[Depends(require_auth)])
def delete_account(account_id: int, db: Session = Depends(get_db)):
    res = db.execute(delete(PlexAccount).where(PlexAccount.id == account_id))
    db.commit()
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}

def _get_accounts(db: Session):
    return db.execute(select(PlexAccount)).scalars().all()

def _mark_account_error(db: Session, acc_id: int, error: str):
    db.execute(
        update(PlexAccount)
        .where(PlexAccount.id == acc_id)
        .values(status="invalid", last_error=error[:1000], last_check_at=datetime.now(timezone.utc))
    )
    db.commit()

def _mark_account_ok(db: Session, acc_id: int):
    now = datetime.now(timezone.utc)
    db.execute(
        update(PlexAccount)
        .where(PlexAccount.id == acc_id)
        .values(status="ok", last_error=None, last_check_at=now, last_ok_at=now)
    )
    db.commit()

def _process(source: str, tmdb_id: Optional[int], tvdb_id: Optional[int], title: str, year: Optional[int], db: Session) -> WebhookResult:
    accounts = _get_accounts(db)

    if settings.verify_in_plex:
        ok_lib = plex_ops.is_available_in_library(tmdb_id=tmdb_id, tvdb_id=tvdb_id, title=title, year=year)
        if not ok_lib:
            res = WebhookResult(removed=0, scanned_accounts=len(accounts), details=[f"Skipped: not found in Plex library (verify enabled) for {title} ({year})"])
            logring.add(LogItem(ts=time.time(), source=source, title=title, year=year, tmdb_id=tmdb_id, tvdb_id=tvdb_id,
                               removed=res.removed, scanned_accounts=res.scanned_accounts, details=res.details))
            return res

    removed = 0
    details: list[str] = []
    for acc in accounts:
        try:
            token = crypto.decrypt(acc.token_enc)
            did, msg = plex_ops.remove_from_watchlist_if_present(
                user_token=token,
                tmdb_id=tmdb_id,
                tvdb_id=tvdb_id,
                title=title,
                year=year,
            )
            if did:
                removed += 1
            details.append(f"[{acc.label}] {msg}")
        except Exception as e:
            err = str(e)
            details.append(f"[{acc.label}] ERROR: {err}")
            # If auth broke, mark invalid immediately.
            if "401" in err or "Unauthorized" in err or "unauthorized" in err:
                _mark_account_error(db, acc.id, err)

    res = WebhookResult(removed=removed, scanned_accounts=len(accounts), details=details)
    logring.add(LogItem(ts=time.time(), source=source, title=title, year=year, tmdb_id=tmdb_id, tvdb_id=tvdb_id,
                       removed=res.removed, scanned_accounts=res.scanned_accounts, details=res.details))
    return res

def _event_type(payload: dict) -> str:
    return (payload.get("eventType") or payload.get("event") or "").strip()

def _should_process_event(event_type: str) -> bool:
    return event_type.lower() == "download"

@app.post("/webhook/radarr", response_model=WebhookResult, dependencies=[Depends(require_webhook)])
async def webhook_radarr(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    et = _event_type(payload)
    if not _should_process_event(et):
        return WebhookResult(removed=0, scanned_accounts=0, details=[f"Ignored eventType={et!r} (accepted: 'Download')"])

    movie = payload.get("movie") or {}
    tmdb_id = movie.get("tmdbId")
    title = movie.get("title") or payload.get("title") or "Unknown"
    year = movie.get("year")

    def to_int(x):
        try:
            return int(x) if x is not None else None
        except Exception:
            return None

    return _process(source="radarr", tmdb_id=to_int(tmdb_id), tvdb_id=None, title=title, year=to_int(year), db=db)

@app.post("/webhook/sonarr", response_model=WebhookResult, dependencies=[Depends(require_webhook)])
async def webhook_sonarr(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    et = _event_type(payload)
    if not _should_process_event(et):
        return WebhookResult(removed=0, scanned_accounts=0, details=[f"Ignored eventType={et!r} (accepted: 'Download')"])

    series = payload.get("series") or {}
    tvdb_id = series.get("tvdbId")
    title = series.get("title") or payload.get("title") or "Unknown"
    year = series.get("year")

    def to_int(x):
        try:
            return int(x) if x is not None else None
        except Exception:
            return None

    return _process(source="sonarr", tmdb_id=None, tvdb_id=to_int(tvdb_id), title=title, year=to_int(year), db=db)

# ---- Daily status check background task ----
async def _daily_status_checker():
    # checks once per day; first run after ~60s
    await asyncio.sleep(60)
    while True:
        try:
            db = SessionLocal()
            accounts = db.execute(select(PlexAccount)).scalars().all()
            for acc in accounts:
                token = None
                try:
                    token = crypto.decrypt(acc.token_enc)
                    ok, msg = plex_ops.validate_user_token(token)
                    if ok:
                        _mark_account_ok(db, acc.id)
                    else:
                        _mark_account_error(db, acc.id, msg)
                except Exception as e:
                    _mark_account_error(db, acc.id, str(e))
            db.close()
        except Exception:
            pass
        await asyncio.sleep(60 * 60 * 24)

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(_daily_status_checker())

# ---- Serve SPA ----
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith("api") or full_path.startswith("webhook") or full_path.startswith("health"):
        raise HTTPException(status_code=404, detail="Not found")
    index = STATIC_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=500, detail="Frontend not built")
    return FileResponse(str(index))
