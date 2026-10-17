"""Malformed source files are rejected before they can partially populate the graph."""

import pandas as pd
import pytest

from scripts.data import load_frames


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.data.DATA", tmp_path)
    frames = {
        "movies": pd.DataFrame(
            {"movieId": [1, 2], "title": ["One (2000)", "Two (2001)"], "genres": ["Drama", "Comedy"]}
        ),
        "ratings": pd.DataFrame({"userId": [1, 1], "movieId": [1, 2], "rating": [4.0, 5.0], "timestamp": [100, 200]}),
        "tags": pd.DataFrame({"userId": [1], "movieId": [1], "tag": ["001"], "timestamp": [150]}),
        "links": pd.DataFrame({"movieId": [1, 2], "imdbId": [100, 200], "tmdbId": [10, 20]}),
    }

    def save():
        for name, frame in frames.items():
            frame.to_csv(tmp_path / (name + ".csv"), index=False)

    return frames, save


@pytest.mark.parametrize(
    "name,field,value",
    [
        ("movies", "movieId", -1),
        ("movies", "movieId", None),
        ("ratings", "userId", 0),
        ("ratings", "movieId", 1.25),
        ("tags", "timestamp", -1),
        ("tags", "timestamp", True),
        ("ratings", "timestamp", 1.5),
        ("links", "movieId", 2**63),
        ("movies", "title", None),
        ("tags", "tag", "   "),
    ],
)
def test_invalid_source_values_abort(source, name, field, value):
    frames, save = source
    frames[name][field] = frames[name][field].astype(object)
    frames[name].loc[0, field] = value
    save()
    with pytest.raises(ValueError):
        load_frames()


@pytest.mark.parametrize("name", ["movies", "links"])
def test_duplicate_catalog_identity_aborts(source, name):
    frames, save = source
    frames[name] = pd.concat([frames[name], frames[name].iloc[:1]])
    save()
    with pytest.raises(ValueError, match="Duplicate movie identities"):
        load_frames()


def test_missing_link_aborts_before_import(source):
    frames, save = source
    frames["links"] = frames["links"].iloc[:1]
    save()
    with pytest.raises(ValueError, match="exactly one links row"):
        load_frames()


def test_source_strings_and_absent_genres_are_preserved(source):
    frames, save = source
    frames["movies"].loc[0, "genres"] = None
    save()
    actual = load_frames()
    assert actual["tags"].iloc[0].tag == "001"
    assert actual["movies"].iloc[0].genres == "(no genres listed)"
    assert len(actual["ratings"]) == 2
