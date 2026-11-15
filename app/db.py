from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine


def make_engine(var_dir: Path) -> Engine:
    # create_engine não abre conexão: o diretório só precisa existir em init_db.
    return create_engine(
        f"sqlite:///{Path(var_dir) / 'app.db'}", connect_args={"check_same_thread": False}
    )


def init_db(engine: Engine, var_dir: Path) -> None:
    from app.repositories import tables  # noqa: F401  (registra as tabelas)

    Path(var_dir).mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)
    _migrate(engine)


def _migrate(engine: Engine) -> None:
    """Adds columns created after the first release to an existing SQLite database."""
    with engine.begin() as connection:
        columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(plot)")}
        if "query_geometry_json" not in columns:
            connection.exec_driver_sql("ALTER TABLE plot ADD COLUMN query_geometry_json VARCHAR")
        # The demo property used to have Portuguese names; the app is in English.
        demo = connection.exec_driver_sql(
            "SELECT id FROM farm WHERE name = 'Sítio Demonstração'").fetchall()
        for (farm_id,) in demo:
            connection.exec_driver_sql(
                "UPDATE farm SET name = 'Demo Farm', owner = 'Demo farmer' WHERE id = ?",
                (farm_id,))
            connection.exec_driver_sql(
                "UPDATE plot SET name = REPLACE(name, 'Talhão ', 'Field ') "
                "WHERE farm_id = ? AND name LIKE 'Talhão %'", (farm_id,))


def new_session(engine: Engine) -> Session:
    return Session(engine)
