"""Textos da documentação da API (Swagger/ReDoc): descrição geral, seções e resumos das rotas."""
from fastapi import FastAPI

DESCRIPTION = """
Dados da **NASA** (POWER, SMAP, GPM, MODIS) e do **IBGE** traduzidos para o produtor rural do
Nordeste: semáforos de chuva e umidade do solo, comparação de rotação de culturas, perdas por
cultura na região e relatórios em linguagem simples.

**Fluxo típico:** cadastrar propriedade → desenhar talhão (polígono) → ver os semáforos →
comparar rotações → gerar relatório (e baixar o PDF).

**Convenções:** datas em `AAAA-MM-DD`; coordenadas em `[longitude, latitude]` (GeoJSON, WGS84);
erros no formato `{"detail": "mensagem em português"}`. `503` significa que a NASA POWER está
indisponível e não há dados salvos para o local.

Os dados da NASA têm cerca de 2 dias de atraso: datas de referência mais recentes são ajustadas
automaticamente (`reference_date_adjusted`).
"""

TAGS = [
    {"name": "sistema", "description": "Verificação de saúde do servidor."},
    {"name": "propriedades",
     "description": "Cadastro de propriedades e dos talhões (polígonos GeoJSON) de cada uma."},
    {"name": "clima",
     "description": "Série diária da NASA POWER no ponto do talhão (chuva, temperatura, "
                    "umidade do solo, radiação)."},
    {"name": "semáforos",
     "description": "Semáforos de chuva e umidade do solo: verde, amarelo ou vermelho, em "
                    "comparação com a média histórica, com uma frase explicativa."},
    {"name": "satélite",
     "description": "Séries de NDVI (MODIS), umidade do solo (SMAP) e chuva (GPM) do talhão. "
                    "Disponível só na região de demonstração (Aquidabã/SE)."},
    {"name": "culturas", "description": "Culturas conhecidas pelo comparador e seus parâmetros."},
    {"name": "rotação",
     "description": "Comparador de rotação de culturas: risco hídrico, vigor do solo e perda "
                    "regional."},
    {"name": "panorama regional",
     "description": "Ranking de culturas com maior perda no Nordeste (IBGE) e causas "
                    "ambientais na região de demonstração."},
    {"name": "mapa",
     "description": "Camadas de mapa (imagens mensais com limites) para sobrepor ao mapa."},
    {"name": "relatórios",
     "description": "Relatórios de análise salvos, com exportação em PDF."},
    {"name": "partida rápida",
     "description": "Trilha de perguntas que gera o relatório final com risco, impacto e "
                    "sugestões."},
]

SUMMARIES = {
    ("GET", "/health"): "Verificar se o servidor está no ar",
    ("POST", "/farms"): "Cadastrar propriedade",
    ("GET", "/farms"): "Listar propriedades",
    ("GET", "/farms/{farm_id}"): "Buscar propriedade",
    ("POST", "/farms/{farm_id}/plots"): "Cadastrar talhão (polígono GeoJSON)",
    ("GET", "/farms/{farm_id}/plots"): "Listar talhões da propriedade",
    ("GET", "/plots/{plot_id}"): "Buscar talhão",
    ("GET", "/plots/{plot_id}/climate"): "Série diária de clima (NASA POWER)",
    ("GET", "/plots/{plot_id}/signals"): "Semáforos de chuva e umidade do solo",
    ("GET", "/plots/{plot_id}/satellite/{layer}"): "Série de satélite do talhão",
    ("GET", "/crops"): "Listar culturas",
    ("POST", "/plots/{plot_id}/rotation/compare"): "Comparar rotações de culturas",
    ("GET", "/regional/losses"): "Ranking de perdas por cultura (IBGE)",
    ("GET", "/regional/causes"): "Causas ambientais das perdas na região",
    ("GET", "/maps/{layer}"): "Camada de mapa (imagens mensais e limites)",
    ("POST", "/plots/{plot_id}/reports/analysis"): "Gerar relatório de análise do talhão",
    ("GET", "/reports"): "Listar relatórios",
    ("GET", "/reports/{report_id}"): "Buscar relatório",
    ("GET", "/reports/{report_id}/pdf"): "Baixar relatório em PDF",
    ("GET", "/quiz"): "Perguntas da trilha (partida rápida)",
    ("POST", "/plots/{plot_id}/quiz"): "Enviar respostas e gerar o relatório final",
}


def apply_docs(app: FastAPI) -> None:
    """Põe os resumos em português no esquema OpenAPI (Swagger, ReDoc e openapi.json)."""
    generate = app.openapi

    def openapi() -> dict:
        schema = generate()  # o FastAPI guarda o resultado em app.openapi_schema
        for path, item in schema["paths"].items():
            for method, operation in item.items():
                summary = SUMMARIES.get((method.upper(), path))
                if summary:
                    operation["summary"] = summary
        return schema

    app.openapi = openapi
