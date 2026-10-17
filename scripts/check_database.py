"""Fail preflight rather than silently skipping all database integration tests."""

from app.config import get_settings
from app.database import GraphStore


def main():
    """Require a real database and seeded snapshot."""
    store = GraphStore(get_settings())
    try:
        store.healthy()
        state = store.read("MATCH (s:SystemState {key:'dataset'}) RETURN s.data_version AS version")
        if not state:
            raise SystemExit("Connected to Neo4j but no dataset exists. Run make seed.")
        print("Neo4j connection and dataset preflight passed")
    finally:
        store.close()


if __name__ == "__main__":
    main()
