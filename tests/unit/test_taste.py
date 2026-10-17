"""Visitor choices are bounded positive seeds rather than fabricated source ratings."""

from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.taste import TasteRequest, recommend, rounds
from tests.fakes import fake_service


@pytest.mark.parametrize("ids", [[], [1, 1], [0], [-1], list(range(1, 12))])
def test_bad_selections(ids):
    with pytest.raises(ValidationError):
        TasteRequest(movie_ids=ids)


def test_rounds_have_fifty_unique_options_and_reproducible_seed():
    service = fake_service()
    service.repository.store.read = Mock(return_value=[{"movie_id": i} for i in range(150)])
    first = rounds(service, 11)
    assert len(first["rounds"]) == 10
    assert all(len(group) == 5 for group in first["rounds"])
    assert len({row["movie_id"] for group in first["rounds"] for row in group}) == 50
    assert first == rounds(service, 11)
    assert first != rounds(service, 12)
    service.repository.store.read.return_value = []
    with pytest.raises(HTTPException) as error:
        rounds(service, 11)
    assert error.value.status_code == 503


def test_visitor_rejects_unknown_seed_and_genre():
    service = fake_service()
    with pytest.raises(HTTPException) as error:
        recommend(service, TasteRequest(movie_ids=[1], genre="Invented"))
    assert error.value.status_code == 422
    service.repository.store.read = Mock(return_value=[])
    with pytest.raises(HTTPException) as error:
        recommend(service, TasteRequest(movie_ids=[999]))
    assert error.value.status_code == 404
