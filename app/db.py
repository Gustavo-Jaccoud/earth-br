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
        _refresh_query_areas(connection)
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


def _refresh_query_areas(connection) -> None:
    """Keeps the stored query area and its centre in line with the current rule (the rectangle
    that encloses the boundary). Rows written under an older rule are rewritten."""
    import json

    from app.models.farms import GeoJSONPolygon
    from app.services import geometry

    rows = connection.exec_driver_sql(
        "SELECT id, geometry_json, query_geometry_json, centroid_lon, centroid_lat FROM plot"
    ).fetchall()
    for plot_id, boundary_json, stored, lon, lat in rows:
        try:
            shape = geometry.to_shape(GeoJSONPolygon.model_validate_json(boundary_json))
        except ValueError:
            continue  # an invalid stored boundary is left as it is
        query = geometry.query_area(shape).model_dump_json()
        point = geometry.query_point(shape)
        same = (stored is not None and json.loads(stored) == json.loads(query)
                and abs(lon - point[0]) < 1e-9 and abs(lat - point[1]) < 1e-9)
        if not same:
            connection.exec_driver_sql(
                "UPDATE plot SET query_geometry_json = ?, centroid_lon = ?, centroid_lat = ? "
                "WHERE id = ?", (query, point[0], point[1], plot_id))
