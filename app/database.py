"""Short-lived Neo4j sessions and bounded database transactions."""

from neo4j import GraphDatabase, Query, READ_ACCESS

from app.config import Settings


class GraphStore:
    """Own one driver and materialize results inside the session lifetime."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
            connection_timeout=5,
            max_transaction_retry_time=5,
        )

    def close(self):
        """Release sockets when the process exits."""
        self.driver.close()

    def read(self, text: str, parameters: dict | None = None) -> list[dict]:
        """Execute application-owned read Cypher, never unvalidated model text."""
        with self.driver.session(database=self.settings.neo4j_database, default_access_mode=READ_ACCESS) as session:
            return session.run(Query(text, timeout=self.settings.query_timeout_seconds), parameters or {}).data()

    def write(self, text: str, parameters: dict | None = None) -> list[dict]:
        """Run a trusted schema/import/batch statement outside the LLM surface."""
        with self.driver.session(database=self.settings.neo4j_database) as session:
            return session.execute_write(lambda transaction: transaction.run(text, parameters or {}).data())

    def healthy(self) -> bool:
        """Verify an actual round trip, rather than just driver creation."""
        return self.read("RETURN 1 AS value")[0]["value"] == 1
