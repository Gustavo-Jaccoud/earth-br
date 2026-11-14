import json

from app import export_openapi
from app.api_docs import SUMMARIES, TAGS
from app.main import create_app
from app.settings import Settings

METHODS = {"get", "post", "put", "delete", "patch"}


def operations(spec):
    return {(m.upper(), path): op for path, item in spec["paths"].items()
            for m, op in item.items() if m in METHODS}


def test_every_operation_has_a_portuguese_summary_and_known_tag(client):
    spec = client.get("/openapi.json").json()
    ops = operations(spec)
    assert set(ops) == set(SUMMARIES), "SUMMARIES precisa cobrir exatamente as rotas da API"
    tag_names = {t["name"] for t in TAGS}
    for key, op in ops.items():
        assert op["summary"] == SUMMARIES[key]
        assert set(op["tags"]) <= tag_names


def test_openapi_describes_the_api(client):
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"] == "Field Shift API"
    assert "NASA" in spec["info"]["description"]
    assert [t["name"] for t in spec["tags"]] == [t["name"] for t in TAGS]
    assert all(t["description"] for t in spec["tags"])


def test_swagger_and_redoc_are_served(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200


def test_export_writes_openapi_json_and_markdown(tmp_path):
    export_openapi.main(out_dir=tmp_path)
    spec = json.loads((tmp_path / "openapi.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "api.md").read_text(encoding="utf-8")
    assert set(spec["paths"]) >= {"/farms", "/plots/{plot_id}/signals"}
    for (method, path), summary in SUMMARIES.items():
        assert f"`{method} {path}`" in markdown and summary in markdown
    assert "/docs" in markdown and "curl" in markdown


def test_exported_spec_matches_running_app(tmp_path, settings):
    export_openapi.main(out_dir=tmp_path)
    exported = json.loads((tmp_path / "openapi.json").read_text(encoding="utf-8"))
    live = create_app(Settings(data_dir=settings.data_dir, var_dir=tmp_path / "v")).openapi()
    assert exported["paths"].keys() == live["paths"].keys()
