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
    assert {"rain", "soil_moisture", "temperature"} <= set(by_id)
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


# ---------------------------------------------------------------------------------------------
# Variáveis novas: temperatura máxima, ET0, balanço hídrico, sequência seca e satélite
# ---------------------------------------------------------------------------------------------

def full_frame(start, end, rain=1.0):
    index = pd.date_range(start, end)
    return pd.DataFrame({"PRECTOTCORR": rain, "T2M": 27.0, "T2M_MAX": 32.0, "T2M_MIN": 22.0,
                         "GWETROOT": 0.5, "TOA_SW_DWN": 39.5}, index=index)


def test_new_power_variables_normals():
    normals = monthly.normals(full_frame("2001-01-01", "2020-12-31"))
    assert normals["temperature_max"][3] == pytest.approx(32.0)
    assert normals["et0"][1] == pytest.approx(31 * 5.2515, rel=1e-3)  # Hargreaves, 5,25 mm/dia
    assert normals["water_balance"][1] == pytest.approx(31 * (1.0 - 5.2515), rel=1e-3)
    assert normals["dry_spell"][1] == 0.0  # chove 1 mm todo dia: nenhum dia seco


def test_dry_spell_is_longest_run_of_days_below_threshold():
    data = full_frame("2026-01-01", "2026-01-31")
    data.loc["2026-01-03":"2026-01-06", "PRECTOTCORR"] = 0.0   # 4 dias
    data.loc["2026-01-10":"2026-01-11", "PRECTOTCORR"] = 0.4   # 2 dias (abaixo de 1 mm)
    data.loc["2026-01-20":"2026-01-26", "PRECTOTCORR"] = 0.0   # 7 dias
    months = monthly.last_months(data, pd.Timestamp("2026-01-31").date(), 1)
    assert months["dry_spell"][0].value == 7.0


def test_dry_spell_run_is_broken_by_missing_days():
    data = full_frame("2026-01-01", "2026-01-31", rain=0.0)
    data.loc["2026-01-16", "PRECTOTCORR"] = float("nan")
    months = monthly.last_months(data, pd.Timestamp("2026-01-31").date(), 1)
    assert months["dry_spell"][0].value == 15.0


def test_water_balance_month_value():
    data = full_frame("2026-01-01", "2026-01-31", rain=10.0)
    months = monthly.last_months(data, pd.Timestamp("2026-01-31").date(), 1)
    assert months["water_balance"][0].value == pytest.approx(31 * (10.0 - 5.2515), rel=1e-3)
    assert months["et0"][0].value == pytest.approx(31 * 5.2515, rel=1e-3)


def test_satellite_months_and_normals():
    index = pd.date_range("2015-01-01", "2026-11-11")
    series = pd.Series([4.0 if d.year == 2026 else 2.0 for d in index], index=index)
    months, normals = monthly.satellite_months(series, pd.Timestamp("2026-11-11").date(), 3,
                                               "sum", 1.0)
    assert [m.label for m in months] == ["2026-09", "2026-10", "2026-11"]
    assert months[1].value == pytest.approx(124.0) and months[1].complete
    assert months[2].value == pytest.approx(44.0) and not months[2].complete
    assert normals[10] == pytest.approx(62.0)  # média de outubro em 2015-2025, sem o ano em curso


def test_satellite_months_without_recent_data_are_none():
    index = pd.date_range("2015-01-01", "2025-09-30")
    months, _ = monthly.satellite_months(pd.Series(2.0, index=index),
                                         pd.Timestamp("2026-11-11").date(), 3, "sum", 1.0)
    assert [m.value for m in months] == [None, None, None]


def test_monthly_endpoint_has_new_variables_and_lists_missing_satellite(client, tmp_path):
    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    body = client.get(f"/plots/{plot['id']}/climate/monthly").json()
    by_id = {v["variable"]: v for v in body["variables"]}
    assert set(by_id) == {"rain", "soil_moisture", "temperature", "temperature_max", "et0",
                          "water_balance", "dry_spell"}
    assert by_id["dry_spell"]["unit"] == "days" and by_id["water_balance"]["unit"] == "mm"
    assert all(v["source"] == "NASA POWER" and v["normal_period"] == "2001-2020"
               for v in by_id.values())
    assert all(len(v["months"]) == 12 for v in by_id.values())
    assert by_id["temperature_max"]["months"][-2]["value"] > by_id["temperature"]["months"][-2][
        "value"]
    assert body["unavailable"] == ["rain_satellite", "soil_moisture_satellite", "ndvi"]
    assert "NaN" not in client.get(f"/plots/{plot['id']}/climate/monthly").text


def test_monthly_endpoint_includes_satellite_when_rasters_exist(client, tmp_path):
    from app.repositories.rasters import RasterStore
    from tests.helpers import make_layer

    plot = make_plot(client)
    install_power(client, tmp_path, plot)
    make_layer(tmp_path, "ndvi", "2018-01-01", "2026-11-11", value=0.4, source="NASA MODIS",
               units="1")
    make_layer(tmp_path, "precipitation", "2015-01-01", "2025-09-30", value=2.0,
               source="NASA GPM IMERG")
    client.app.state.rasters = RasterStore(tmp_path)
    body = client.get(f"/plots/{plot['id']}/climate/monthly?months=24").json()
    by_id = {v["variable"]: v for v in body["variables"]}
    assert body["unavailable"] == ["soil_moisture_satellite"]
    ndvi = by_id["ndvi"]
    assert ndvi["source"] == "NASA MODIS" and ndvi["unit"] == "" and ndvi["normal_period"] == (
        "2018-2025")
    assert ndvi["months"][-2]["value"] == pytest.approx(0.4)
    assert "underestimates" in by_id["rain_satellite"]["note"] and by_id["ndvi"]["note"] is None
    assert by_id["rain"]["note"] is None
    rain = by_id["rain_satellite"]["months"]
    assert rain[-1]["value"] is None  # o GPM termina em set/2025
    assert next(m for m in rain if m["label"] == "2025-06")["value"] == pytest.approx(60.0)
