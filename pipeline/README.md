# Pipeline de dados

Scripts **offline**, rodados antes da demonstração. Eles preparam arquivos pequenos em `data/` que a
API lê. Instalação das dependências extras: `.venv/bin/pip install -e ".[pipeline]"`.

## Ordem de execução

| # | Comando | O que faz | Precisa de conta Earthdata? |
|---|---|---|---|
| 1 | `python -m pipeline.gaez` | Baixa aptidão e rendimento atingível por cultura do FAO GAEZ v4 e recorta o Nordeste → `data/gaez/gaez.nc` | não |
| 2 | `python -m pipeline.seed_demo` (com a API rodando) | Cria a propriedade de demonstração e guarda em cache os dados do NASA POWER | não |
| 3 | `python -m pipeline.appeears` | NDVI (MODIS) e umidade do solo (SMAP) → `data/rasters/{ndvi,soil_moisture}.nc` | **sim** |
| 4 | `python -m pipeline.gpm` | Chuva diária (GPM IMERG) → `data/rasters/precipitation.nc` | **sim** |
| 5 | `python -m pipeline.render_maps` | Gera os PNGs mensais e `index.json` em `data/maps/<camada>/` | não |

Os passos 1 e 2 já foram executados e seus resultados estão versionados em `data/`.

## Credenciais (passos 3 e 4)

Crie uma conta gratuita em <https://urs.earthdata.nasa.gov> e aprove os aplicativos *NASA GESDISC DATA
ARCHIVE* (para o GPM). Depois:

```bash
export EARTHDATA_USERNAME=seu_usuario EARTHDATA_PASSWORD=sua_senha   # AppEEARS (SMAP, MODIS)
export EDL_TOKEN=seu_token_do_earthdata                              # Harmony (GPM) — ou:
export EDL_USERNAME=seu_usuario EDL_PASSWORD=sua_senha               #   usuário e senha
```

- O **AppEEARS não aceita o token** do Earthdata Login (testado: 403); ele exige usuário e senha.
- O **Harmony aceita o token** (Earthdata Login → *Generate Token*).
- Para o GPM é preciso **aceitar os termos do arquivo GES DISC** em
  <https://urs.earthdata.nasa.gov/approve_app?client_id=e2WVk8Pw6weeLUKZYOxvTQ>. Sem isso o Harmony
  falha com `403` e o arquivo responde `EULA Acceptance Failure` (verificado em 2026-11-14).
- Nunca grave senha ou token em arquivos do repositório.

## O que foi testado e o que não foi

- **Testado automaticamente:** recorte e leitura do GAEZ, cálculo de anos secos, contrato dos rasters
  (`layers.py`), geração dos mapas (`render_maps.py`), montagem do pedido ao AppEEARS, máscara de
  valores inválidos, divisão em blocos e conversão do GPM.
- **Testado ao vivo, parcialmente:** o `gpm.py` consulta o catálogo (CMR), autentica no Harmony com o
  token e cria o job; o job falhou só por falta de aceite dos termos do GES DISC (veja acima). Falta
  ver o download e a conversão com dados reais.
- **NÃO testado ao vivo:** login, tarefa e download do AppEEARS (`appeears.py`), escritos pela
  documentação da API. Se algo falhar, o erro aparece com a mensagem original; ajuste e rode de novo.
- Os tempos de download não foram medidos. O AppEEARS processa a tarefa em fila (minutos a horas) e o
  GPM é baixado em blocos de 6 meses.

## Se uma fonte falhar

A API continua funcionando: sem raster de uma camada, os semáforos usam o NASA POWER e o
comparador marca o critério de solo como "sem dado" (`score: null`). O GPM *Final* tem atraso de
meses; para datas mais recentes que o último dado, a API usa o POWER automaticamente.

## Contrato dos arquivos

Veja `docs/architecture.md`. Todo raster segue o mesmo formato (`value`, dims `time, lat, lon`,
atributos `source`, `product`, `units`, `resolution`) e é gravado por `pipeline.layers.write_layer`.
