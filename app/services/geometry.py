import math

from shapely.geometry import Polygon

from app.models.farms import GeoJSONPolygon

METERS_PER_DEGREE = 111_320


def _check_ring(ring: list[tuple[float, float]], what: str) -> None:
    if len(ring) < 4:
        raise ValueError(f"{what} precisa de pelo menos 4 pontos (o último igual ao primeiro).")
    if ring[0] != ring[-1]:
        raise ValueError(f"{what} precisa estar fechado: o último ponto igual ao primeiro.")


def to_shape(geom: GeoJSONPolygon) -> Polygon:
    """Converte o GeoJSON em polígono shapely; ValueError (em português) se for inválido."""
    rings = geom.coordinates or [[]]  # polígono vazio cai na checagem de "pelo menos 4 pontos"
    _check_ring(rings[0], "O polígono")
    for hole in rings[1:]:
        _check_ring(hole, "O buraco do polígono")
    poly = Polygon(rings[0], holes=rings[1:])
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
