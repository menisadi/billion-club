# The Billion Club

A quiz about Spotify's most-streamed songs. Each round shows a random song and
asks whether it has crossed one billion total streams, then reveals the exact
count.

Live at https://menisadi.github.io/billion-club/

## How it works

`index.html` is a single self-contained page (no build step, no dependencies)
that draws 10 questions per game from a pool of 250 songs, guaranteeing at
least 4 above and 4 below the billion-stream mark. Just open the file in a
browser, or visit the GitHub Pages link above.

## Data

The song pool lives in `data.js` and is generated from kworb.net's Spotify
charts by `scripts/build_pool.py`. It evenly samples each side of the
billion-stream line for a wide, balanced mix of songs.

- [All-time most-streamed songs](https://kworb.net/spotify/songs.html)
- [1990s](https://kworb.net/spotify/songs_1990.html), [1980s](https://kworb.net/spotify/songs_1980.html), [1970s](https://kworb.net/spotify/songs_1970.html), [1960s](https://kworb.net/spotify/songs_1960.html) charts

Refresh the counts (regenerates `data.js` with today's date):

```
uv run scripts/build_pool.py            # or --dry-run to preview the diff
```
