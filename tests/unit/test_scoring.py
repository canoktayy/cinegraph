"""Hand-computed score and source cleaning edge cases."""

import math

import pytest

from app.scoring import bayesian_rating, normalize_tag, parse_year, shrunk_jaccard, validate_rating


@pytest.mark.parametrize("value", [0.5, 1, 2.5, 4, 5])
def test_valid_rating(value):
    assert validate_rating(value) == value


@pytest.mark.parametrize("value", [0, 5.5, 3.2, math.nan, math.inf, -1])
def test_invalid_rating(value):
    with pytest.raises(ValueError):
        validate_rating(value)


def test_tag_normalization_retains_semantics():
    assert normalize_tag("  Sci-Fi   ＭＯＶＩＥ ") == "sci-fi movie"
    assert normalize_tag("café") == normalize_tag("cafe\u0301")
    assert normalize_tag("can't") == "can't"


@pytest.mark.parametrize(
    "title,year", [("Film (1999)", 1999), ("Film (Director's Cut)", None), ("Film (1999) extra", None), ("Film", None)]
)
def test_year_parse(title, year):
    assert parse_year(title) == year


def test_jaccard_with_support_shrinkage():
    score, support = shrunk_jaccard({1, 2, 3}, {2, 3, 4})
    assert support == 2
    assert score == pytest.approx((2 / 4) * (2 / 7))
    assert shrunk_jaccard(set(), set()) == (0, 0)
    with pytest.raises(ValueError):
        shrunk_jaccard({1}, {1}, 0)


def test_bayesian_baseline():
    assert bayesian_rating(0, 0, 3.5) == 3.5
    assert bayesian_rating(20, 5, 3) == 4
