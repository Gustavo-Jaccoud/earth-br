"""Gera a documentação estática da API: docs/openapi.json e docs/api.md.

Uso:  python -m app.export_openapi
"""
import json
from pathlib import Path

from app.api_docs import TAGS
from app.main import create_app
from app.settings import Settings

METHODS = ("get", "post", "put", "patch", "delete")
CURL_FLOW = """\
```bash
# 1. propriedade e talhão (o polígono é GeoJSON, em [longitude, latitude])
curl -X POST localhost:8000/farms -H 'content-type: application/json' \\
  -d '{"name": "Sítio Demonstração", "municipality": "Aquidabã", "state": "SE"}'
curl -X POST localhost:8000/farms/1/plots -H 'content-type: application/json' \\
  -d '{"name": "Talhão 1", "current_crop": "milho", "geometry": {"type": "Polygon",
       "coordinates": [[[-37.05,-10.27],[-37.04,-10.27],[-37.04,-10.26],
                        [-37.05,-10.26],[-37.05,-10.27]]]}}'

# 2. semáforos (hoje e numa data da estação chuvosa)
curl localhost:8000/plots/1/signals
curl 'localhost:8000/plots/1/signals?reference_date=2022-06-30'

# 3. comparar rotações
curl -X POST localhost:8000/plots/1/rotation/compare -H 'content-type: application/json' \\
  -d '{"options": [["milho", "feijao"], ["sorgo", "feijao_caupi"]]}'

# 4. panorama regional
curl 'localhost:8000/regional/losses'                       # Nordeste
curl 'localhost:8000/regional/causes?crop=milho'            # causas em Aquidabã

# 5. relatório e PDF
curl -X POST localhost:8000/plots/1/reports/analysis
curl -o relatorio.pdf localhost:8000/reports/1/pdf
```"""


def _params(operation: dict) -> str:
    parts = []
    for p in operation.get("parameters", []):
        kind = p.get("schema", {}).get("type") or "enum"
        parts.append(f"`{p['name']}` ({p['in']}{', obrigatório' if p.get('required') else ''}, "
                     f"{kind})")
    return ", ".join(parts)


def build_markdown(spec: dict) -> str:
    ops = [(m.upper(), path, op) for path, item in spec["paths"].items()
           for m, op in item.items() if m in METHODS]
    lines = [
        f"# {spec['info']['title']} — referência", "",
        "Documentação interativa (com botão **Try it out**): rode a API e abra "
        "**http://localhost:8000/docs** (Swagger) ou **http://localhost:8000/redoc** (ReDoc). "
        "O contrato completo, para gerar clientes, está em [`openapi.json`](openapi.json).", "",
        "> Gerado por `python -m app.export_openapi` — não edite à mão.", "",
        spec["info"]["description"].strip(), "",
    ]
    for tag in TAGS:
        rows = [(m, path, op) for m, path, op in ops if tag["name"] in op.get("tags", [])]
        if not rows:
            continue
        lines += [f"## {tag['name'].capitalize()}", "", tag["description"], "",
                  "| Rota | O que faz |", "|---|---|"]
        lines += [f"| `{m} {path}` | {op['summary']} |" for m, path, op in rows]
        lines.append("")
        for m, path, op in rows:
            details = [d for d in (op.get("description", "").strip().split("\n\n")[0],
                                   _params(op)) if d]
            if details:
                lines += [f"**`{m} {path}`** — " + " ".join(
                    d if i == 0 else f"Parâmetros: {d}." for i, d in enumerate(details)), ""]
    lines += ["## Exemplo de fluxo", "", CURL_FLOW, ""]
    return "\n".join(lines)


def main(out_dir: Path = Path("docs")) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = create_app(Settings(var_dir=out_dir / ".unused")).openapi()
    (out_dir / "openapi.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "api.md").write_text(build_markdown(spec), encoding="utf-8")
    print(f"gravado {out_dir / 'openapi.json'} e {out_dir / 'api.md'}")


if __name__ == "__main__":
    main()
