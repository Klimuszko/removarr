from __future__ import annotations
import re
from typing import Iterable

def norm_title(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def extract_guid_ids(guids: Iterable[str]):
    out = {}
    for g in guids or []:
        if not g:
            continue
        m = re.match(r"^(tmdb|tvdb|imdb)://(.+)$", g)
        if m:
            out[m.group(1)] = m.group(2)
            continue
        m = re.match(r"^com\.plexapp\.agents\.(themoviedb|thetvdb)://(\d+)", g)
        if m:
            out["tmdb" if m.group(1) == "themoviedb" else "tvdb"] = m.group(2)
            continue
        m = re.match(r"^com\.plexapp\.agents\.imdb://(tt\d+)", g)
        if m:
            out["imdb"] = m.group(1)
            continue
    return out
