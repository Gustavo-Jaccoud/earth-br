import pytest

SQUARE = [[-37.05, -10.27], [-37.04, -10.27], [-37.04, -10.26], [-37.05, -10.26], [-37.05, -10.27]]
FAR_SQUARE = [[-40.51, -9.41], [-40.50, -9.41], [-40.50, -9.40], [-40.51, -9.40], [-40.51, -9.41]]
BOWTIE = [[-37.05, -10.27], [-37.04, -10.26], [-37.04, -10.27], [-37.05, -10.26], [-37.05, -10.27]]


def make_farm(client):
    body = {"name": "Sítio Demonstração", "municipality": "Aquidabã", "state": "SE"}
    response = client.post("/farms", json=body)
    assert response.status_code == 201
    return response.json()


def plot_body(ring, name="Talhão 1"):
    return {"name": name, "geometry": {"type": "Polygon", "coordinates": [ring]}}


def test_create_plot_in_demo_region(client):
    farm = make_farm(client)
    response = client.post(f"/farms/{farm['id']}/plots", json=plot_body(SQUARE))
    assert response.status_code == 201
    plot = response.json()
    assert plot["in_demo_region"] is True
    assert plot["area_ha"] > 0
    assert plot["farm_id"] == farm["id"]
    assert client.get(f"/plots/{plot['id']}").json() == plot
    assert client.get(f"/farms/{farm['id']}/plots").json() == [plot]


def test_create_plot_outside_region(client):
    farm = make_farm(client)
    plot = client.post(f"/farms/{farm['id']}/plots", json=plot_body(FAR_SQUARE)).json()
    assert plot["in_demo_region"] is False


def test_invalid_polygon_422_and_not_saved(client):
    farm = make_farm(client)
    response = client.post(f"/farms/{farm['id']}/plots", json=plot_body(BOWTIE))
    assert response.status_code == 422
    assert "invalid" in response.json()["detail"]
    assert client.get(f"/farms/{farm['id']}/plots").json() == []


def test_farms_listed_and_fetched(client):
    farm = make_farm(client)
    assert client.get("/farms").json() == [farm]
    assert client.get(f"/farms/{farm['id']}").json() == farm


@pytest.mark.parametrize("path", ["/farms/999", "/plots/999", "/farms/999/plots"])
def test_unknown_ids_404(client, path):
    assert client.get(path).status_code == 404


def test_plot_on_unknown_farm_404(client):
    assert client.post("/farms/999/plots", json=plot_body(SQUARE)).status_code == 404


@pytest.mark.parametrize("coordinates", [[], [SQUARE, []]])
def test_empty_polygon_or_hole_422_not_500(client, coordinates):
    farm = make_farm(client)
    body = {"name": "T", "geometry": {"type": "Polygon", "coordinates": coordinates}}
    response = client.post(f"/farms/{farm['id']}/plots", json=body)
    assert response.status_code == 422
    assert client.get(f"/farms/{farm['id']}/plots").json() == []


# --- duas geometrias: limite real (visual) e quadrado de consulta (NASA POWER) ---------------

L_SHAPE = [[-37.050, -10.270], [-37.046, -10.270], [-37.046, -10.268], [-37.048, -10.268],
           [-37.048, -10.266], [-37.050, -10.266], [-37.050, -10.270]]


def ring_area_ha(ring):
    import math
    pairs = zip(ring, ring[1:], strict=False)
    area = abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in pairs)) / 2
    lat = sum(p[1] for p in ring[:-1]) / (len(ring) - 1)
    return area * 111_320**2 * math.cos(math.radians(lat)) / 10_000


def bounds(ring):
    return (min(p[0] for p in ring), min(p[1] for p in ring),
            max(p[0] for p in ring), max(p[1] for p in ring))


def test_irregular_boundary_is_kept_and_the_query_area_encloses_it(client):
    farm = make_farm(client)
    plot = client.post(f"/farms/{farm['id']}/plots", json=plot_body(L_SHAPE)).json()
    assert plot["geometry"]["coordinates"][0] == L_SHAPE  # limite real, como desenhado
    query = plot["query_geometry"]["coordinates"][0]
    assert len(query) == 5 and query[0] == query[-1]
    # retângulo alinhado aos eixos que envolve o polígono inteiro, justo nos seus limites
    assert bounds(query) == pytest.approx(bounds(L_SHAPE))
    assert len({p[0] for p in query}) == 2 and len({p[1] for p in query}) == 2
    west, south, east, north = bounds(query)
    assert all(west <= x <= east and south <= y <= north for x, y in L_SHAPE)
    assert ring_area_ha(query) > plot["area_ha"]  # o L ocupa 3/4 do retângulo
    assert plot["area_ha"] == pytest.approx(ring_area_ha(L_SHAPE), rel=0.01)  # área do limite real
    assert plot["centroid"] == pytest.approx([(west + east) / 2, (south + north) / 2])
    assert client.get(f"/plots/{plot['id']}").json() == plot


def test_triangle_far_from_its_centroid_square_is_fully_enclosed(client):
    # Um triângulo comprido: o quadrado de mesma área centrado no centroide deixaria pontas de
    # fora; a área de consulta tem de conter todos os vértices.
    triangle = [[-37.060, -10.270], [-37.020, -10.268], [-37.058, -10.262], [-37.060, -10.270]]
    farm = make_farm(client)
    plot = client.post(f"/farms/{farm['id']}/plots", json=plot_body(triangle)).json()
    west, south, east, north = bounds(plot["query_geometry"]["coordinates"][0])
    assert all(west <= x <= east and south <= y <= north for x, y in triangle)


def test_square_boundary_gets_the_same_square_as_query_area(client):
    farm = make_farm(client)
    plot = client.post(f"/farms/{farm['id']}/plots", json=plot_body(SQUARE)).json()
    assert bounds(plot["query_geometry"]["coordinates"][0]) == pytest.approx(bounds(SQUARE))
    assert plot["centroid"] == pytest.approx([-37.045, -10.265])


def test_stored_query_areas_from_the_old_rule_are_recomputed(client, settings):
    import json
    import sqlite3

    from fastapi.testclient import TestClient

    from app.main import create_app

    farm = make_farm(client)
    plot = client.post(f"/farms/{farm['id']}/plots", json=plot_body(L_SHAPE)).json()
    old = [[-37.0495, -10.2695], [-37.0465, -10.2695], [-37.0465, -10.2665], [-37.0495, -10.2665],
           [-37.0495, -10.2695]]  # quadrado de mesma área, que não envolve o L
    db = sqlite3.connect(settings.var_dir / "app.db")
    db.execute("UPDATE plot SET query_geometry_json = ?, centroid_lon = -37.0483 WHERE id = ?",
               (json.dumps({"type": "Polygon", "coordinates": [old]}), plot["id"]))
    db.commit()
    db.close()
    with TestClient(create_app(settings)) as restarted:
        again = restarted.get(f"/plots/{plot['id']}").json()
    assert bounds(again["query_geometry"]["coordinates"][0]) == pytest.approx(bounds(L_SHAPE))
    assert again["centroid"] == pytest.approx(plot["centroid"])


def test_database_from_before_query_geometry_is_migrated(tmp_path, settings):
    import sqlite3

    from fastapi.testclient import TestClient

    from app.main import create_app

    settings.var_dir.mkdir(parents=True)
    db = sqlite3.connect(settings.var_dir / "app.db")
    db.executescript("""
        CREATE TABLE farm (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL,
            municipality VARCHAR NOT NULL, state VARCHAR NOT NULL, ibge_code VARCHAR,
            owner VARCHAR);
        CREATE TABLE plot (id INTEGER PRIMARY KEY, farm_id INTEGER NOT NULL, name VARCHAR NOT NULL,
            current_crop VARCHAR, geometry_json VARCHAR NOT NULL, centroid_lon FLOAT NOT NULL,
            centroid_lat FLOAT NOT NULL, area_ha FLOAT NOT NULL, in_demo_region BOOLEAN NOT NULL);
        INSERT INTO farm VALUES (1, 'Antiga', 'Aquidabã', 'SE', NULL, NULL);
        INSERT INTO plot VALUES (1, 1, 'T1', 'milho',
            '{"type":"Polygon","coordinates":[[[-37.05,-10.27],[-37.04,-10.27],[-37.04,-10.26],[-37.05,-10.26],[-37.05,-10.27]]]}',
            -37.045, -10.265, 121.9, 1);
    """)
    db.commit()
    db.close()
    with TestClient(create_app(settings)) as old:
        plot = old.get("/plots/1").json()
        assert len(plot["query_geometry"]["coordinates"][0]) == 5
        assert old.get("/farms/1/plots").json()[0]["name"] == "T1"
