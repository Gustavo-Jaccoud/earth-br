from tests.helpers import LAST_VALID_DAY, install_power, make_plot


def test_climate_no_fill_values_and_missing_days_are_null(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    response = client.get(f"/plots/{plot['id']}/climate?start=2026-11-08&end=2026-11-14")
    assert response.status_code == 200
    body = response.json()
    assert "-999" not in response.text
    rain = next(s for s in body["series"] if s["variable"] == "PRECTOTCORR")
    assert rain["source"] == "NASA POWER" and rain["unit"] == "mm/day"
    assert len(rain["values"]) == 7
    assert rain["values"][-1]["value"] is None  # 14/11, ainda sem dado
    assert rain["values"][0]["value"] is not None


def test_climate_default_is_last_90_days_ending_at_last_valid_day(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    body = client.get(f"/plots/{plot['id']}/climate").json()
    assert body["end"] == LAST_VALID_DAY.isoformat()
    assert len(body["series"][0]["values"]) == 90


def test_climate_range_in_history_gap_is_null(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    body = client.get(f"/plots/{plot['id']}/climate?start=2023-12-30&end=2024-01-02").json()
    rain = next(s for s in body["series"] if s["variable"] == "PRECTOTCORR")["values"]
    assert [v["value"] is None for v in rain] == [False, False, True, True]


def test_climate_503_when_unavailable(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot, history=False, recent=False)
    response = client.get(f"/plots/{plot['id']}/climate")
    assert response.status_code == 503
    assert "NASA POWER" in response.json()["detail"]


def test_climate_start_after_end_422(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    assert client.get(f"/plots/{plot['id']}/climate?start=2026-11-10&end=2026-11-01"
                      ).status_code == 422


def test_climate_unknown_plot_404(client):
    assert client.get("/plots/999/climate").status_code == 404
