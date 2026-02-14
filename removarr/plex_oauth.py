from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import time
import threading

from plexapi.myplex import MyPlexPinLogin, MyPlexAccount

@dataclass
class OAuthFlow:
    id: str
    created_at: float
    login: MyPlexPinLogin

class PlexOAuthManager:
    def __init__(self):
        self._flows: dict[str, OAuthFlow] = {}
        self._lock = threading.Lock()

    def start(self, flow_id: str) -> str:
        pl = MyPlexPinLogin(oauth=True)
        url = pl.oauthUrl()
        with self._lock:
            self._flows[flow_id] = OAuthFlow(id=flow_id, created_at=time.time(), login=pl)
        return url

    def poll(self, flow_id: str) -> tuple[str, Optional[str]]:
        with self._lock:
            flow = self._flows.get(flow_id)
        if not flow:
            return "expired", None

        pl = flow.login
        # hard-expire after 3 minutes
        if time.time() - flow.created_at > 180:
            with self._lock:
                self._flows.pop(flow_id, None)
            return "expired", None

        try:
            if pl.checkLogin():
                token = pl.token
                # cleanup
                with self._lock:
                    self._flows.pop(flow_id, None)
                return "ok", token
            if pl.expired:
                with self._lock:
                    self._flows.pop(flow_id, None)
                return "expired", None
            return "pending", None
        except Exception:
            return "error", None
