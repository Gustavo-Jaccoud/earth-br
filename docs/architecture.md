# Arquitetura

```
pipeline/  (offline, roda antes da demo)          app/  (FastAPI, roda na demo)
  SMAP ─┐                                           clients/power.py ── NASA POWER (ao vivo, com cache)
  GPM  ─┼─► recorte pela região ─► data/ ◄───────── repositories/ (lê data/ + SQLite)
  MODIS─┤                                           services/ (semáforos, comparador, textos, relatórios)
  IBGE ─┘                                           api/ (rotas)  ──► Frontend
                                                    config/ (culturas, regras, trilha, frases — YAML)
```

**Decisão central:** os dados de satélite (SMAP, GPM, MODIS) são pesados e lentos para baixar, então o
pipeline os prepara **uma vez** para a região de demonstração. A API só lê arquivos pequenos. O
NASA POWER é rápido e fica ao vivo, com cache em disco para funcionar sem internet.
Fora da região de demonstração só há POWER.

## Contratos de dados (pipeline → API)

- `data/region.json`: `{"name", "ibge_code", "state_code", "bbox": [min_lon, min_lat, max_lon, max_lat], "rainy_season_months"}`
- `data/ibge/pam.csv` (formato longo): `level,territory_code,territory_name,crop,year,planted_ha,harvested_ha,production,production_unit,yield_kg_ha`; `level ∈ {region, state, municipality}`.
- `data/rasters/<layer>.nc`: xarray com variável `value`, dims `(time, lat, lon)`, attrs `units`, `source`, `product`, `resolution`. Camadas: `ndvi`, `soil_moisture`, `precipitation`.
- `data/maps/<layer>/index.json` + PNGs mensais para sobrepor ao mapa do frontend.
- `data/cache/power/{history|recent}_{lat}_{lon}.json`: resposta bruta do NASA POWER.

## Regras em arquivos de configuração (`app/config/`)

| Arquivo | O que controla |
|---|---|
| `signals.yaml` | janelas e limiares dos semáforos |
| `rotation.yaml` | pesos dos critérios do comparador |
| `crops.yaml` | culturas, calendário, coeficientes de água, preços ilustrativos |
| `quiz.yaml` | perguntas da trilha (conteúdo de exemplo) |
| `phrases.yaml` | modelos de frase em português |
