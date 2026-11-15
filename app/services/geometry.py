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


def query_area(poly: Polygon) -> GeoJSONPolygon:
    """Rectangle that encloses the whole polygon (its bounding box, aligned with the meridians
    and parallels). It is the spatial reference for NASA POWER queries: every part of the
    property lies inside it. For a square boundary it is the square itself."""
    west, south, east, north = poly.bounds
    ring = [(west, south), (east, south), (east, north), (west, north), (west, south)]
    return GeoJSONPolygon(type="Polygon", coordinates=[ring])


def query_point(poly: Polygon) -> tuple[float, float]:
    """(lon, lat) at the centre of the query area: the point sent to NASA POWER."""
    west, south, east, north = poly.bounds
    return ((west + east) / 2, (south + north) / 2)
