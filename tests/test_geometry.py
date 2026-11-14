import pytest

from app.models.farms import GeoJSONPolygon
from app.services.geometry import area_ha, centroid, to_shape


def poly(ring):
    return GeoJSONPolygon(type="Polygon", coordinates=[ring])


SQUARE = [(-37.05, -10.27), (-37.04, -10.27), (-37.04, -10.26), (-37.05, -10.26), (-37.05, -10.27)]


def test_area_of_known_square():
    assert area_ha(to_shape(poly(SQUARE))) == pytest.approx(121.9, rel=0.01)


def test_centroid_is_lon_lat():
    lon, lat = centroid(to_shape(poly(SQUARE)))
    assert (lon, lat) == pytest.approx((-37.045, -10.265))


def test_open_ring_rejected():
    with pytest.raises(ValueError, match="closed"):
        to_shape(poly(SQUARE[:-1]))


def test_too_few_points_rejected():
    with pytest.raises(ValueError, match="at least"):
        to_shape(poly(SQUARE[:2] + [SQUARE[0]]))


def test_self_intersecting_rejected():
    bowtie = [(-37.05, -10.27), (-37.04, -10.26), (-37.04, -10.27), (-37.05, -10.26),
              (-37.05, -10.27)]
    with pytest.raises(ValueError, match="invalid"):
        to_shape(poly(bowtie))


def test_empty_polygon_rejected():
    with pytest.raises(ValueError, match="at least"):
        to_shape(GeoJSONPolygon(type="Polygon", coordinates=[]))


@pytest.mark.parametrize("hole", [[], SQUARE[:2] + [SQUARE[0]], SQUARE[:-1]])
def test_invalid_hole_rejected(hole):
    with pytest.raises(ValueError, match="hole"):
        to_shape(GeoJSONPolygon(type="Polygon", coordinates=[SQUARE, hole]))
