from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_initial_migration_contains_core_tables_and_event_store():
    migration = next(Path("migrations/versions").glob("0001_*.py")).read_text()

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
    ordered = list(reversed(revisions))

    assert script.get_heads() == ["0009"]
    assert [revision.revision for revision in ordered] == [
        "0001",
        "0002",
        "0003",
        "0004",
        "0005",
        "0006",
        "0007",
        "0008",
        "0009",
    ]
    assert [revision.down_revision for revision in ordered] == [
        None,
        "0001",
        "0002",
        "0003",
        "0004",
        "0005",
        "0006",
        "0007",
        "0008",
    ]


def test_alembic_revision_ids_fit_internal_length_convention():
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    for revision in script.walk_revisions():
        assert len(revision.revision) <= 16
