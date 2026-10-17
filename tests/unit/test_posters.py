"""Poster enrichment must not associate a different IMDb film or accept arbitrary URLs."""

from scripts.fetch_posters import match_posters


def test_poster_requires_both_ids_and_an_image_path():
    movies = [{"movie_id": 1, "title": "One", "tmdb_id": 862, "imdb_id": "0114709"}]
    row = {"id": "862", "imdb_id": "tt0114709", "poster_path": "/abc123.jpg"}
    assert match_posters(movies, [row]) == {"1": ["abc123.jpg", 862]}
    assert not match_posters(movies, [{**row, "imdb_id": "tt9999999"}])
    assert not match_posters(movies, [{**row, "poster_path": "https://untrusted.invalid/a.jpg"}])
    assert not match_posters(movies, [{**row, "id": "bad"}])


def test_incomplete_metadata_rows_are_ignored():
    assert not match_posters([], [{"id": "123", "poster_path": None}, {"id": None}])
