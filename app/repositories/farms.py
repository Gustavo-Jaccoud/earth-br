from sqlmodel import Session, select

from app.models.farms import Farm, FarmCreate, GeoJSONPolygon, Plot, PlotCreate
from app.repositories.region import Region
from app.repositories.tables import FarmRow, PlotRow
from app.services import geometry


def _plot(row: PlotRow) -> Plot:
    boundary = GeoJSONPolygon.model_validate_json(row.geometry_json)
    # Rows without a stored query area get it computed on the fly.
    query = (GeoJSONPolygon.model_validate_json(row.query_geometry_json)
             if row.query_geometry_json else geometry.query_area(geometry.to_shape(boundary)))
    return Plot(
        id=row.id,
        farm_id=row.farm_id,
        name=row.name,
        current_crop=row.current_crop,
        geometry=boundary,
        query_geometry=query,
        centroid=(row.centroid_lon, row.centroid_lat),
        area_ha=row.area_ha,
        in_demo_region=row.in_demo_region,
    )


class FarmRepository:
    def __init__(self, session: Session, region: Region):
        self.session = session
        self.region = region

    def create_farm(self, data: FarmCreate) -> Farm:
        row = FarmRow(**data.model_dump())
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return Farm.model_validate(row, from_attributes=True)

    def list_farms(self) -> list[Farm]:
        rows = self.session.exec(select(FarmRow).order_by(FarmRow.id)).all()
        return [Farm.model_validate(r, from_attributes=True) for r in rows]

    def get_farm(self, farm_id: int) -> Farm | None:
        row = self.session.get(FarmRow, farm_id)
        return Farm.model_validate(row, from_attributes=True) if row else None

    def create_plot(self, farm_id: int, data: PlotCreate) -> Plot:
        """Levanta ValueError se a geometria for inválida (nada é gravado)."""
        shape = geometry.to_shape(data.geometry)
        lon, lat = geometry.query_point(shape)
        row = PlotRow(
            farm_id=farm_id,
            name=data.name,
            current_crop=data.current_crop,
            geometry_json=data.geometry.model_dump_json(),
            query_geometry_json=geometry.query_area(shape).model_dump_json(),
            centroid_lon=lon,
            centroid_lat=lat,
            area_ha=round(geometry.area_ha(shape), 4),
            in_demo_region=self.region.contains(shape),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _plot(row)

    def list_plots(self, farm_id: int) -> list[Plot]:
        rows = self.session.exec(
            select(PlotRow).where(PlotRow.farm_id == farm_id).order_by(PlotRow.id)
        ).all()
        return [_plot(r) for r in rows]

    def get_plot(self, plot_id: int) -> Plot | None:
        row = self.session.get(PlotRow, plot_id)
        return _plot(row) if row else None
