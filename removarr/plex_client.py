from __future__ import annotations

from typing import Optional, Tuple
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer

from .utils import extract_guid_ids, norm_title

class PlexOps:
    def __init__(self, plex_base_url: Optional[str], plex_server_token: Optional[str]):
        self.plex_base_url = plex_base_url
        self.plex_server_token = plex_server_token
        self._server: Optional[PlexServer] = None

    def _get_server(self) -> Optional[PlexServer]:
        if not self.plex_base_url or not self.plex_server_token:
            return None
        if self._server is None:
            self._server = PlexServer(self.plex_base_url, self.plex_server_token)
        return self._server

    def account(self, user_token: str) -> MyPlexAccount:
        return MyPlexAccount(token=user_token)

    def validate_user_token(self, user_token: str) -> tuple[bool, str]:
        try:
            acct = self.account(user_token)
            # Touch a property that requires auth.
            _ = acct.username
            return True, getattr(acct, "username", "") or "ok"
        except Exception as e:
            return False, str(e)

    def is_available_in_library(self, tmdb_id: Optional[int], tvdb_id: Optional[int], title: str, year: Optional[int]) -> bool:
        server = self._get_server()
        if server is None:
            return True

        try:
            results = server.search(query=title)
        except Exception:
            return False

        target_title = norm_title(title)
        for r in results:
            try:
                r_title = norm_title(getattr(r, "title", "") or "")
                r_year = getattr(r, "year", None)
                if target_title and r_title != target_title:
                    continue
                if year and r_year and int(r_year) != int(year):
                    continue
                gid = extract_guid_ids(getattr(r, "guids", None) or [])
                if tmdb_id and gid.get("tmdb") == str(tmdb_id):
                    return True
                if tvdb_id and gid.get("tvdb") == str(tvdb_id):
                    return True
                if target_title and (not year or (r_year and int(r_year) == int(year))):
                    return True
            except Exception:
                continue
        return False

    def remove_from_watchlist_if_present(self, user_token: str, tmdb_id: Optional[int], tvdb_id: Optional[int], title: str, year: Optional[int]) -> Tuple[bool, str]:
        acct = self.account(user_token)
        items = acct.watchlist()
        target_title = norm_title(title)

        for item in items:
            gid = extract_guid_ids(getattr(item, "guids", None) or [])
            if tmdb_id and gid.get("tmdb") == str(tmdb_id):
                item.removeFromWatchlist()
                return True, f"Removed by TMDB {tmdb_id}"
            if tvdb_id and gid.get("tvdb") == str(tvdb_id):
                item.removeFromWatchlist()
                return True, f"Removed by TVDB {tvdb_id}"

            i_title = norm_title(getattr(item, "title", "") or "")
            i_year = getattr(item, "year", None)
            if i_title == target_title and (year is None or (i_year is not None and int(i_year) == int(year))):
                item.removeFromWatchlist()
                return True, "Removed by title/year fallback"

        return False, "Not on watchlist"
