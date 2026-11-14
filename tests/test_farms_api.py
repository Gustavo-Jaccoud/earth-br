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
