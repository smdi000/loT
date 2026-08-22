from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_initial_migration_creates_required_tables(tmp_path: Path) -> None:
    db_file = tmp_path / "migration.db"
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{db_file.as_posix()}")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite+pysqlite:///{db_file.as_posix()}")
    try:
        inspector = inspect(engine)
        assert {"users", "devices", "user_devices", "tuya_messages", "training_sessions"}.issubset(
            inspector.get_table_names()
        )
        assert {"password_hash", "updated_at"}.issubset(
            {column["name"] for column in inspector.get_columns("users")}
        )
        training_columns = {column["name"]: column for column in inspector.get_columns("training_sessions")}
        assert "training_type" in training_columns
        assert training_columns["training_type"]["nullable"] is True

        command.downgrade(config, "20260808_02")
        downgraded = inspect(engine)
        assert "training_type" not in {
            column["name"] for column in downgraded.get_columns("training_sessions")
        }
    finally:
        engine.dispose()
