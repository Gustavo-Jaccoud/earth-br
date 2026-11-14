from pipeline import seed_demo


def test_seed_is_idempotent(client):
    first = seed_demo.main(client=client)
    second = seed_demo.main(client=client)
    assert first == second and len(first) == 2
    farms = client.get("/farms").json()
    assert len(farms) == 1 and farms[0]["ibge_code"] == "2800209"
    plots = client.get(f"/farms/{farms[0]['id']}/plots").json()
    assert [p["id"] for p in plots] == first
    assert all(p["in_demo_region"] for p in plots)


def test_seed_survives_missing_power_data(client):
    # POWER sem cache e sem internet: o seed termina mesmo assim (só avisa).
    assert len(seed_demo.main(client=client)) == 2
