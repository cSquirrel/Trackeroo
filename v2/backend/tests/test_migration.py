from __future__ import annotations

import sqlite3

from sqlalchemy import inspect

from app.database import Base, engine
from app.main import _migrate_add_priority, _migrate_add_task_type


def test_migrate_adds_missing_type_column_to_existing_db():
    """Simulates a database created before `tasks.type` existed."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    db_path = engine.url.database
    conn = sqlite3.connect(db_path)
    conn.execute("ALTER TABLE tasks DROP COLUMN type")
    conn.commit()
    conn.close()

    columns_before = {c["name"] for c in inspect(engine).get_columns("tasks")}
    assert "type" not in columns_before

    _migrate_add_task_type()

    columns_after = {c["name"] for c in inspect(engine).get_columns("tasks")}
    assert "type" in columns_after

    # Idempotent: running it again on an already-migrated DB is a no-op, not
    # an error (e.g. "duplicate column").
    _migrate_add_task_type()

    Base.metadata.drop_all(engine)


def test_migrate_adds_missing_priority_columns_to_existing_db():
    """Simulates a database created before `priority` existed on tasks/epics."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    db_path = engine.url.database
    conn = sqlite3.connect(db_path)
    conn.execute("ALTER TABLE tasks DROP COLUMN priority")
    conn.execute("ALTER TABLE epics DROP COLUMN priority")
    conn.commit()
    conn.close()

    assert "priority" not in {c["name"] for c in inspect(engine).get_columns("tasks")}
    assert "priority" not in {c["name"] for c in inspect(engine).get_columns("epics")}

    _migrate_add_priority()

    assert "priority" in {c["name"] for c in inspect(engine).get_columns("tasks")}
    assert "priority" in {c["name"] for c in inspect(engine).get_columns("epics")}

    # Idempotent, same as the type migration.
    _migrate_add_priority()

    Base.metadata.drop_all(engine)
