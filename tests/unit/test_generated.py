"""Model-written Cypher: every static check, the EXPLAIN read-only proof and the single repair attempt."""

from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from neo4j.exceptions import CypherSyntaxError

from app.agent.generated import GeneratedCypher, check_cypher, generate_and_run, prove_read_only
from app.models import AskRequest
from tests.fakes import fake_service

GOOD = "MATCH (:User)-[r:RATED]->(m:Movie) RETURN m.title AS title, count(r) AS ratings ORDER BY ratings DESC LIMIT 5"


def test_a_clean_read_query_passes_unchanged():
    assert check_cypher(GOOD, 5) == GOOD


def test_missing_limit_is_added_and_a_larger_limit_is_capped():
    assert check_cypher("MATCH (m:Movie) RETURN m.title AS title", 7).endswith("LIMIT 7")
    assert check_cypher("MATCH (m:Movie) RETURN m.title AS title LIMIT 500", 10).endswith("LIMIT 10")


@pytest.mark.parametrize(
    "query,reason",
    [
        ("MATCH (m:Movie) DETACH DELETE m RETURN 1", "keyword"),
        ("MATCH (m:Movie) SET m.title = 'x' RETURN m.title", "keyword"),
        ("MATCH (m:Movie) RETURN m.title; MATCH (n) DELETE n", "one statement"),
        ("CALL db.labels() YIELD label RETURN label", "keyword"),
        ("MATCH (m:Movie) CALL apoc.help('x') YIELD name RETURN name", "keyword"),
        ("MATCH (m:Movie) RETURN m.title // hidden", "Comments"),
        ("MATCH (a:Account) RETURN a.id", "Unknown label"),
        ("MATCH (:User)-[:OWNS]->(m:Movie) RETURN m.title", "Unknown relationship"),
        ("RETURN 1", "start with MATCH"),
        ("MATCH (m:Movie) WITH m.title AS title ORDER BY title LIMIT 5", "no RETURN"),
        ("MATCH (m:Movie) RETURN m.title LIMIT $n", "LIMIT must be a number"),
        ("LOAD CSV FROM 'file:///x' AS row RETURN row", "keyword"),
    ],
)
def test_unsafe_or_invalid_queries_are_rejected(query, reason):
    with pytest.raises(HTTPException) as error:
        check_cypher(query, 5)
    assert error.value.status_code == 422 and reason in error.value.detail["message"]


def test_keywords_inside_string_literals_are_not_false_alarms():
    query = "MATCH (m:Movie) WHERE toLower(m.title) CONTAINS 'set it off' RETURN m.title AS title LIMIT 3"
    assert check_cypher(query, 5) == query


def test_explain_must_classify_the_query_as_read_only():
    store = Mock()
    store.query_type.return_value = "rw"
    with pytest.raises(HTTPException) as error:
        prove_read_only(store, GOOD)
    assert "not read-only" in error.value.detail["message"]
    store.query_type.side_effect = CypherSyntaxError("Invalid input")
    with pytest.raises(HTTPException) as error:
        prove_read_only(store, GOOD)
    assert error.value.detail["code"] == "invalid_generated_cypher"


def make_service(kind="r"):
    service = fake_service()
    service.repository.store.query_type = Mock(return_value=kind)
    service.repository.store.read = Mock(return_value=[{"title": "Forrest Gump (1994)", "ratings": 329}])
    return service


def test_a_rejected_draft_gets_one_repair_with_the_reason():
    writer = Mock()
    writer.write.side_effect = [
        GeneratedCypher(cypher="MATCH (m:Movie) DETACH DELETE m RETURN 1", explanation="bad"),
        GeneratedCypher(cypher=GOOD, explanation="Most rated films."),
    ]
    service = make_service()
    result = generate_and_run(AskRequest(question="most rated", mode="generated", limit=5), service, writer, "t")
    assert result["compiled_cypher"] == GOOD and result["rows"]
    assert "keyword" in writer.write.call_args.args[3], "the second draft is told why the first failed"
    assert any(warning.startswith("First draft rejected") for warning in result["warnings"])


def test_two_rejected_drafts_never_run():
    writer = Mock()
    writer.write.return_value = GeneratedCypher(cypher="MATCH (m:Movie) SET m.x = 1 RETURN m.x", explanation="bad")
    service = make_service()
    with pytest.raises(HTTPException) as error:
        generate_and_run(AskRequest(question="x", mode="generated"), service, writer, "t")
    assert error.value.status_code == 422 and writer.write.call_count == 2
    service.repository.store.read.assert_not_called()


def test_a_write_hidden_from_static_checks_is_stopped_by_explain():
    writer = Mock()
    writer.write.return_value = GeneratedCypher(cypher=GOOD, explanation="looks fine")
    service = make_service(kind="w")
    with pytest.raises(HTTPException):
        generate_and_run(AskRequest(question="x", mode="generated"), service, writer, "t")
    service.repository.store.read.assert_not_called()
