#!/usr/bin/env python3
"""
spotify_test.py — Spotify API diagnostic script (spotipy edition)

Tests various endpoints to pinpoint exactly which are accessible.
Automatically tries to get an OAuth user token from the running Flask app
first, then falls back to Client Credentials (app-level) for public endpoints.

Usage:
    python spotify_test.py
    python spotify_test.py --playlist <url_or_id>
    python spotify_test.py --token <bearer_token>
    python spotify_test.py --flask http://localhost:5000
"""

import os
import sys
import argparse
import requests as _requests  # raw requests for fetching token from Flask

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:5000/callback")

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ── Printing helpers ───────────────────────────────────────────────────────

def ok(msg):     print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg):   print(f"  {RED}✗{RESET} {msg}")
def warn(msg):   print(f"  {YELLOW}⚠{RESET}  {msg}")
def info(msg):   print(f"  {CYAN}→{RESET} {msg}")
def header(msg): print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}\n{BOLD}{msg}{RESET}")


# ── Token helpers ──────────────────────────────────────────────────────────

def get_cc_spotify():
    """Return a Spotify client using Client Credentials (no user auth)."""
    if not CLIENT_ID or not CLIENT_SECRET:
        return None, "SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET not set"
    try:
        cc = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
        sp = spotipy.Spotify(auth_manager=cc)
        sp.search("test", limit=1)  # validate token works
        return sp, None
    except spotipy.SpotifyException as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)


def get_user_spotify(token):
    """Return a Spotify client using an existing bearer token."""
    return spotipy.Spotify(auth=token)


def fetch_oauth_token_from_flask(flask_url):
    """Grab the live OAuth user token from the running Flask app."""
    try:
        r = _requests.get(f"{flask_url}/api/debug-token", timeout=5)
        if r.status_code == 200:
            return r.json().get("access_token"), None
        elif r.status_code == 401:
            return None, "Flask running but no user logged in — log in at the app first"
        else:
            return None, f"Flask returned {r.status_code}"
    except _requests.ConnectionError:
        return None, "Flask app not reachable"


def extract_playlist_id(url_or_id):
    if not url_or_id:
        return None
    url_or_id = url_or_id.split("?")[0].strip()
    if "open.spotify.com/playlist/" in url_or_id:
        return url_or_id.split("open.spotify.com/playlist/")[-1].strip("/")
    if "spotify:playlist:" in url_or_id:
        return url_or_id.split("spotify:playlist:")[-1]
    return url_or_id


# ── Test suites ────────────────────────────────────────────────────────────

def test_credentials():
    header("1. Credentials (.env)")
    ok(f"CLIENT_ID  : {CLIENT_ID[:8]}...") if CLIENT_ID else fail("CLIENT_ID not set")
    ok(f"CLIENT_SECRET: {CLIENT_SECRET[:4]}...") if CLIENT_SECRET else fail("CLIENT_SECRET not set")
    return bool(CLIENT_ID and CLIENT_SECRET)


def test_current_user(sp, token_type):
    header(f"2. Current User  [{token_type}]")
    try:
        user = sp.current_user()
        ok(f"/me → {user.get('display_name', '?')}  <{user.get('email', 'no email scope')}>")
        return True
    except spotipy.SpotifyException as e:
        c = e.http_status
        if c == 401:
            warn("/me 401 — expected with Client Credentials token (no user scope)")
        elif c == 403:
            warn("/me 403 — expected with Client Credentials token")
        else:
            fail(f"/me error: {e}")
        return False


def test_public_endpoints(sp):
    header("3. Public / Catalog endpoints")

    # Search
    try:
        r = sp.search("Radiohead", type="artist", limit=1)
        items = r.get("artists", {}).get("items", [])
        ok("search() ✓")
        if items:
            info(f"  Artist: {items[0]['name']}")
    except spotipy.SpotifyException as e:
        fail(f"search() → {e.http_status}: {e.msg}")

    # Single track
    try:
        t = sp.track("4uLU6hMCjMI75M1A2tKUQC")
        ok(f"track() ✓  → {t['name']} — {t['artists'][0]['name']}")
    except spotipy.SpotifyException as e:
        fail(f"track() → {e.http_status}: {e.msg}")

    # Batch tracks
    try:
        ids = ["4uLU6hMCjMI75M1A2tKUQC", "7qiZfU4dY1lWllzX7mPBI3", "3n3Ppam7vgaVa1iaRUIOKE"]
        batch = sp.tracks(ids)
        names = [t["name"] for t in batch.get("tracks", []) if t]
        ok(f"tracks() batch ✓  → {', '.join(names)}")
    except spotipy.SpotifyException as e:
        fail(f"tracks() batch → {e.http_status}: {e.msg}")
        if e.http_status == 403:
            warn("  /tracks batch is restricted in Development Mode")

    # Album
    try:
        alb = sp.album("6dVIqscmAB9EobAq4JOYPL")
        ok(f"album() ✓  → {alb['name']}")
    except spotipy.SpotifyException as e:
        fail(f"album() → {e.http_status}: {e.msg}")


def test_audio_features(sp):
    header("4. Audio Features (deprecated Nov 2024)")

    # Single
    try:
        af = sp.audio_features(["4uLU6hMCjMI75M1A2tKUQC"])
        if af and af[0]:
            f = af[0]
            ok(f"audio_features() single ✓")
            info(f"  danceability={f['danceability']}  energy={f['energy']}  tempo={f['tempo']}")
        else:
            warn("audio_features() returned empty result (None entry)")
    except spotipy.SpotifyException as e:
        fail(f"audio_features() single → {e.http_status}")
        if e.http_status == 403:
            warn("  Restricted in Development Mode — request Extended Quota in your Spotify Dashboard")

    # Batch
    try:
        ids = ["4uLU6hMCjMI75M1A2tKUQC", "7qiZfU4dY1lWllzX7mPBI3"]
        af  = sp.audio_features(ids)
        real = [f for f in af if f] if af else []
        ok(f"audio_features() batch ✓  ({len(real)}/{len(ids)} returned)")
    except spotipy.SpotifyException as e:
        fail(f"audio_features() batch → {e.http_status}")


def test_playlist(sp, playlist_id):
    header(f"5. Playlist  (ID: {playlist_id})")

    # Metadata
    try:
        meta = sp.playlist(playlist_id)  # no fields filter → gets everything
        ok(f"playlist() metadata ✓")
        total = (meta.get('tracks') or {}).get('total', '?')
        info(f"  '{meta['name']}' by {meta['owner']['display_name']}  ({total} tracks)")
    except spotipy.SpotifyException as e:
        fail(f"playlist() metadata → {e.http_status}: {str(e)[:80]}")
        if e.http_status == 403:
            warn("  Private playlist? Make sure you're using an OAuth user token (log in first).")
        return

    # Tracks — no fields filter (what the current app does)
    try:
        items_result = sp.playlist_items(playlist_id, limit=5)
        items = [i["track"]["name"] for i in items_result.get("items", []) if i.get("track")]
        ok(f"playlist_items() (no fields) ✓  — {len(items)} items")
        info(f"  First tracks: {', '.join(items[:3])}")
    except spotipy.SpotifyException as e:
        fail(f"playlist_items() (no fields) → {e.http_status}: {str(e)[:80]}")

    # Tracks — WITH fields filter
    try:
        items_f = sp.playlist_items(
            playlist_id, limit=5,
            fields="next,items(track(id,name))"
        )
        ok("playlist_items() (with fields=...) ✓")
    except spotipy.SpotifyException as e:
        fail(f"playlist_items() (with fields=...) → {e.http_status}")
        if e.http_status == 403:
            warn("  fields= filter causes 403 — confirmed, app uses field-less URL now")


def test_recommendations(sp):
    header("6. Recommendations endpoint")
    try:
        r = sp.recommendations(seed_tracks=["4uLU6hMCjMI75M1A2tKUQC"], limit=3)
        names = [t["name"] for t in r.get("tracks", [])]
        ok(f"recommendations() ✓  → {', '.join(names)}")
    except spotipy.SpotifyException as e:
        fail(f"recommendations() → {e.http_status}: {e.msg}")
        if e.http_status in (403, 404):
            warn("  Deprecated Nov 2024 — not available in Development Mode")


def print_summary():
    print(f"\n{BOLD}{'='*60}")
    print("  Interpretation guide:")
    print(f"{'='*60}{RESET}")
    print(f"  {YELLOW}401 on /me with CC token{RESET}       → expected, need user OAuth token")
    print(f"  {YELLOW}403 on audio_features(){RESET}         → deprecated for dev-mode apps")
    print(f"    Fix: Dashboard → your app → Request Extended Quota Mode")
    print(f"  {YELLOW}403 on tracks()/recommendations(){RESET}→ same dev-mode restriction")
    print(f"  {YELLOW}403 on playlist_items(){RESET}         → need user OAuth token OR")
    print(f"    add yourself as a test user in Spotify Dashboard")
    print()


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Spotify API diagnostic (spotipy)")
    parser.add_argument("--playlist", help="Playlist URL or ID to test", default=None)
    parser.add_argument("--token",    help="Bearer token (skips auto-fetch)", default=None)
    parser.add_argument("--flask",    help="Flask URL", default="http://localhost:5000")
    args = parser.parse_args()

    print(f"\n{BOLD}{'='*60}")
    print("  Spotify API Diagnostic  (spotipy edition)")
    print(f"{'='*60}{RESET}")

    if not test_credentials():
        print(f"\n{RED}Aborting — fix credentials first.{RESET}\n")
        sys.exit(1)

    # ── Token selection ────────────────────────────────────────────────
    sp = None
    token_type = None

    if args.token:
        sp = get_user_spotify(args.token)
        token_type = "User-provided Bearer token"
        ok(f"Using provided Bearer token")
    else:
        # 1) Try OAuth token from Flask app
        print(f"\n{CYAN}Trying OAuth user token from Flask ({args.flask})...{RESET}")
        user_token, err = fetch_oauth_token_from_flask(args.flask)
        if user_token:
            sp = get_user_spotify(user_token)
            token_type = "OAuth User Token (from Flask session)"
            ok("Got OAuth user token from Flask app — full user scope available")
        else:
            warn(f"Couldn't get user token: {err}")
            # 2) Fall back to Client Credentials
            print(f"  {CYAN}Falling back to Client Credentials (limited scope)...{RESET}")
            sp, cc_err = get_cc_spotify()
            if sp is None:
                fail(f"Client Credentials failed: {cc_err}")
                sys.exit(1)
            token_type = "Client Credentials (app-level — user endpoints will fail)"
            ok("Client Credentials token obtained")

    # ── Run tests ──────────────────────────────────────────────────────
    test_current_user(sp, token_type)
    test_public_endpoints(sp)
    test_audio_features(sp)

    if args.playlist:
        pid = extract_playlist_id(args.playlist)
        test_playlist(sp, pid)
    else:
        warn("No --playlist given. Using a public Spotify playlist.")
        test_playlist(sp, "37i9dQZF1DXcBWIGoYBM5M")

    test_recommendations(sp)
    print_summary()


if __name__ == "__main__":
    main()
