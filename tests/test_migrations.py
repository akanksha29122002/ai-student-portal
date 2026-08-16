from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_initial_migration_contains_core_tables_and_event_store():
    migration = Path("migrations/versions/0001_initial_backend_architecture.py").read_text()

    for table_name in [
        "organizations",
        "programs",
        "batches",
        "students",
        "mentors",
        "projects",
        "repositories",
        "daily_tasks",
        "submissions",
        "evaluations",
        "mentor_reviews",
        "notifications",
        "audit_logs",
        "activity_logs",
        "system_events",
    ]:
        assert f'"{table_name}"' in migration


def test_alembic_revision_graph_is_single_linear_chain():
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    revisions = list(script.walk_revisions())

    assert script.get_heads() == ["0007"]
    assert [revision.revision for revision in reversed(revisions)] == [
        "0001_initial_backend_architecture",
        "0002_event_store_optimizations",
        "0003",
        "0004",
        "0005",
        "0006",
        "0007",
    ]
