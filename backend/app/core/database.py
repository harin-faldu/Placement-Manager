from __future__ import annotations

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    url = settings.database_url
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(url, pool_pre_ping=True)


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def install_guards(bind=None) -> None:
    target = bind or engine
    if target.dialect.name == "sqlite":
        statements = [
            """
            CREATE TRIGGER IF NOT EXISTS audit_logs_no_update
            BEFORE UPDATE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'audit log is append-only');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS audit_logs_no_delete
            BEFORE DELETE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'audit log is append-only');
            END
            """,
        ]
    elif target.dialect.name == "mysql":
        statements = [
            "DROP TRIGGER IF EXISTS audit_logs_no_update",
            "DROP TRIGGER IF EXISTS audit_logs_no_delete",
            """
            CREATE TRIGGER audit_logs_no_update
            BEFORE UPDATE ON audit_logs
            FOR EACH ROW
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'audit log is append-only'
            """,
            """
            CREATE TRIGGER audit_logs_no_delete
            BEFORE DELETE ON audit_logs
            FOR EACH ROW
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'audit log is append-only'
            """,
        ]
    elif target.dialect.name == "postgresql":
        statements = [
            """
            CREATE OR REPLACE FUNCTION placement_audit_immutable()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit log is append-only';
            END;
            $$ LANGUAGE plpgsql
            """,
            "DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs",
            "DROP TRIGGER IF EXISTS audit_logs_no_delete ON audit_logs",
            """
            CREATE TRIGGER audit_logs_no_update
            BEFORE UPDATE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION placement_audit_immutable()
            """,
            """
            CREATE TRIGGER audit_logs_no_delete
            BEFORE DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION placement_audit_immutable()
            """,
        ]
    else:
        return
    with target.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_schema() -> None:
    inspector = inspect(engine)
    if "compliance_flags" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("compliance_flags")}
    if "resolution_note" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE compliance_flags ADD COLUMN resolution_note TEXT"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
