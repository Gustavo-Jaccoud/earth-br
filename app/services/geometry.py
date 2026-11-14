import math

from shapely.geometry import Polygon

from app.models.farms import GeoJSONPolygon

METERS_PER_DEGREE = 111_320


def to_shape(geom: GeoJSONPolygon) -> Polygon:
    """Converte o GeoJSON em polígono shapely; ValueError (em português) se for inválido."""
    shell = geom.coordinates[0]
    if len(shell) < 4:
        raise ValueError("O polígono precisa de pelo menos 4 pontos (o último igual ao primeiro).")
    if shell[0] != shell[-1]:
        raise ValueError("O polígono precisa estar fechado: o último ponto igual ao primeiro.")
    poly = Polygon(shell, holes=geom.coordinates[1:])
    if not poly.is_valid:
        raise ValueError("O polígono é inválido: as linhas do contorno se cruzam.")
    return poly


def centroid(poly: Polygon) -> tuple[float, float]:
    """(lon, lat) do centroide."""
    c = poly.centroid
    return (c.x, c.y)


def area_ha(poly: Polygon) -> float:
    """Área aproximada em hectares (projeção plana local, suficiente para talhões)."""
    lat = poly.centroid.y
    m2 = poly.area * METERS_PER_DEGREE**2 * math.cos(math.radians(lat))
    return m2 / 10_000
