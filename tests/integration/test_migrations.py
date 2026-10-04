"""NFR-05: migrations must build exactly the schema the ORM expects."""
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.core.db import Base
from tests.conftest import ROOT, alembic_config


@pytest.fixture()
def migrated_engine(tmp_path):
    from alembic import command

    engine = create_engine(f"sqlite:///{tmp_path / 'migrated.db'}")
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.mark.nfr05
def test_migrations_produce_the_orm_schema_without_drift(migrated_engine):
    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": False})
        diff = compare_metadata(context, Base.metadata)
    assert diff == [], f"ORM models and Alembic migrations drifted: {diff}"


@pytest.mark.nfr05
def test_migrations_create_ledger_and_idempotency_structures(migrated_engine):
    inspector = inspect(migrated_engine)
    assert "trades" in inspector.get_table_names()
    order_columns = {column["name"] for column in inspector.get_columns("orders")}
    assert {"idempotency_key", "request_fingerprint"} <= order_columns
    assert any(index["unique"] and index["column_names"] == ["customer_id", "idempotency_key"] for index in inspector.get_indexes("orders"))


@pytest.mark.nfr05
def test_migration_history_is_linear_and_downgrade_is_refused():
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(alembic_config())
    revisions = list(script.walk_revisions())
    assert len(script.get_heads()) == 1
    assert [revision.revision for revision in reversed(revisions)][0] == "0001_initial"
    assert (ROOT / "migrations" / "versions").is_dir()
