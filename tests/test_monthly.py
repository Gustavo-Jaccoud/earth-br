import pandas as pd
import pytest

from app.services import monthly
from tests.helpers import LAST_VALID_DAY, install_power, make_plot


def frame(start, end, rain=1.0, temp=25.0, soil=0.5):
    index = pd.date_range(start, end)
    return pd.DataFrame({"PRECTOTCORR": rain, "T2M": temp, "GWETROOT": soil}, index=index)


def test_normals_are_monthly_totals_for_rain_and_means_for_the_rest():
    normals = monthly.normals(frame("2001-01-01", "2020-12-31"))
    assert normals["rain"][1] == pytest.approx(31.0) and normals["rain"][4] == pytest.approx(30.0)
    assert normals["temperature"][7] == pytest.approx(25.0)
    assert normals["soil_moisture"][7] == pytest.approx(50.0)  # em %


def test_last_12_months_ends_at_reference_month_and_flags_partial_month():
    data = frame("2024-01-01", "2026-11-11")
    months = monthly.last_months(data, pd.Timestamp("2026-11-11").date(), 12)
    assert [m.label for m in months["rain"]][0] == "2025-12"
    assert [m.label for m in months["rain"]][-1] == "2026-11"
    assert months["rain"][-2].value == pytest.approx(31.0) and months["rain"][-2].complete
    assert months["rain"][-1].value == pytest.approx(11.0) and not months["rain"][-1].complete


def test_month_without_data_is_none():
    data = frame("2026-10-01", "2026-11-11")
    months = monthly.last_months(data, pd.Timestamp("2026-11-11").date(), 3)
    assert months["rain"][0].value is None and months["rain"][1].value == pytest.approx(31.0)


def test_monthly_endpoint(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    body = client.get(f"/plots/{plot['id']}/climate/monthly").json()
    assert body["source"] == "NASA POWER" and body["reference_date"] == LAST_VALID_DAY.isoformat()
    assert body["normal_period"] == "2001-2020"
    by_id = {v["variable"]: v for v in body["variables"]}
    assert set(by_id) == {"rain", "soil_moisture", "temperature"}
    assert by_id["rain"]["unit"] == "mm" and by_id["soil_moisture"]["unit"] == "%"
    rain = by_id["rain"]["months"]
    assert len(rain) == 12 and rain[-1]["label"] == "2026-11" and rain[0]["label"] == "2025-12"
    assert all(m["normal"] is not None and m["normal"] >= 0 for m in rain)
    assert rain[-1]["complete"] is False and rain[-2]["complete"] is True
    assert "-999" not in client.get(f"/plots/{plot['id']}/climate/monthly").text


def test_monthly_endpoint_months_param_and_limits(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    assert len(client.get(f"/plots/{plot['id']}/climate/monthly?months=6").json()["variables"][0][
        "months"]) == 6
    assert client.get(f"/plots/{plot['id']}/climate/monthly?months=0").status_code == 422
    assert client.get(f"/plots/{plot['id']}/climate/monthly?months=500").status_code == 422


def test_monthly_endpoint_503_without_power(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot, history=False, recent=False)
    assert client.get(f"/plots/{plot['id']}/climate/monthly").status_code == 503
