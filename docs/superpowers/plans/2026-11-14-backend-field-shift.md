# Backend Field Shift — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** API FastAPI + pipeline de dados que transformam dados da NASA (POWER, SMAP, GPM, MODIS) e do IBGE em semáforos, comparador de rotação, panorama de perdas e relatórios para talhões no Nordeste, com demo em Aquidabã (SE).

**Architecture:** Abordagem A do spec: o pipeline (`pipeline/`) roda offline e grava arquivos pequenos em `data/`; a API (`app/`) lê esses arquivos, guarda propriedades/talhões/relatórios em SQLite e consulta o NASA POWER ao vivo com cache em disco versionado. Regras, culturas, perguntas e frases ficam em `app/config/*.yaml`.

**Tech Stack:** Python ≥3.10, FastAPI, Pydantic v2, SQLModel (SQLite), httpx, pandas, numpy, xarray + h5netcdf, shapely ≥2, PyYAML, reportlab; testes com pytest + respx; lint com ruff. Pipeline (extra opcional): requests, harmony-py, earthaccess, matplotlib.

**Spec:** `docs/superpowers/specs/2026-11-14-backend-field-shift-design.md`

## Global Constraints

- Python `>=3.10` (máquina de demo tem 3.10.12). Ambiente: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`.
- Sem autenticação. CORS liberado (`allow_origins=["*"]`).
- Rotas, nomes de campos JSON e código em inglês; **todo texto destinado ao usuário em português**, vindo de `app/config/phrases.yaml`. README e `docs/` em português.
- Toda série, semáforo e critério devolvido carrega `source` (ex.: `"NASA POWER"`, `"NASA SMAP"`, `"NASA GPM IMERG"`, `"NASA MODIS"`, `"IBGE PAM"`).
- Valor `-999` do POWER = ausente (`None`/`NaN`); nunca aparece numa resposta.
- Limiares, pesos, culturas, perguntas e frases **só** em `app/config/*.yaml`; nenhum número de regra no código.
- `data/` é versionado e deve ficar < 50 MB; downloads brutos vão para `data/raw/` (gitignored). Banco e PDFs em `var/` (gitignored).
- Região de demo: **Aquidabã (SE)**, IBGE `2800209`, bbox do município `[-37.1654, -10.375, -36.929, -10.1631]`; bbox da região de demo (com margem) `[-37.25, -10.45, -36.85, -10.10]` (`[min_lon, min_lat, max_lon, max_lat]`). Agricultura de **sequeiro**.
- NASA POWER: `GET https://power.larc.nasa.gov/api/temporal/daily/point`, `community=AG`, parâmetros `T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,GWETROOT,ALLSKY_SFC_SW_DWN,TOA_SW_DWN`. Normal climatológica = **2001–2020**. Histórico = `2001-01-01..2023-12-31`. Recente = últimos 400 dias até hoje.
- IBGE: SIDRA tabela `5457`, variáveis `8331` (área plantada, ha), `216` (área colhida, ha), `214` (produção), `112` (rendimento, kg/ha), anos 2010–2023.
- Commits pequenos, mensagem em inglês no formato `tipo: descrição`, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Data de referência além do último dado disponível** (o POWER atrasa ~2 dias e devolve `-999` no fim): a API ajusta para o último dia com dado e sinaliza `reference_date_adjusted: true`, sem 500 nem semáforo calculado sobre buraco. → teste na Task 5.
2. **Internet caída na apresentação:** POWER usa o cache; sem cache, resposta 503 com mensagem em português, nunca 500. → teste na Task 4.
3. **Talhão desenhado fora da região de demo:** rotas de satélite respondem 404 com explicação; semáforos caem para POWER; critério de solo do comparador vira "sem dado" e sai da pontuação. → testes nas Tasks 7 e 9.
4. **Polígono inválido** (anel aberto, auto-interseção, menos de 4 pontos): 422 com mensagem clara, nada é gravado. → teste na Task 3.
5. **Estação seca** (normal de chuva quase zero): sem divisão por zero nem percentual absurdo; semáforo usa limiar absoluto e frase de "período normalmente seco". → teste na Task 5.

---

## Estrutura de arquivos

```
pyproject.toml  .gitignore  README.md
app/
  main.py               create_app(), CORS, inclui routers, monta /static/maps
  settings.py           Settings (env): DATA_DIR, VAR_DIR, POWER_LIVE
  db.py                 engine SQLite, get_session(), init_db()
  config_loader.py      carrega e valida app/config/*.yaml
  config/               crops.yaml, signals.yaml, rotation.yaml, quiz.yaml, phrases.yaml
  models/               esquemas Pydantic da API (um arquivo por recurso)
  api/                  routers (um por recurso) + deps.py
  services/             geometry, climatology, texts, signals, water, rotation, losses, causes, reports, quiz, pdf
  clients/power.py      cliente NASA POWER com cache
  repositories/         tables.py (SQLModel), farms.py, reports.py, rasters.py, ibge.py, region.py
pipeline/
  README.md  region.py  ibge_pam.py  layers.py  appeears.py  gpm.py  render_maps.py  seed_demo.py
data/
  region.json  ibge/pam.csv  rasters/{ndvi,soil_moisture,precipitation}.nc  maps/<layer>/  cache/power/
docs/
  architecture.md  data-sources.md
tests/
  conftest.py  fixtures/  test_*.py
```

## Contratos de dados (pipeline → API)

- `data/region.json`: `{"name": "Aquidabã (SE)", "ibge_code": "2800209", "state_code": "28", "bbox": [-37.25, -10.45, -36.85, -10.10], "rainy_season_months": [4, 5, 6, 7, 8]}`
- `data/ibge/pam.csv` (formato longo): `level,territory_code,territory_name,crop,year,planted_ha,harvested_ha,production,production_unit,yield_kg_ha`. `level ∈ {region, state, municipality}`. Valores SIDRA `-`, `..`, `...`, `X` → vazio.
- `data/rasters/<layer>.nc`: Dataset xarray com uma variável `value`, dims `(time, lat, lon)`, graus WGS84, attrs `units`, `source`, `product`, `resolution`. Camadas: `ndvi` (adimensional, −1..1), `soil_moisture` (m³/m³), `precipitation` (mm/dia).
- `data/maps/<layer>/index.json`: `{"layer", "unit", "legend": [{"color", "label"}], "periods": [{"period": "YYYY-MM", "file": "YYYY-MM.png", "bounds": [[south, west], [north, east]]}]}`
- `data/cache/power/{kind}_{lat:.2f}_{lon:.2f}.json` com `kind ∈ {history, recent}`: resposta bruta do POWER.

## Rotas (contrato com o frontend)

| Método | Caminho | Resposta | Task real |
|---|---|---|---|
| GET | `/health` | `{"status": "ok"}` | 1 |
| POST/GET | `/farms`, GET `/farms/{farm_id}` | `Farm` / `list[Farm]` | 3 |
| POST/GET | `/farms/{farm_id}/plots`, GET `/plots/{plot_id}` | `Plot` / `list[Plot]` | 3 |
| GET | `/plots/{plot_id}/climate?start=&end=` | `ClimateResponse` | 4 |
| GET | `/plots/{plot_id}/signals?reference_date=` | `SignalsResponse` | 5, 7 |
| GET | `/plots/{plot_id}/satellite/{layer}?start=&end=` | `SatelliteSeries` | 7 |
| GET | `/crops` | `list[Crop]` | 2 |
| POST | `/plots/{plot_id}/rotation/compare` | `RotationResponse` | 9 |
| GET | `/regional/losses?level=&code=` | `LossRanking` | 8 |
| GET | `/regional/causes?crop=` | `CausesResponse` | 10 |
| GET | `/maps/{layer}` | `MapLayerIndex` | 11 |
| POST | `/plots/{plot_id}/reports/analysis` | `Report` | 12 |
| GET | `/reports`, `/reports/{report_id}` | `list[ReportSummary]` / `Report` | 12 |
| GET | `/quiz` | `list[Question]` | 13 |
| POST | `/plots/{plot_id}/quiz` | `Report` | 13 |
| GET | `/reports/{report_id}/pdf` | `application/pdf` | 14 |

Prioridade (spec §7): **P0** = Tasks 1–6, 8, 9, 15 · **P1** = 7, 10, 11, 12 · **P2** = 13, 14. Ordem de execução = numeração.

---

### Task 1: Esqueleto do projeto

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `app/__init__.py`, `app/main.py`, `app/settings.py`, `README.md` (esqueleto), `tests/conftest.py`, `tests/test_health.py`

**Interfaces:**
- Produces: `app.main.create_app(settings: Settings | None = None) -> FastAPI`; `app.main.app`; `app.settings.Settings` (dataclass com `data_dir: Path = Path("data")`, `var_dir: Path = Path("var")`, `power_live: bool = True`, lidos de env `DATA_DIR`, `VAR_DIR`, `POWER_LIVE`); fixture pytest `client` (TestClient com `Settings` apontando `var_dir` para `tmp_path` e `data_dir` para `tests/fixtures/data`).

- [ ] **Step 1:** `pyproject.toml` com dependências do Tech Stack (`[project.optional-dependencies] dev = [pytest, respx, ruff]`, `pipeline = [requests, harmony-py, earthaccess, matplotlib]`), `requires-python = ">=3.10"`, ruff `line-length = 100`. `.gitignore`: `.venv/ var/ data/raw/ __pycache__/ .pytest_cache/ *.egg-info/`.
- [ ] **Step 2: Teste que falha** — `tests/test_health.py::test_health`: `client.get("/health")` → 200, `{"status": "ok"}`.
- [ ] **Step 3:** Rodar `.venv/bin/pytest tests/test_health.py -v` → FAIL (import).
- [ ] **Step 4:** Implementar `create_app` (CORS `*`, rota `/health`, `title="Field Shift API"`).
- [ ] **Step 5:** `.venv/bin/pytest -v` → PASS; `.venv/bin/ruff check .` → sem erros; `.venv/bin/uvicorn app.main:app` sobe e `/docs` abre.
- [ ] **Step 6:** Commit `chore: project skeleton with health endpoint`.

### Task 2: Contrato da API com respostas de exemplo + configuração

Entrega o contrato inteiro para o frontend trabalhar em paralelo (decisão do spec). Cada rota da tabela existe e devolve exemplo realista no formato final; as tasks seguintes trocam o exemplo pela implementação real.

**Files:**
- Create: `app/models/{farms,climate,signals,satellite,crops,rotation,regional,maps,reports,quiz}.py`, `app/api/*.py` (um router por linha da tabela), `app/api/examples.py`, `app/config_loader.py`, `app/config/{crops,signals,rotation,quiz,phrases}.yaml`, `app/services/texts.py`
- Test: `tests/test_contract.py`, `tests/test_config.py`, `tests/test_texts.py`

**Interfaces (Produces — todos Pydantic v2):**
- farms: `GeoJSONPolygon(type: Literal["Polygon"], coordinates: list[list[tuple[float, float]]])`; `FarmCreate(name: str, municipality: str, state: str, ibge_code: str | None = None, owner: str | None = None)`; `Farm(FarmCreate, id: int)`; `PlotCreate(name: str, current_crop: str | None = None, geometry: GeoJSONPolygon)`; `Plot(PlotCreate, id: int, farm_id: int, centroid: tuple[float, float]  # (lon, lat)`, `area_ha: float, in_demo_region: bool)`
- climate: `DailyValue(date: date, value: float | None)`; `ClimateSeries(variable: str, unit: str, source: str, values: list[DailyValue])`; `ClimateResponse(plot_id: int, start: date, end: date, series: list[ClimateSeries])`
- signals: `Signal(kind: Literal["rain", "soil_moisture"], color: Literal["green", "yellow", "red"], value: float, normal: float, deviation_pct: float | None, unit: str, window_days: int, source: str, message: str)`; `SignalsResponse(plot_id: int, reference_date: date, reference_date_adjusted: bool, signals: list[Signal])`
- satellite: `SatelliteSeries(plot_id: int, layer: Literal["ndvi", "soil_moisture", "precipitation"], unit: str, source: str, values: list[DailyValue])`
- crops: `Crop(id: str, name: str, ibge_name: str | None, soil_restoring: bool, planting_month: int, kc: list[float], price_brl_per_kg: float | None)`
- rotation: `RotationRequest(options: list[list[str]])` (2–4 opções, cada uma com 1–3 ids); `CriterionScore(name: Literal["water", "soil", "regional_loss"], score: float | None, source: str, detail: str)`; `RotationOptionResult(crops: list[str], scores: list[CriterionScore], total: float, rank: int)`; `RotationResponse(plot_id: int, options: list[RotationOptionResult], verdict: str)`
- regional: `LossRankingItem(crop: str, mean_loss_pct: float, worst_year: int, worst_loss_pct: float, years: int)`; `LossRanking(level: Literal["region", "state", "municipality"], territory_code: str, territory_name: str, period: tuple[int, int], source: str, items: list[LossRankingItem])`; `CauseYear(year: int, loss_pct: float, rain_anomaly_pct: float | None)`; `CausesResponse(territory_name: str, crop: str, years: list[CauseYear], message: str)`
- maps: `LegendItem(color: str, label: str)`; `MapPeriod(period: str, url: str, bounds: list[list[float]])`; `MapLayerIndex(layer: str, unit: str, legend: list[LegendItem], periods: list[MapPeriod])`
- reports: `ReportSection(title: str, text: str, data: dict)`; `Report(id: int, plot_id: int, kind: Literal["analysis", "quiz"], title: str, created_at: datetime, sections: list[ReportSection])`; `ReportSummary(id, plot_id, kind, title, created_at)`
- quiz: `QuizOption(id: str, label: str)`; `Question(id: str, text: str, options: list[QuizOption])`; `QuizAnswers(answers: dict[str, str])`
- `app.config_loader.load_config(config_dir: Path = Path("app/config")) -> AppConfig` (Pydantic: `crops: list[Crop]`, `signals: SignalsConfig`, `rotation: RotationConfig`, `quiz: QuizConfig`, `phrases: dict[str, str]`); `get_config()` com `lru_cache`. Falha na carga se um YAML for inválido.
- `app.services.texts.render(key: str, **values) -> str` — `phrases[key].format(**values)`; números formatados pelo chamador.

**Conteúdo de configuração (valores iniciais, editáveis pelo time):**
- `signals.yaml`: `rain: {window_days: 30, min_normal_mm: 20, pct: {yellow: -20, red: -50}, abs_deficit_mm: {yellow: 10, red: 15}}`, `soil_moisture: {window_days: 7, pct: {yellow: -10, red: -25}}`, `min_satellite_years: 5`. Regra: desvio ≤ `yellow` → amarelo, ≤ `red` → vermelho, senão verde.
- `rotation.yaml`: `weights: {water: 0.5, soil: 0.2, regional_loss: 0.3}`, `ndvi_range: [0.2, 0.7]`, `soil_restoring_bonus: 25`, `ndvi_years: 3`.
- `crops.yaml` (valores aproximados inspirados na FAO-56; preços ilustrativos — dizer isso num comentário no arquivo): `milho` ("Milho (em grão)", não recupera, plantio 4, kc `[0.4, 0.8, 1.15, 1.0, 0.6]`, 1.2), `feijao` ("Feijão (em grão)", recupera, 4, `[0.4, 1.05, 1.0]`, 6.0), `feijao_caupi` (ibge `null`, recupera, 4, `[0.4, 1.0, 0.9]`, 5.0), `sorgo` ("Sorgo (em grão)", não, 4, `[0.4, 0.75, 1.0, 0.6]`, 1.0), `mandioca` ("Mandioca", não, 4, `[0.3, 0.3, 0.5, 0.8, 0.8, 0.8, 0.8, 0.8, 0.7, 0.5, 0.4, 0.3]`, 0.8), `palma` (ibge `null`, não, 3, `[0.4]*12`, `null`).
- `quiz.yaml`: 4 perguntas de exemplo (irrigação, cobertura do solo, cultura principal, área afetada pela última seca); cada opção com `risk: 0..2` e `suggestion: str | null`; marcar no arquivo como **conteúdo de exemplo**.
- `phrases.yaml`: chaves `rain.green`, `rain.yellow`, `rain.red`, `rain.dry_season`, `soil_moisture.green`, `soil_moisture.yellow`, `soil_moisture.red`, `rotation.verdict`, `rotation.no_data`, `causes.year`, `causes.none`, `quiz.risk.low`, `quiz.risk.medium`, `quiz.risk.high`, `quiz.financial`, `quiz.no_financial`. Ex.: `rain.red: "Choveu {value} mm nos últimos {days} dias, {deviation} abaixo da média ({normal} mm). Risco alto para a lavoura."`

- [ ] **Step 1: Testes que falham**
  - `test_contract.py::test_all_routes_in_openapi`: o conjunto de `paths` de `/openapi.json` contém todos os caminhos da tabela de rotas.
  - `test_contract.py::test_example_responses_validate` (parametrizado por rota GET/POST da tabela, exceto PDF): status 200/201 e o JSON valida no modelo de resposta correspondente. **Regra para as tasks seguintes:** quem troca o exemplo de uma rota pela implementação real tira essa rota da parametrização (ela passa a ter testes próprios) e apaga o exemplo de `examples.py`.
  - `test_config.py::test_config_loads` (6 culturas, pesos somam 1.0); `test_config.py::test_every_crop_kc_nonempty`.
  - `test_texts.py::test_render_fills_values`: `render("rain.red", value="12", days=30, deviation="-60%", normal="30")` contém `"12 mm"`; `test_render_unknown_key_raises` → `KeyError`.
- [ ] **Step 2:** `pytest tests/test_contract.py tests/test_config.py tests/test_texts.py -v` → FAIL.
- [ ] **Step 3:** Implementar modelos, config, `render`, e routers devolvendo objetos de `app/api/examples.py` (exemplos coerentes com Aquidabã: centroide ~(-37.05, -10.27), fonte nomeada).
- [ ] **Step 4:** Mesmos testes → PASS.
- [ ] **Step 5:** Commit `feat: full API contract with example responses and config files`.

### Task 3: Propriedades e talhões (SQLite + geometria)

**Files:**
- Create: `app/db.py`, `app/repositories/{tables,farms,region}.py`, `app/services/geometry.py`, `tests/fixtures/data/region.json` (cópia do contrato)
- Modify: `app/api/farms.py`, `app/api/examples.py` (remover exemplos de farms/plots)
- Test: `tests/test_geometry.py`, `tests/test_farms_api.py`

**Interfaces:**
- Produces: `geometry.to_shape(geom: GeoJSONPolygon) -> shapely.Polygon` (levanta `ValueError` com mensagem em português se anel aberto, < 4 pontos ou `not is_valid`); `geometry.area_ha(poly) -> float` (área em graus² × `(111_320**2) × cos(lat_centroide)` / 10_000); `geometry.centroid(poly) -> tuple[float, float]`; `region.load_region(data_dir: Path) -> Region` (`name, ibge_code, state_code, bbox, rainy_season_months`); `Region.contains(poly) -> bool` (centroide dentro da bbox); `farms.FarmRepository(session)` com `create_farm`, `list_farms`, `get_farm`, `create_plot`, `list_plots`, `get_plot` → modelos da Task 2; dependência `app.api.deps.get_plot_or_404(plot_id) -> Plot`.
- Tabelas: `FarmRow`, `PlotRow` (geometria guardada como JSON texto). Banco em `{var_dir}/app.db`, criado em `create_app`.

- [ ] **Step 1: Testes que falham**
  - `test_area_of_known_square`: quadrado de 0.01° em lat −10.27 → `area_ha` ≈ 121.9 (±1%).
  - `test_open_ring_rejected`, `test_self_intersecting_rejected` (polígono em "gravata") → `ValueError`.
  - `test_create_plot_in_demo_region`: POST farm + POST plot com quadrado em torno de (−37.05, −10.27) → 201, `in_demo_region is True`, `area_ha > 0`; GET `/plots/{id}` devolve o mesmo.
  - `test_create_plot_outside_region`: quadrado em (−40.5, −9.4) → `in_demo_region is False`.
  - `test_invalid_polygon_422_and_not_saved` (**Review Focus 4**): gravata → 422 com `detail` em português; GET `/farms/{id}/plots` → lista vazia.
  - `test_unknown_plot_404`.
- [ ] **Step 2:** Rodar → FAIL.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** `pytest -v` → PASS (inclui contrato).
- [ ] **Step 5:** Commit `feat: farms and plots persisted in SQLite with geometry validation`.

### Task 4: Cliente NASA POWER com cache + rota de clima

**Files:**
- Create: `app/clients/power.py`, `tests/fixtures/power_history.json`, `tests/fixtures/power_recent.json` (capturar com curl para (−10.27, −37.05); o `recent` deve terminar com dias `-999`; reduzir o histórico a 2001–2020 para os testes)
- Modify: `app/api/climate.py`, `app/api/deps.py` (dependência `get_power_client`)
- Test: `tests/test_power_client.py`, `tests/test_climate_api.py`

**Interfaces:**
- Produces: `POWER_PARAMS: list[str]` (Global Constraints); `class PowerUnavailable(Exception)`; `class PowerClient(cache_dir: Path, live: bool = True, http: httpx.Client | None = None, today: Callable[[], date] = date.today)` com:
  - `history(lat: float, lon: float) -> pd.DataFrame` — 2001-01-01..2023-12-31; se o cache existe, **não** chama a rede.
  - `recent(lat: float, lon: float) -> pd.DataFrame` — últimos 400 dias até `today()`; tenta ao vivo (timeout 60 s) e sobrescreve o cache; em erro de rede/HTTP usa o cache; sem cache → `PowerUnavailable`.
  - DataFrame: índice `DatetimeIndex` diário, colunas = `POWER_PARAMS`, `-999` → `NaN`.
- `last_available_date(df: pd.DataFrame, column: str) -> date` — último dia com valor não-nulo.
- `PowerUnavailable` mapeado por exception handler para **503** `{"detail": "Não foi possível obter dados da NASA POWER agora e não há dados salvos para este local."}`.
- Rota `/plots/{id}/climate?start=&end=` (padrão: últimos 90 dias): usa `recent` (e `history` se `start` < janela recente), devolve uma `ClimateSeries` por parâmetro com `source="NASA POWER"`, unidade do header do POWER, `None` nos dias faltantes.

- [ ] **Step 1: Testes que falham** (rede simulada com `respx`)
  - `test_fill_value_becomes_nan`: fixture recent → últimas linhas `NaN`; `last_available_date` = último dia válido da fixture.
  - `test_history_uses_cache_without_network`: cache presente + respx sem rotas → retorna dados.
  - `test_recent_falls_back_to_cache_on_error`: respx devolve 500 → retorna o cache.
  - `test_recent_without_cache_raises`: erro + sem cache → `PowerUnavailable`.
  - `test_climate_api_503_when_unavailable` (**Review Focus 2**): GET `/plots/{id}/climate` → 503 e `detail` contém "NASA POWER".
  - `test_climate_api_no_fill_values`: nenhum valor `-999` na resposta.
- [ ] **Step 2:** Rodar → FAIL.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Rodar → PASS.
- [ ] **Step 5:** Commit `feat: NASA POWER client with offline cache and climate endpoint`.

### Task 5: Climatologia + semáforos (via POWER)

**Files:**
- Create: `app/services/climatology.py`, `app/services/signals.py`
- Modify: `app/api/signals.py`
- Test: `tests/test_climatology.py`, `tests/test_signals.py`

**Interfaces:**
- Consumes: `PowerClient`, `last_available_date` (Task 4); `render` e `SignalsConfig` (Task 2).
- Produces:
  - `climatology.window(series: pd.Series, end: date, days: int, agg: Literal["sum", "mean"]) -> float | None` — janela `(end - days + 1)..end`; `None` se > 20% `NaN`.
  - `climatology.normal(series: pd.Series, end: date, days: int, years: Iterable[int], agg) -> float | None` — média de `window` terminando em `end` trocado para cada ano (29/02 → 28/02); janelas que cruzam a virada de ano usam o ano anterior no começo.
  - `signals.classify(deviation_pct: float, thresholds: dict) -> Literal["green", "yellow", "red"]`.
  - `signals.rain_signal(series: pd.Series, normal_series: pd.Series, normal_years: Iterable[int], reference: date, cfg, source: str) -> Signal`; `signals.soil_signal(...)` idem.
  - `signals.build_signals(plot: Plot, reference_date: date | None, power: PowerClient, rasters: "RasterStore | None" = None) -> SignalsResponse` (`RasterStore` nasce na Task 7; aqui o parâmetro é sempre `None` e não é usado).
- Regras: chuva = `PRECTOTCORR`, soma; umidade = `GWETROOT`, média. Normal com anos 2001–2020 vindos de `history`. Chuva com `normal < min_normal_mm` → modo absoluto: `deficit = normal - value`, cor por `abs_deficit_mm`, `deviation_pct = None`, frase `rain.dry_season`. `reference_date` ausente → `last_available_date`; posterior a ele → ajusta e `reference_date_adjusted = True`. Valores arredondados a 1 casa.

- [ ] **Step 1: Testes que falham**
  - `test_window_sum_simple`, `test_window_none_when_mostly_nan`.
  - `test_normal_cross_year_window`: série sintética com 1 mm/dia, janela de 30 dias terminando em 10/01 → normal 30.0.
  - `test_classify_thresholds`: −10 → green, −20 → yellow, −50 → red (limiares do `signals.yaml`).
  - `test_rain_red_when_well_below_normal`: série sintética com normal 100 mm e recente 30 mm → `color == "red"`, `deviation_pct == -70.0`, `message` contém "30".
  - `test_dry_season_uses_absolute_mode` (**Review Focus 5**): normal 5 mm, recente 0 mm → `deviation_pct is None`, cor `green`, `message` igual a `render("rain.dry_season", ...)`; nenhum `inf`/`nan` no JSON.
  - `test_reference_date_clamped` (**Review Focus 1**): GET `/plots/{id}/signals?reference_date=2099-01-01` (fixtures da Task 4) → 200, `reference_date` = último dia válido, `reference_date_adjusted is True`.
  - `test_signals_sources_power`: as duas fontes são `"NASA POWER"`.
- [ ] **Step 2:** Rodar → FAIL.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Rodar → PASS.
- [ ] **Step 5:** Commit `feat: rain and soil moisture traffic lights from NASA POWER`.

### Task 6: Seed da demo + README (fecha o mínimo apresentável)

**Files:**
- Create: `data/region.json` (contrato), `pipeline/seed_demo.py`, `data/cache/power/history_*.json` e `recent_*.json` (gerados), `docs/architecture.md`
- Modify: `README.md`
- Test: `tests/test_seed_demo.py`

**Interfaces:**
- Produces: `seed_demo.main(api_base: str = "http://localhost:8000", client: httpx.Client | None = None) -> list[int]` (o teste passa um `client` ligado à app) — cria via API a propriedade "Sítio Demonstração" (Aquidabã/SE, `ibge_code="2800209"`) com 2 talhões (~5 ha cada, dentro do município, perto de (−37.05, −10.27)), chama `/signals` de cada um para encher o cache do POWER, devolve os ids dos talhões. Idempotente: se já existe uma propriedade com esse nome, reaproveita.

- [ ] **Step 1: Teste que falha** — `test_seed_is_idempotent`: rodar `main` duas vezes contra o `TestClient` (via `httpx` transport) → 1 propriedade, 2 talhões.
- [ ] **Step 2:** Rodar → FAIL. **Step 3:** Implementar. **Step 4:** Rodar → PASS.
- [ ] **Step 5:** Rodar de verdade: `uvicorn app.main:app` + `python -m pipeline.seed_demo` → arquivos em `data/cache/power/` criados; repetir com `POWER_LIVE=0` e o Wi-Fi desligado → `/signals` responde 200.
- [ ] **Step 6:** README em português: o problema, o público, as fontes NASA (tabela fonte → produto → para que serve → resolução), **o caminho de um dado até o semáforo** (POWER → janela de 30 dias → normal 2001–2020 → desvio % → cor → frase), como rodar (venv, uvicorn, seed, testes), link para `/docs`. `docs/architecture.md` com o diagrama do spec §5 e os contratos de dados deste plano.
- [ ] **Step 7:** Commit `feat: demo seed with cached NASA POWER data and README`.

### Task 7: Rasters de satélite na API (SMAP, GPM, MODIS)

**Files:**
- Create: `app/repositories/rasters.py`, `pipeline/layers.py`, `tests/fixtures/data/rasters/` (gerados no teste com `write_layer`)
- Modify: `app/api/satellite.py`, `app/services/signals.py`, `app/api/deps.py`
- Test: `tests/test_layers.py`, `tests/test_rasters.py`, `tests/test_signals.py` (casos novos)

**Interfaces:**
- Produces:
  - `pipeline.layers.write_layer(da: xr.DataArray, layer: str, source: str, product: str, units: str, resolution: str, out_dir: Path) -> Path` — valida dims `(time, lat, lon)`, grava `out_dir/<layer>.nc` no contrato (variável `value`, attrs).
  - `RasterStore(data_dir: Path)`: `has(layer) -> bool`; `meta(layer) -> dict` (`units`, `source`); `plot_series(layer: str, polygon: shapely.Polygon) -> pd.Series | None` — média dos pixels com centro dentro do polígono (`shapely.contains_xy`); sem nenhum, pixel mais próximo do centroide; `None` se o arquivo não existe ou o centroide está fora da extensão do raster; `coverage(layer) -> tuple[date, date] | None`.
- `build_signals` passa a preferir satélite: chuva ← `precipitation`, umidade ← `soil_moisture`, quando o raster cobre a janela de referência **e** tem ≥ `min_satellite_years` anos completos fora do ano de referência; a normal usa esses anos; `source` = attr do raster. Caso contrário, mantém POWER.
- Rota `/plots/{id}/satellite/{layer}`: 404 `{"detail": "Dados de satélite disponíveis apenas para a região de demonstração (Aquidabã/SE)."}` quando `plot_series` devolve `None` ou o layer não existe.

- [ ] **Step 1: Testes que falham**
  - `test_write_layer_contract`: DataArray sintético → arquivo reabre com `value`, attrs `units`/`source`.
  - `test_plot_series_mean_of_inside_pixels`: grade 4×4 com valores conhecidos, polígono cobrindo 4 pixels → média exata.
  - `test_plot_series_small_plot_uses_nearest_pixel`.
  - `test_satellite_outside_region_404` (**Review Focus 3**): talhão fora da bbox → 404 com o `detail` acima.
  - `test_signals_prefer_satellite_when_covered`: raster sintético de `precipitation` 2015–2025 → `source` do sinal de chuva = attr do raster.
  - `test_signals_fallback_when_raster_short`: raster com 2 anos → `source == "NASA POWER"`.
- [ ] **Step 2:** Rodar → FAIL. **Step 3:** Implementar. **Step 4:** Rodar → PASS.
- [ ] **Step 5:** Commit `feat: satellite raster store and satellite-first traffic lights`.

### Task 8: IBGE PAM — pipeline + ranking de perdas

**Files:**
- Create: `pipeline/ibge_pam.py`, `app/repositories/ibge.py`, `app/services/losses.py`, `data/ibge/pam.csv` (gerado), `tests/fixtures/sidra_sample.json`, `tests/fixtures/data/ibge/pam.csv`
- Modify: `app/api/regional.py`
- Test: `tests/test_ibge_pipeline.py`, `tests/test_losses.py`

**Interfaces:**
- Produces:
  - `pipeline.ibge_pam.parse_sidra(rows: list[dict], level: str) -> list[dict]` (linhas no formato do CSV; ignora a 1ª linha de cabeçalho do SIDRA; pivota as variáveis por território/cultura/ano).
  - `pipeline.ibge_pam.main(start_year: int = 2010, end_year: int = 2023, out: Path = Path("data/ibge/pam.csv"))` — requisições `https://apisidra.ibge.gov.br/values/t/5457/{nível}/v/8331,216,214,112/p/{ano}/c782/all`, **uma por nível por ano**: `n2/2` (Nordeste), `n3/21,22,23,24,25,26,27,28,29` (UFs), `n6/in n3 28` (municípios de SE; ranking municipal só para Sergipe — limite de 100 mil valores do SIDRA).
  - `IbgeRepository(data_dir)`: `rows(level: str, code: str) -> pd.DataFrame`; `territory_name(level, code) -> str`.
  - `losses.yearly_loss(df: pd.DataFrame) -> pd.DataFrame` — por (cultura, ano): `loss = clip(1 − production_kg / (planted_ha × median_yield_kg_ha), 0, 1)`, `production_kg = production × 1000`, só `production_unit == "Toneladas"` e `planted_ha > 0`; mediana do rendimento por cultura no território.
  - `losses.ranking(df, min_years: int = 5, min_mean_planted_ha: float) -> list[LossRankingItem]` — ordenado por `mean_loss_pct` desc; `min_mean_planted_ha` padrão por nível: region 10000, state 1000, municipality 10.
  - `losses.crop_loss_pct(repo, ibge_name: str, municipality_code: str | None, state_code: str) -> tuple[float, str] | None` — média do município; se faltar, do estado; devolve `(pct, nível usado)`.
- Rota `/regional/losses?level=region|state|municipality&code=` (padrão `region`, `2`); `source="IBGE PAM"`; 404 se o território não existe no CSV.

- [ ] **Step 1: Testes que falham**
  - `test_parse_sidra_pivots_variables`: fixture com Milho/Feijão de 1 município → 2 linhas com `planted_ha`, `harvested_ha`, `production`, `yield_kg_ha`; `"-"` → vazio.
  - `test_yearly_loss_drought_year`: rendimento mediano 2000 kg/ha; ano com 100 ha e 50 t → `loss == 0.75`.
  - `test_ranking_order_and_filters`: cultura com 3 anos fica de fora; ordem decrescente.
  - `test_losses_api_region`: GET `/regional/losses` → `level == "region"`, itens ordenados, `source == "IBGE PAM"`.
- [ ] **Step 2:** Rodar → FAIL. **Step 3:** Implementar. **Step 4:** Rodar → PASS.
- [ ] **Step 5:** Rodar `python -m pipeline.ibge_pam` → `data/ibge/pam.csv` com linhas `region`, `state` e `municipality` (2800209 presente); tamanho < 20 MB.
- [ ] **Step 6:** Commit `feat: IBGE PAM pipeline and crop loss ranking for the Northeast`.

### Task 9: Comparador de rotação de culturas

**Files:**
- Create: `app/services/water.py`, `app/services/rotation.py`
- Modify: `app/api/rotation.py`
- Test: `tests/test_water.py`, `tests/test_rotation.py`

**Interfaces:**
- Consumes: `PowerClient.history` (Task 4); `RasterStore.plot_series("ndvi", ...)` (Task 7; se a Task 7 não estiver pronta, passar `None`); `losses.crop_loss_pct` (Task 8); `RotationConfig`, `Crop` (Task 2).
- Produces:
  - `water.et0_hargreaves(tmax: float, tmin: float, tmean: float, ra_mj: float) -> float` = `0.0023 × 0.408 × ra_mj × (tmean + 17.8) × sqrt(max(tmax − tmin, 0))` (mm/dia; `ra_mj` = `TOA_SW_DWN`).
  - `water.monthly_climatology(history: pd.DataFrame, years=range(2001, 2021)) -> pd.DataFrame` — índice mês 1..12, colunas `rain_mm`, `et0_mm` (totais mensais, média entre anos).
  - `water.sequence_months(crops: list[Crop]) -> list[tuple[Crop, int, float]]` — (cultura, mês 1..12, kc): a 1ª cultura começa no seu `planting_month`; cada seguinte começa no mês após o fim da anterior; meses dão a volta em 12.
  - `water.water_score(seq_months, clim) -> float` = `100 × média(min(1, rain_mm / (kc × et0_mm)))`.
  - `rotation.compare(plot: Plot, request: RotationRequest, ...) -> RotationResponse` — critérios por opção: `water` (`source="NASA POWER"`), `soil` = `clip((ndvi_médio_últimos_ndvi_years − 0.2) / 0.5, 0, 1) × 100`, mais `soil_restoring_bonus` (máx. 100) se alguma cultura `soil_restoring` e score < 50, `None` sem NDVI (`source="NASA MODIS"`); `regional_loss` = `100 − média(perda % das culturas com dado)`, `None` se nenhuma tem dado (`source="IBGE PAM"`). `total` = média ponderada pelos `weights` só com critérios não-`None` (pesos renormalizados). `rank` 1 = maior total. `verdict` = `render("rotation.verdict", best=..., total=...)`. Código IBGE do município: `farm.ibge_code`, senão o da região quando `in_demo_region`.
- Erros: id de cultura desconhecido → 422 com a lista de ids válidos; menos de 2 opções → 422.

- [ ] **Step 1: Testes que falham**
  - `test_et0_known_value`: `et0_hargreaves(32, 22, 27, 39.5)` ≈ 5.25 (±0.01).
  - `test_sequence_months_wraps`: mandioca (12 meses a partir de abril) seguida de feijão → feijão ocupa abril–junho do ano seguinte.
  - `test_water_score_full_coverage`: chuva ≥ demanda em todos os meses → 100.
  - `test_compare_ranks_and_renormalizes`: sem NDVI (`rasters=None`) → critério `soil` com `score is None` e `total` calculado só com `water` e `regional_loss` (**Review Focus 3**).
  - `test_soil_bonus_for_restoring_crop`: NDVI 0.3 → feijão recebe +25 no `soil`, milho não.
  - `test_unknown_crop_422`: `[["milho"], ["arroz"]]` → 422 e `detail` cita `"milho"` entre os ids válidos.
- [ ] **Step 2:** Rodar → FAIL. **Step 3:** Implementar. **Step 4:** Rodar → PASS.
- [ ] **Step 5:** Commit `feat: crop rotation comparator with water, soil and regional loss criteria`.

### Task 10: Causas ambientais (região de demo)

**Files:**
- Create: `app/services/causes.py`
- Modify: `app/api/regional.py`
- Test: `tests/test_causes.py`

**Interfaces:**
- Consumes: `losses.yearly_loss`, `IbgeRepository` (Task 8); `PowerClient.history` no centroide da bbox da região; `Region.rainy_season_months`.
- Produces: `causes.season_rain_anomaly(history: pd.DataFrame, months: list[int], normal_years=range(2001, 2021)) -> dict[int, float]` — por ano: `(chuva da estação − média 2001–2020) / média × 100`. `causes.explain(crop_id: str, ...) -> CausesResponse` — perdas do **município da região**, ou do estado se o município não tiver dado para a cultura; `message` monta `render("causes.year", ...)` para os 3 anos de maior perda com anomalia ≤ −20%, ou `causes.none`.
- Rota `/regional/causes?crop=milho` (padrão `milho`); 422 se a cultura não tem `ibge_name`.

- [ ] **Step 1: Testes que falham** — `test_season_anomaly_sign` (ano seco → negativo); `test_explain_mentions_worst_drought_year` (dados sintéticos: ano de maior perda com −50% de chuva aparece na `message`); `test_causes_crop_without_ibge_422` (`palma`).
- [ ] **Step 2:** Rodar → FAIL. **Step 3:** Implementar. **Step 4:** Rodar → PASS.
- [ ] **Step 5:** Commit `feat: environmental causes of crop losses for the demo region`.

### Task 11: Pipeline de satélite + camadas de mapa

O download depende de credenciais Earthdata e de serviços externos: só a conversão e a renderização têm teste automatizado; o download tem verificação manual.

**Files:**
- Create: `pipeline/region.py`, `pipeline/appeears.py`, `pipeline/gpm.py`, `pipeline/render_maps.py`, `pipeline/README.md`, `docs/data-sources.md`
- Modify: `app/api/maps.py`, `app/main.py` (montar `StaticFiles(directory=data_dir/"maps")` em `/static/maps`)
- Test: `tests/test_render_maps.py`, `tests/test_maps_api.py`

**Interfaces:**
- `pipeline.region.load_bbox() -> tuple[float, float, float, float]` (de `data/region.json`).
- `pipeline.appeears.main(start="2015-04-01", end=<hoje>)`: login no AppEEARS (`https://appeears.earthdatacloud.nasa.gov/api/`) com `EARTHDATA_USERNAME`/`EARTHDATA_PASSWORD`; 1 tarefa de área (polígono da bbox, saída netCDF4) com `MOD13Q1.061` camada `_250m_16_days_NDVI` e `SPL3SMP_E` (versão e camada AM de umidade conferidas em `GET /product/SPL3SMP_E.<versão>`); espera, baixa em `data/raw/appeears/`, converte com `write_layer` → `ndvi.nc` (escala para −1..1 se vier inteiro), `soil_moisture.nc`.
- `pipeline.gpm.main(start="2015-01-01", end=<último disponível>)`: `GPM_3IMERGDF` (v07) recortado na bbox via Harmony (`harmony-py`), variável `precipitation` → `precipitation.nc` (mm/dia). Se o Harmony não funcionar dentro do timebox, documentar no README do pipeline e seguir: a API cai para o POWER.
- `pipeline.render_maps.render_layer(nc_path: Path, out_dir: Path, cmap: str, vmin: float, vmax: float, months: int = 24) -> dict` — média mensal dos últimos `months` meses → `YYYY-MM.png` (RGBA, NaN transparente) + `index.json` no contrato; legenda com 5 cores. Mapas: `ndvi` (`RdYlGn`, 0–0.8), `soil_moisture` (`YlGnBu`, 0–0.5), `precipitation` (`Blues`, 0–300 mm/mês, soma mensal).
- Rota `/maps/{layer}` → `MapLayerIndex` com `url = "/static/maps/{layer}/{file}"`; 404 se não há `index.json`.

- [ ] **Step 1: Testes que falham** — `test_render_layer_writes_index_and_pngs` (raster sintético de 3 meses → 3 PNGs, `bounds == [[min_lat, min_lon], [max_lat, max_lon]]`); `test_maps_api_urls_resolve` (GET `/maps/ndvi` e depois GET na `url` do 1º período → 200 `image/png`); `test_maps_unknown_layer_404`.
- [ ] **Step 2:** Rodar → FAIL. **Step 3:** Implementar `render_maps`, rota e estáticos. **Step 4:** Rodar → PASS.
- [ ] **Step 5:** Implementar `appeears.py` e `gpm.py`; rodar com credenciais reais → `data/rasters/{ndvi,soil_moisture}.nc` (e `precipitation.nc` se possível), cada um abrindo com `value`/attrs; `du -sh data/` < 50 MB.
- [ ] **Step 6:** `python -m pipeline.render_maps` → `data/maps/*/index.json`; com a API rodando, `/plots/{id}/signals` de um talhão do seed mostra `source` de satélite onde houver cobertura.
- [ ] **Step 7:** `pipeline/README.md` (ordem de execução, credenciais, tempo esperado, o que fazer se uma fonte falhar) e `docs/data-sources.md` (produto, versão, resolução, período, link de cada fonte).
- [ ] **Step 8:** Commit `feat: satellite pipeline (SMAP, MODIS, GPM) and map layers`.

### Task 12: Relatórios de análise

**Files:**
- Create: `app/repositories/reports.py`, `app/services/reports.py`
- Modify: `app/repositories/tables.py` (`ReportRow`: id, plot_id, kind, title, sections_json, created_at), `app/api/reports.py`
- Test: `tests/test_reports.py`

**Interfaces:**
- Produces: `ReportRepository(session)`: `save(plot_id, kind, title, sections) -> Report`, `list(plot_id: int | None = None) -> list[ReportSummary]` (mais recentes primeiro), `get(report_id) -> Report | None`. `reports.build_analysis(plot, reference_date: date | None, rotation: RotationRequest | None, ...) -> list[ReportSection]` — seções: "Condição atual" (sinais, `data` = `SignalsResponse`), "Comparação de rotação" (se pedida), "Perdas na região" (top 5 do ranking do estado), "Causas ambientais" (se `in_demo_region`). Uma seção cuja fonte falhou vira texto "Dado indisponível no momento." em vez de derrubar o relatório.
- Rota `POST /plots/{id}/reports/analysis` (body opcional `{reference_date, rotation}`) → 201 `Report`; `GET /reports?plot_id=`; `GET /reports/{id}` (404 se não existe).

- [ ] **Step 1: Testes que falham** — `test_analysis_report_saved_and_listed`; `test_report_survives_power_outage` (POWER sem cache → 201 e a seção "Condição atual" com o texto de indisponível); `test_report_404`.
- [ ] **Step 2:** Rodar → FAIL. **Step 3:** Implementar. **Step 4:** Rodar → PASS.
- [ ] **Step 5:** Commit `feat: saved analysis reports`.

### Task 13: Partida rápida / trilha de perguntas

**Files:**
- Create: `app/services/quiz.py`
- Modify: `app/api/quiz.py`
- Test: `tests/test_quiz.py`

**Interfaces:**
- Consumes: `QuizConfig` (Task 2), `build_signals` (Task 5), `losses.crop_loss_pct` (Task 8), `ReportRepository` (Task 12).
- Produces: `quiz.evaluate(plot: Plot, answers: QuizAnswers, ...) -> list[ReportSection]` — risco = `100 × soma(risk) / soma(risk máximo)`; nível baixo < 34 ≤ médio < 67 ≤ alto → `quiz.risk.*`; impacto financeiro estimado = `area_ha × rendimento mediano (kg/ha) × perda % × price_brl_per_kg` da cultura respondida (pergunta `cultura`), senão `quiz.no_financial`; impacto ambiental = semáforos atuais; sugestões = `suggestion` das opções escolhidas (sem `null`).
- Rotas: `GET /quiz` → perguntas (sem `risk`/`suggestion`); `POST /plots/{id}/quiz` → salva e devolve `Report(kind="quiz")`. Pergunta sem resposta ou opção inexistente → 422 citando o id da pergunta.

- [ ] **Step 1: Testes que falham** — `test_quiz_questions_hide_internal_fields`; `test_quiz_high_risk_report` (todas as opções de risco 2 → texto de `quiz.risk.high` e seção de sugestões não vazia); `test_quiz_missing_answer_422`.
- [ ] **Step 2:** Rodar → FAIL. **Step 3:** Implementar. **Step 4:** Rodar → PASS.
- [ ] **Step 5:** Commit `feat: quick-start question trail producing a report`.

### Task 14: Exportação em PDF

**Files:**
- Create: `app/services/pdf.py`
- Modify: `app/api/reports.py`
- Test: `tests/test_pdf.py`

**Interfaces:**
- Produces: `pdf.render_report(report: Report, plot: Plot) -> bytes` (reportlab, A4): título, data, talhão (nome, área, município), cada seção com título e texto, e uma tabela chave/valor para os campos escalares de `data`; rodapé "Fontes: NASA POWER, SMAP, GPM, MODIS; IBGE PAM".
- Rota `GET /reports/{id}/pdf` → `application/pdf`, `Content-Disposition: attachment; filename="relatorio-{id}.pdf"`.

- [ ] **Step 1: Testes que falham** — `test_pdf_bytes`: começa com `b"%PDF"`, tamanho > 1 KB; `test_pdf_handles_accents`: relatório com "Aquidabã" e "Feijão" gera sem erro.
- [ ] **Step 2:** Rodar → FAIL. **Step 3:** Implementar. **Step 4:** Rodar → PASS.
- [ ] **Step 5:** Commit `feat: PDF export for reports`.

### Task 15: Ensaio da demo e acabamento

**Files:**
- Modify: `README.md`, `app/api/examples.py` (remover; nenhuma rota pode depender dele), `tests/test_contract.py` (remover `test_example_responses_validate`; manter `test_all_routes_in_openapi`)

- [ ] **Step 1:** `grep -r "examples" app/` → sem ocorrências; `pytest -v` → tudo PASS; `ruff check .` → limpo.
- [ ] **Step 2:** Ensaio offline: apagar `var/`, subir a API com `POWER_LIVE=0`, rodar o seed, depois percorrer o fluxo do wireframe só pelo `/docs` — cadastro → semáforos → comparar `[["milho","feijao"],["sorgo","feijao_caupi"]]` → ranking → causas → mapa → relatório → PDF. Cada passo responde 200/201 e nenhuma resposta contém `-999`, `NaN` ou `Infinity`.
- [ ] **Step 3:** README final: seção "Limitações conhecidas" (resolução do POWER ~50 km; satélite só na região de demo; valores de Kc/preço aproximados; sem previsão; Banco do Nordeste e Sebrae como evolução) e "Próximos passos".
- [ ] **Step 4:** Commit `docs: demo rehearsal and known limitations`.
