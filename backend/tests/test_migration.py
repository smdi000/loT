from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_initial_migration_creates_required_tables(tmp_path: Path) -> None:
    db_file = tmp_path / "migration.db"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
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
    finally:
        engine.dispose()
