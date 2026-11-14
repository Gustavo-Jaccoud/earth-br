# Pipeline de dados

Scripts **offline**, rodados antes da demonstração. Eles preparam arquivos pequenos em `data/` que a
API lê. Instalação das dependências extras: `.venv/bin/pip install -e ".[pipeline]"`.

## Ordem de execução

| # | Comando | O que faz | Precisa de conta Earthdata? |
|---|---|---|---|
| 1 | `python -m pipeline.ibge_pam` | Baixa a Produção Agrícola Municipal do IBGE (2010–2023) → `data/ibge/pam.csv` | não |
| 2 | `python -m pipeline.seed_demo` (com a API rodando) | Cria a propriedade de demonstração e guarda em cache os dados do NASA POWER | não |
| 3 | `python -m pipeline.appeears` | NDVI (MODIS) e umidade do solo (SMAP) → `data/rasters/{ndvi,soil_moisture}.nc` | **sim** |
| 4 | `python -m pipeline.gpm` | Chuva diária (GPM IMERG) → `data/rasters/precipitation.nc` | **sim** |
| 5 | `python -m pipeline.render_maps` | Gera os PNGs mensais e `index.json` em `data/maps/<camada>/` | não |

Os passos 1 e 2 já foram executados e seus resultados estão versionados em `data/`.

## Credenciais (passos 3 e 4)

Crie uma conta gratuita em <https://urs.earthdata.nasa.gov> e aprove os aplicativos *NASA GESDISC DATA
ARCHIVE* (para o GPM). Depois:

```bash
export EARTHDATA_USERNAME=seu_usuario EARTHDATA_PASSWORD=sua_senha   # AppEEARS
export EDL_USERNAME=seu_usuario EDL_PASSWORD=sua_senha               # Harmony (GPM)
```

## O que foi testado e o que não foi

- **Testado automaticamente:** leitura do SIDRA e cálculo de perdas, contrato dos rasters
  (`layers.py`), geração dos mapas (`render_maps.py`), montagem do pedido ao AppEEARS, máscara de
  valores inválidos, divisão em blocos e conversão do GPM.
- **NÃO testado ao vivo** (exige conta Earthdata): o login, a tarefa e o download do AppEEARS
  (`appeears.py`) e o fluxo do Harmony (`gpm.py`). Foram escritos pela documentação das APIs. Se algo
  falhar, o erro aparece com a mensagem original; ajuste o trecho de rede e rode de novo.
- Os tempos de download não foram medidos. O AppEEARS processa a tarefa em fila (minutos a horas) e o
  GPM é baixado em blocos de 6 meses.

## Se uma fonte falhar

A API continua funcionando: sem raster de uma camada, os semáforos usam o NASA POWER e o
comparador marca o critério de solo como "sem dado" (`score: null`). O GPM *Final* tem atraso de
meses; para datas mais recentes que o último dado, a API usa o POWER automaticamente.

## Contrato dos arquivos

Veja `docs/architecture.md`. Todo raster segue o mesmo formato (`value`, dims `time, lat, lon`,
atributos `source`, `product`, `units`, `resolution`) e é gravado por `pipeline.layers.write_layer`.
