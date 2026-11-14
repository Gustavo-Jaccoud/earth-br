import pytest
from pydantic import TypeAdapter

from app.models.crops import Crop
from app.models.maps import MapLayerIndex
from app.models.quiz import Question
from app.models.regional import CausesResponse, LossRanking
from app.models.reports import Report, ReportSummary
from app.models.rotation import RotationResponse
from app.models.satellite import SatelliteSeries

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[-37.05, -10.27], [-37.04, -10.27], [-37.04, -10.26], [-37.05, -10.26],
                     [-37.05, -10.27]]],
}
ROTATION_BODY = {"options": [["milho", "feijao"], ["sorgo", "feijao_caupi"]]}

# (method, path, body, expected status, response type)
EXAMPLE_ROUTES = [
    ("GET", "/plots/1/satellite/ndvi", None, 200, SatelliteSeries),
    ("POST", "/plots/1/rotation/compare", ROTATION_BODY, 200, RotationResponse),
    ("GET", "/regional/losses", None, 200, LossRanking),
    ("GET", "/regional/causes", None, 200, CausesResponse),
    ("GET", "/maps/ndvi", None, 200, MapLayerIndex),
    ("POST", "/plots/1/reports/analysis", None, 201, Report),
    ("GET", "/reports", None, 200, list[ReportSummary]),
    ("GET", "/reports/1", None, 200, Report),
    ("GET", "/quiz", None, 200, list[Question]),
    ("POST", "/plots/1/quiz", {"answers": {}}, 201, Report),
]

EXPECTED_PATHS = {
    "/health", "/farms", "/farms/{farm_id}", "/farms/{farm_id}/plots", "/plots/{plot_id}",
    "/plots/{plot_id}/climate", "/plots/{plot_id}/signals",
    "/plots/{plot_id}/satellite/{layer}", "/crops", "/plots/{plot_id}/rotation/compare",
    "/regional/losses", "/regional/causes", "/maps/{layer}", "/plots/{plot_id}/reports/analysis",
    "/reports", "/reports/{report_id}", "/quiz", "/plots/{plot_id}/quiz",
    "/reports/{report_id}/pdf",
}


def test_all_routes_in_openapi(client):
    paths = set(client.get("/openapi.json").json()["paths"])
    assert EXPECTED_PATHS <= paths


@pytest.mark.parametrize("method,path,body,status,model", EXAMPLE_ROUTES)
def test_example_responses_validate(client, method, path, body, status, model):
    response = client.request(method, path, json=body)
    assert response.status_code == status, response.text
    TypeAdapter(model).validate_python(response.json())


def test_crops_endpoint_lists_config_crops(client):
    crops = TypeAdapter(list[Crop]).validate_python(client.get("/crops").json())
    expected = {"milho", "feijao", "feijao_caupi", "sorgo", "mandioca", "palma"}
    assert {c.id for c in crops} >= expected
