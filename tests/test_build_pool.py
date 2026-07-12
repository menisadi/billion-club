"""Tests for the pool parser and sampler in scripts/build_pool.py."""

from __future__ import annotations

from build_pool import Song, _even_sample, parse_rows

SAMPLE_HTML = """
<table><tbody>
<tr><td class="text"><div>The Weeknd - Blinding Lights</div></td><td>5,494,122,712</td><td>1,508,556</td></tr>
<tr><td class="text"><div>Otis Redding - (Sittin' On) the Dock of the Bay</div></td><td>1,108,817,495</td><td>1,234</td></tr>
<tr><td class="text"><div>Simon &amp; Garfunkel - 50 Ways to Leave Your Lover</div></td><td>345,378,366</td><td>567</td></tr>
</tbody></table>
"""


def test_parse_rows_extracts_artist_title_streams() -> None:
    rows = parse_rows(SAMPLE_HTML)
    assert rows == [
        Song("The Weeknd", "Blinding Lights", 5_494_122_712),
        Song("Otis Redding", "(Sittin' On) the Dock of the Bay", 1_108_817_495),
        Song("Simon & Garfunkel", "50 Ways to Leave Your Lover", 345_378_366),
    ]


def test_parse_rows_splits_on_first_separator_and_unescapes() -> None:
    # Title contains a hyphen but not " - "; artist has an HTML entity.
    html = (
        '<tr><td class="text"><div>AC/DC - T.N.T.</div></td>'
        "<td>1,019,694,016</td><td>1</td></tr>"
    )
    (song,) = parse_rows(html)
    assert song.artist == "AC/DC"
    assert song.title == "T.N.T."


def test_parse_rows_skips_malformed_rows() -> None:
    html = (
        '<tr><td class="text"><div>NoSeparatorHere</div></td>'
        "<td>1,000</td><td>1</td></tr>"
    )
    assert parse_rows(html) == []


def test_even_sample_spans_the_range() -> None:
    songs = [Song("a", str(i), i) for i in range(100)]
    picked = _even_sample(songs, 10)
    assert len(picked) == 10
    assert picked[0] == songs[0]  # keeps the extremes' neighbourhoods
    assert picked == sorted(picked, key=lambda s: s.streams)  # order preserved


def test_even_sample_returns_all_when_want_exceeds_length() -> None:
    songs = [Song("a", "1", 1), Song("b", "2", 2)]
    assert _even_sample(songs, 5) == songs
