"""
Media-Steuerung: YouTube- und Spotify-Suche im Browser öffnen.
Sicherheit: Allowlist-Pflicht — nur freigegebene Domains werden geöffnet.
Kein Selenium, kein PyWhatKit, kein Browser-Automation.
"""

from __future__ import annotations

import subprocess
import urllib.parse
from urllib.parse import urlparse
from typing import Any

# ── Allowlist ─────────────────────────────────────────────────────────────────
# Nur Domains aus dieser Liste dürfen geöffnet werden.
# "www."-Präfix wird beim Vergleich automatisch entfernt.

ALLOWED_PLATFORMS: frozenset[str] = frozenset({
    "youtube.com",
    "music.youtube.com",
    "open.spotify.com",
})

_CREATE_NO_WINDOW = 0x08000000


# ── Allowlist-Check ───────────────────────────────────────────────────────────


def _extract_domain(url: str) -> str:
    """Extrahiert normalisierten Domain-Namen ohne www.-Präfix."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _is_allowed(url: str) -> bool:
    """True wenn URL-Domain in ALLOWED_PLATFORMS ist."""
    domain = _extract_domain(url)
    return domain in ALLOWED_PLATFORMS


def open_allowed_url(url: str) -> dict[str, Any]:
    """
    Öffnet URL im Standard-Browser — NUR wenn Domain in ALLOWED_PLATFORMS.
    Returns: {"ok": bool, "url": str, "error": str|None}
    """
    if not url or not url.strip():
        return {"ok": False, "url": url, "error": "Leere URL."}

    domain = _extract_domain(url)
    if not domain:
        return {"ok": False, "url": url, "error": "URL konnte nicht geparst werden."}

    if not _is_allowed(url):
        return {
            "ok": False,
            "url": url,
            "error": (
                f"SICHERHEITSRISIKO: Domain '{domain}' nicht in Allowlist. "
                f"Erlaubt: {sorted(ALLOWED_PLATFORMS)}"
            ),
        }

    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", url],
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW,
        )
        return {"ok": True, "url": url, "error": None}

    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}


# ── YouTube ───────────────────────────────────────────────────────────────────


def play_on_youtube(query: str) -> dict[str, Any]:
    """
    Öffnet YouTube-Suche im Browser.
    Returns: {"ok": bool, "url": str, "query": str, "error": str|None}
    """
    if not query or not query.strip():
        return {"ok": False, "url": "", "query": query, "error": "Leere Suchanfrage."}

    encoded = urllib.parse.quote_plus(query.strip())
    url = f"https://www.youtube.com/results?search_query={encoded}"
    result = open_allowed_url(url)
    return {**result, "query": query}


def play_on_youtube_music(query: str) -> dict[str, Any]:
    """
    Öffnet YouTube Music-Suche im Browser.
    Returns: {"ok": bool, "url": str, "query": str, "error": str|None}
    """
    if not query or not query.strip():
        return {"ok": False, "url": "", "query": query, "error": "Leere Suchanfrage."}

    encoded = urllib.parse.quote_plus(query.strip())
    url = f"https://music.youtube.com/search?q={encoded}"
    result = open_allowed_url(url)
    return {**result, "query": query}


# ── Spotify ───────────────────────────────────────────────────────────────────


def play_on_spotify(query: str) -> dict[str, Any]:
    """
    Öffnet Spotify-Websuche im Browser.
    Returns: {"ok": bool, "url": str, "query": str, "error": str|None}
    """
    if not query or not query.strip():
        return {"ok": False, "url": "", "query": query, "error": "Leere Suchanfrage."}

    encoded = urllib.parse.quote(query.strip())
    url = f"https://open.spotify.com/search/{encoded}"
    result = open_allowed_url(url)
    return {**result, "query": query}


# ── Dispatch ──────────────────────────────────────────────────────────────────


def play_music(platform: str, query: str) -> dict[str, Any]:
    """
    Dispatch-Funktion für Backend-Commands.
    platform: "youtube" | "youtube_music" | "spotify"
    Returns strukturiertes Ergebnis-Dict.
    """
    platform_lower = str(platform).strip().lower()

    if platform_lower in ("youtube", "yt"):
        return play_on_youtube(query)

    if platform_lower in ("youtube_music", "yt_music", "ytm"):
        return play_on_youtube_music(query)

    if platform_lower == "spotify":
        return play_on_spotify(query)

    return {
        "ok": False,
        "url": "",
        "query": query,
        "error": f"Unbekannte Plattform: '{platform}'. Erlaubt: youtube, youtube_music, spotify.",
    }
