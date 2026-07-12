"""Regenerate ``data.js`` from kworb.net's Spotify charts.

Re-derives the whole quiz pool each run: the top songs from the all-time chart
plus the top songs from four decade charts, deduplicated. Run with::

    uv run scripts/build_pool.py             # regenerate data.js
    uv run scripts/build_pool.py --dry-run   # print stats + diff, write nothing

Stdlib only, so it needs no runtime dependencies and runs anywhere uv can.
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import html
import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BASE = "https://kworb.net/spotify"
BILLION = 1_000_000_000

# Selection knobs — tune these to reshape the pool.
#
# Candidates come from the all-time chart plus four decade charts (deduped). To
# give the quiz a *wide, evenly spread* mix — tricky near-billion songs as well
# as obvious mega-hits and deep-catalog oldies — each side of the billion line
# is sorted by streams and then evenly sampled across its whole range, rather
# than just taking the top N (which would cluster at the extremes).
ALL_TIME_URL = f"{BASE}/songs.html"
ALL_TIME_SKIP = 1  # skip rank #1 (the too-obvious emblem of the club)
DECADES = ("1990", "1980", "1970", "1960")
OVER_TARGET = 125  # over-billion songs sampled across 1B .. top
UNDER_TARGET = 125  # sub-billion songs sampled across floor .. 1B
UNDER_FLOOR = 250_000_000  # drop ultra-obscure songs below this

# Safety guards — abort rather than write a broken data.js.
MIN_ROWS_PER_PAGE = 100
MIN_POOL = 200
MAX_POOL = 260
MIN_EACH_SIDE = 20  # over- and under-billion songs; runtime needs >= 4 of each

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "data.js"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# <tr>...<td class="text"><div>Artist - Title</div></td><td>1,234,567</td>...
ROW_RE = re.compile(
    r'<td class="text"><div>(?P<label>.*?)</div></td>\s*<td>(?P<streams>[\d,]+)</td>',
    re.DOTALL,
)


@dataclass(frozen=True)
class Song:
    artist: str
    title: str
    streams: int


def fetch(url: str) -> str:
    """Fetch a URL's body as text (kworb 403s the default urllib User-Agent)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return response.read().decode("utf-8", "replace")


def parse_rows(page: str) -> list[Song]:
    """Extract songs from a kworb chart page, in chart order."""
    songs: list[Song] = []
    for match in ROW_RE.finditer(page):
        label = html.unescape(match.group("label")).strip()
        artist, sep, title = label.partition(" - ")
        if not sep:
            continue  # not an "Artist - Title" row; skip defensively
        streams = int(match.group("streams").replace(",", ""))
        songs.append(Song(artist.strip(), title.strip(), streams))
    return songs


def _even_sample(songs: list[Song], want: int) -> list[Song]:
    """Pick ``want`` songs evenly spaced across ``songs`` (order preserved)."""
    if want >= len(songs):
        return list(songs)
    step = len(songs) / want
    return [songs[int(i * step)] for i in range(want)]


def build_pool() -> list[Song]:
    """Fetch every chart and assemble the deduplicated pool."""
    seen: set[tuple[str, str]] = set()
    candidates: list[Song] = []

    def add_rows(rows: list[Song]) -> None:
        for song in rows:
            key = (song.artist, song.title)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(song)

    all_time = parse_rows(fetch(ALL_TIME_URL))
    _require_rows(ALL_TIME_URL, all_time)
    add_rows(all_time[ALL_TIME_SKIP:])

    for decade in DECADES:
        url = f"{BASE}/songs_{decade}.html"
        rows = parse_rows(fetch(url))
        _require_rows(url, rows)
        add_rows(rows)

    over = sorted(
        (c for c in candidates if c.streams >= BILLION),
        key=lambda s: s.streams,
        reverse=True,
    )
    under = sorted(
        (c for c in candidates if UNDER_FLOOR <= c.streams < BILLION),
        key=lambda s: s.streams,
        reverse=True,
    )
    pool = _even_sample(over, OVER_TARGET) + _even_sample(under, UNDER_TARGET)
    _validate_pool(pool)
    return pool


def _require_rows(url: str, rows: list[Song]) -> None:
    if len(rows) < MIN_ROWS_PER_PAGE:
        raise SystemExit(
            f"error: {url} parsed only {len(rows)} rows "
            f"(expected >= {MIN_ROWS_PER_PAGE}); kworb layout may have changed."
        )


def _validate_pool(pool: list[Song]) -> None:
    over = sum(1 for s in pool if s.streams >= BILLION)
    under = len(pool) - over
    if not MIN_POOL <= len(pool) <= MAX_POOL:
        raise SystemExit(
            f"error: pool size {len(pool)} outside [{MIN_POOL}, {MAX_POOL}]."
        )
    if over < MIN_EACH_SIDE or under < MIN_EACH_SIDE:
        raise SystemExit(
            f"error: unbalanced pool (over={over}, under={under}); "
            f"need >= {MIN_EACH_SIDE} of each."
        )


def render(pool: list[Song], updated: str) -> str:
    """Render the pool as the contents of data.js (one object per line)."""
    lines = [
        "// Auto-generated by scripts/build_pool.py — do not edit by hand.",
        "// Source: kworb.net Spotify charts.",
        f'const POOL_UPDATED = "{updated}";',
        "const POOL = [",
    ]
    for song in pool:
        obj = {"artist": song.artist, "title": song.title, "streams": song.streams}
        lines.append("  " + json.dumps(obj, ensure_ascii=False) + ",")
    lines.append("];")
    return "\n".join(lines) + "\n"


def _print_stats(pool: list[Song]) -> None:
    over = sum(1 for s in pool if s.streams >= BILLION)
    print(f"pool: {len(pool)} songs | over {over} | under {len(pool) - over}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print stats and a diff vs the current data.js; write nothing",
    )
    args = parser.parse_args()

    pool = build_pool()
    updated = datetime.date.today().isoformat()
    new_content = render(pool, updated)
    _print_stats(pool)

    if args.dry_run:
        current = OUTPUT_PATH.read_text() if OUTPUT_PATH.exists() else ""
        diff = difflib.unified_diff(
            current.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile="data.js (current)",
            tofile="data.js (new)",
        )
        sys.stdout.writelines(diff)
        print("\n(dry run — data.js not written)")
        return 0

    OUTPUT_PATH.write_text(new_content)
    print(f"wrote {OUTPUT_PATH.relative_to(REPO_ROOT)} (updated {updated})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
