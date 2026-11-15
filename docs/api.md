# Earth+br API — referência

Documentação interativa (com botão **Try it out**): rode a API e abra **http://localhost:8000/docs** (Swagger) ou **http://localhost:8000/redoc** (ReDoc). O contrato completo, para gerar clientes, está em [`openapi.json`](openapi.json).

> Gerado por `python -m app.export_openapi` — não edite à mão.

Dados da **NASA** (POWER, SMAP, GPM, MODIS) e da **FAO** (GAEZ) traduzidos para o produtor rural do
Nordeste: semáforos de chuva e umidade do solo, comparação de rotação de culturas, aptidão de cada
cultura no local e relatórios em linguagem simples.

**Fluxo típico:** cadastrar propriedade → desenhar talhão (polígono) → ver os semáforos →
comparar rotações → gerar relatório (e baixar o PDF).

**Convenções:** datas em `AAAA-MM-DD`; coordenadas em `[longitude, latitude]` (GeoJSON, WGS84);
erros no formato `{"detail": "mensagem em português"}`. `503` significa que a NASA POWER está
indisponível e não há dados salvos para o local.

Os dados da NASA têm cerca de 2 dias de atraso: datas de referência mais recentes são ajustadas
automaticamente (`reference_date_adjusted`).

## Sistema

Verificação de saúde do servidor.

| Rota | O que faz |
|---|---|
| `GET /health` | Verificar se o servidor está no ar |

## Propriedades

Cadastro de propriedades e dos talhões (polígonos GeoJSON) de cada uma.

| Rota | O que faz |
|---|---|
| `GET /farms` | Listar propriedades |
| `POST /farms` | Cadastrar propriedade |
| `GET /farms/{farm_id}` | Buscar propriedade |
| `POST /farms/{farm_id}/plots` | Cadastrar talhão (polígono GeoJSON) |
| `GET /farms/{farm_id}/plots` | Listar talhões da propriedade |
| `GET /plots/{plot_id}` | Buscar talhão |

**`GET /farms/{farm_id}`** — `farm_id` (path, obrigatório, integer)

**`POST /farms/{farm_id}/plots`** — `farm_id` (path, obrigatório, integer)

**`GET /farms/{farm_id}/plots`** — `farm_id` (path, obrigatório, integer)

**`GET /plots/{plot_id}`** — `plot_id` (path, obrigatório, integer)

## Clima

Série diária da NASA POWER no ponto do talhão (chuva, temperatura, umidade do solo, radiação).

| Rota | O que faz |
|---|---|
| `GET /plots/{plot_id}/climate` | Série diária de clima (NASA POWER) |
| `GET /plots/{plot_id}/climate/monthly` | Série mensal de clima contra a normal |

**`GET /plots/{plot_id}/climate`** — `plot_id` (path, obrigatório, integer), `start` (query, enum), `end` (query, enum)

**`GET /plots/{plot_id}/climate/monthly`** — Monthly values for the last `months` months, each next to the historical normal for that
calendar month. NASA POWER: rain, root-zone soil moisture, mean and maximum air temperature,
reference evapotranspiration (Hargreaves), water balance (rain minus evapotranspiration) and
the longest run of dry days. Satellite (when the rasters exist): rain (GPM), soil moisture
(SMAP) and NDVI (MODIS); the ones without data are listed in `unavailable`. The current
month is partial (`complete: false`). Parâmetros: `plot_id` (path, obrigatório, integer), `months` (query, integer).

## Semáforos

Semáforos de chuva e umidade do solo: verde, amarelo ou vermelho, em comparação com a média histórica, com uma frase explicativa.

| Rota | O que faz |
|---|---|
| `GET /plots/{plot_id}/signals` | Semáforos de chuva e umidade do solo |

**`GET /plots/{plot_id}/signals`** — Semáforos de chuva e umidade do solo. `reference_date` além do último dado
disponível é ajustada automaticamente (`reference_date_adjusted`). Parâmetros: `plot_id` (path, obrigatório, integer), `reference_date` (query, enum).

## Satélite

Séries de NDVI (MODIS), umidade do solo (SMAP) e chuva (GPM) do talhão. Disponível só na região de demonstração (Aquidabã/SE).

| Rota | O que faz |
|---|---|
| `GET /plots/{plot_id}/satellite/{layer}` | Série de satélite do talhão |

**`GET /plots/{plot_id}/satellite/{layer}`** — `layer` (path, obrigatório, string), `plot_id` (path, obrigatório, integer), `start` (query, enum), `end` (query, enum)

## Culturas

Culturas conhecidas pelo comparador e seus parâmetros.

| Rota | O que faz |
|---|---|
| `GET /crops` | Listar culturas |

## Rotação

Comparador de rotação de culturas: risco hídrico, vigor do solo e aptidão da cultura no local.

| Rota | O que faz |
|---|---|
| `POST /plots/{plot_id}/rotation/compare` | Comparar rotações de culturas |

**`POST /plots/{plot_id}/rotation/compare`** — Compara sequências de culturas (ex.: milho → feijão) para o talhão: risco hídrico (chuva
histórica x necessidade da cultura), vigor do solo (NDVI) e aptidão da cultura no local
(FAO GAEZ). Parâmetros: `plot_id` (path, obrigatório, integer).

## Panorama do local

Aptidão de cada cultura no local (FAO GAEZ) e histórico de anos secos (NASA POWER).

| Rota | O que faz |
|---|---|
| `GET /plots/{plot_id}/suitability` | Aptidão das culturas no local (FAO GAEZ) |
| `GET /plots/{plot_id}/dry-years` | Anos secos do local (NASA POWER) |

**`GET /plots/{plot_id}/suitability`** — Culturas ordenadas pela aptidão ao clima e solo do local, em sequeiro e com baixo uso de
insumos (FAO GAEZ v4, clima 1981-2010), com o rendimento atingível em kg de matéria seca
por hectare. `without_data` lista as culturas que o GAEZ não cobre neste ponto. Parâmetros: `plot_id` (path, obrigatório, integer).

**`GET /plots/{plot_id}/dry-years`** — Chuva da estação chuvosa do local (os 5 meses seguidos mais chuvosos), ano a ano, e o
desvio em relação à normal de 2001-2020. Destaca os anos mais secos. Parâmetros: `plot_id` (path, obrigatório, integer).

## Mapa

Camadas de mapa (imagens mensais com limites) para sobrepor ao mapa.

| Rota | O que faz |
|---|---|
| `GET /maps/{layer}` | Camada de mapa (imagens mensais e limites) |

**`GET /maps/{layer}`** — Camada de mapa (PNG mensal + limites) para sobrepor ao mapa do frontend. Parâmetros: `layer` (path, obrigatório, string).

## Relatórios

Relatórios de análise salvos, com exportação em PDF.

| Rota | O que faz |
|---|---|
| `POST /plots/{plot_id}/reports/analysis` | Gerar relatório de análise do talhão |
| `GET /reports` | Listar relatórios |
| `GET /reports/{report_id}` | Buscar relatório |
| `GET /reports/{report_id}/pdf` | Baixar relatório em PDF |

**`POST /plots/{plot_id}/reports/analysis`** — Gera e salva o relatório de análise do talhão (condição atual, rotação opcional,
aptidão das culturas e anos secos). Parâmetros: `plot_id` (path, obrigatório, integer).

**`GET /reports`** — `plot_id` (query, enum)

**`GET /reports/{report_id}`** — `report_id` (path, obrigatório, integer)

**`GET /reports/{report_id}/pdf`** — The report as a PDF. The file is stored when the report is created and served from
disk afterwards (it is generated again if the stored file is missing). Parâmetros: `report_id` (path, obrigatório, integer).

## Assistente

Assistente de demonstração (sem IA): respostas prontas preenchidas com os dados reais do talhão.

| Rota | O que faz |
|---|---|
| `GET /chat/suggestions` | Saudação e perguntas sugeridas do assistente |
| `POST /plots/{plot_id}/chat` | Perguntar ao assistente de demonstração |

**`GET /chat/suggestions`** — Greeting and starter questions for an empty chat.

**`POST /plots/{plot_id}/chat`** — Demo assistant (no AI): finds the topic of the question by keywords and answers with a
pre-written text filled with the field's real data. When the data is missing the answer is
the topic's fixed text (`used_data: false`); an unrelated question gets a generic answer
(`topic: "generic"`). Texts and keywords live in `app/config/chat.yaml`. Parâmetros: `plot_id` (path, obrigatório, integer).

## Partida rápida

Trilha de perguntas que gera o relatório final com risco, impacto e sugestões.

| Rota | O que faz |
|---|---|
| `GET /quiz` | Perguntas da trilha (partida rápida) |
| `POST /plots/{plot_id}/quiz` | Enviar respostas e gerar o relatório final |

**`GET /quiz`** — Perguntas da trilha (sem os pesos de risco e sugestões, que ficam no backend).

**`POST /plots/{plot_id}/quiz`** — Responde a trilha e devolve o relatório final: risco, impacto ambiental e financeiro
e sugestões de contenção de danos. Parâmetros: `plot_id` (path, obrigatório, integer).

## Exemplo de fluxo

```bash
# 1. propriedade e talhão (o polígono é GeoJSON, em [longitude, latitude])
curl -X POST localhost:8000/farms -H 'content-type: application/json' \
  -d '{"name": "Demo Farm", "municipality": "Aquidabã", "state": "SE"}'
curl -X POST localhost:8000/farms/1/plots -H 'content-type: application/json' \
  -d '{"name": "Field 1", "current_crop": "milho", "geometry": {"type": "Polygon",
       "coordinates": [[[-37.05,-10.27],[-37.04,-10.27],[-37.04,-10.26],
                        [-37.05,-10.26],[-37.05,-10.27]]]}}'

# 2. semáforos (hoje e numa data da estação chuvosa)
curl localhost:8000/plots/1/signals
curl 'localhost:8000/plots/1/signals?reference_date=2022-06-30'

# 3. comparar rotações
curl -X POST localhost:8000/plots/1/rotation/compare -H 'content-type: application/json' \
  -d '{"options": [["milho", "feijao"], ["sorgo", "feijao_caupi"]]}'

# 4. panorama regional
curl 'localhost:8000/regional/losses'                       # Nordeste
curl 'localhost:8000/regional/causes?crop=milho'            # causas em Aquidabã

# 5. relatório e PDF
curl -X POST localhost:8000/plots/1/reports/analysis
curl -o relatorio.pdf localhost:8000/reports/1/pdf
```
