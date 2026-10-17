"""Regression for the real Docker-DNS outage observed during restart testing."""

from unittest.mock import MagicMock

import pytest
from neo4j.exceptions import ServiceUnavailable

from app.config import Settings
from app.database import GraphStore


@pytest.mark.parametrize(
    "message,error_type",
    [("Cannot resolve address neo4j:7687", ServiceUnavailable), ("Invalid parameter type", ValueError)],
)
def test_transport_dns_is_normalized_without_masking_other_errors(message, error_type, monkeypatch):
    store = GraphStore(Settings())
    session = MagicMock()
    session.__enter__.return_value.run.side_effect = ValueError(message)
    monkeypatch.setattr(store.driver, "session", lambda **_: session)
    try:
        with pytest.raises(error_type):
            store.read("RETURN 1")
    finally:
        store.close()
