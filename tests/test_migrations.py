from pathlib import Path


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

