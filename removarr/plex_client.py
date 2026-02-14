from __future__ import annotations

from typing import Optional, Tuple

import requests
import xml.etree.ElementTree as ET
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


    def _discover_watchlist_xml(self, user_token: str) -> str:
        # Plex migrated Watchlist APIs from metadata.provider.plex.tv to discover.provider.plex.tv.
        # Using direct HTTP avoids PlexAPI breakages.
        base = "https://discover.provider.plex.tv"
        url = f"{base}/library/sections/watchlist/all"
        params = {
            "includeCollections": "1",
            "includeExternalMedia": "1",
            "X-Plex-Token": user_token,
        }
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r.text

    def _discover_remove_watchlist(self, user_token: str, rating_key: str) -> None:
        base = "https://discover.provider.plex.tv"
        url = f"{base}/actions/removeFromWatchlist"
        params = {"ratingKey": rating_key, "X-Plex-Token": user_token}
        r = requests.put(url, params=params, timeout=20)
        r.raise_for_status()

    def remove_from_watchlist_if_present(
        self,
        user_token: str,
        tmdb_id: Optional[int],
        tvdb_id: Optional[int],
        title: str,
        year: Optional[int],
    ) -> Tuple[bool, str]:
        # Fetch watchlist from Plex Discover API (XML)
        try:
            xml_text = self._discover_watchlist_xml(user_token)
        except Exception as e:
            return False, f"Failed to fetch watchlist: {e}"

        target_title = norm_title(title)
        try:
            root = ET.fromstring(xml_text)
        except Exception as e:
            return False, f"Failed to parse watchlist XML: {e}"

        # Iterate all nodes; watchlist entries typically have ratingKey + title.
        for node in root.iter():
            rk = node.attrib.get("ratingKey") or node.attrib.get("ratingkey")
            if not rk:
                continue

            node_title = norm_title(node.attrib.get("title", "") or "")
            node_year = node.attrib.get("year")
            guid = node.attrib.get("guid", "") or ""

            gids = {"raw": guid}
            # extract ids from guid string + nested Guid tags
            if guid:
                try:
                    tmp = extract_guid_ids([{"id": guid}])  # type: ignore[arg-type]
                    gids.update(tmp)
                except Exception:
                    pass

            for g in node.findall(".//Guid"):
                gid = g.attrib.get("id") or ""
                if gid:
                    try:
                        tmp = extract_guid_ids([{"id": gid}])  # type: ignore[arg-type]
                        gids.update(tmp)
                    except Exception:
                        continue

            # Prefer exact id matches
            if tmdb_id and (gids.get("tmdb") == str(tmdb_id)):
                try:
                    self._discover_remove_watchlist(user_token, rk)
                    return True, f"Removed by TMDB {tmdb_id}"
                except Exception as e:
                    return False, f"Remove failed (TMDB match): {e}"

            if tvdb_id and (gids.get("tvdb") == str(tvdb_id)):
                try:
                    self._discover_remove_watchlist(user_token, rk)
                    return True, f"Removed by TVDB {tvdb_id}"
                except Exception as e:
                    return False, f"Remove failed (TVDB match): {e}"

            # Fallback: title/year
            if node_title and node_title == target_title:
                if year is None:
                    try:
                        self._discover_remove_watchlist(user_token, rk)
                        return True, "Removed by title fallback"
                    except Exception as e:
                        return False, f"Remove failed (title match): {e}"
                else:
                    try:
                        if node_year and int(node_year) == int(year):
                            self._discover_remove_watchlist(user_token, rk)
                            return True, "Removed by title/year fallback"
                    except Exception:
                        pass

        return False, "Not on watchlist"
