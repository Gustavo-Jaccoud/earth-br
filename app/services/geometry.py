import math

from shapely.geometry import Polygon

from app.models.farms import GeoJSONPolygon

METERS_PER_DEGREE = 111_320


def _check_ring(ring: list[tuple[float, float]], what: str) -> None:
    if len(ring) < 4:
        raise ValueError(f"{what} needs at least 4 points (the last equal to the first).")
    if ring[0] != ring[-1]:
        raise ValueError(f"{what} must be closed: the last point must equal the first.")


def to_shape(geom: GeoJSONPolygon) -> Polygon:
    """Converte o GeoJSON em polígono shapely; ValueError (em português) se for inválido."""
    rings = geom.coordinates or [[]]  # polígono vazio cai na checagem de "pelo menos 4 pontos"
    _check_ring(rings[0], "The polygon")
    for hole in rings[1:]:
        _check_ring(hole, "The polygon hole")
    poly = Polygon(rings[0], holes=rings[1:])
    if not poly.is_valid:
        raise ValueError("The polygon is invalid: its outline crosses itself.")
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


def query_square(poly: Polygon) -> GeoJSONPolygon:
    """Square with the same area as the polygon, centred on its centroid (same flat local
    projection as area_ha). It is the spatial reference used for NASA POWER queries."""
    lon, lat = centroid(poly)
    half_m = math.sqrt(area_ha(poly) * 10_000) / 2
    d_lat = half_m / METERS_PER_DEGREE
    d_lon = half_m / (METERS_PER_DEGREE * math.cos(math.radians(lat)))
    ring = [(lon - d_lon, lat - d_lat), (lon + d_lon, lat - d_lat), (lon + d_lon, lat + d_lat),
            (lon - d_lon, lat + d_lat), (lon - d_lon, lat - d_lat)]
    return GeoJSONPolygon(type="Polygon", coordinates=[ring])
