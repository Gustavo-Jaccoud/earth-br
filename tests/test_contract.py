from pydantic import TypeAdapter

from app.models.crops import Crop

EXPECTED_PATHS = {
    "/health", "/farms", "/farms/{farm_id}", "/farms/{farm_id}/plots", "/plots/{plot_id}",
    "/plots/{plot_id}/climate", "/plots/{plot_id}/climate/monthly",
    "/plots/{plot_id}/signals",
    "/plots/{plot_id}/satellite/{layer}", "/crops", "/plots/{plot_id}/rotation/compare",
    "/plots/{plot_id}/suitability", "/plots/{plot_id}/dry-years", "/maps/{layer}",
    "/plots/{plot_id}/reports/analysis",
    "/reports", "/reports/{report_id}", "/quiz", "/plots/{plot_id}/quiz",
    "/reports/{report_id}/pdf",
}


def test_all_routes_in_openapi(client):
    paths = set(client.get("/openapi.json").json()["paths"])
    assert EXPECTED_PATHS <= paths


def test_crops_endpoint_lists_config_crops(client):
    crops = TypeAdapter(list[Crop]).validate_python(client.get("/crops").json())
    expected = {"milho", "feijao", "feijao_caupi", "sorgo", "mandioca", "palma"}
    assert {c.id for c in crops} >= expected
