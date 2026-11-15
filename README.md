# Field Shift — Backend

Backend (Python + FastAPI) do protótipo para o desafio **Field Shift: Adapting Farms with NASA Data**.

## O problema

Pequenos e médios produtores do Nordeste perdem safra com seca e chuva extrema. Os dados da NASA que
ajudariam a se antecipar existem, mas estão em formatos científicos brutos, inacessíveis no dia a dia
do campo. Este backend traduz esses dados em **semáforos**, **comparações de rotação de culturas** e
**relatórios em linguagem simples**.

**Público:** agricultores familiares e pequenas empresas rurais; cooperativas e agroindústrias locais
(rastreabilidade e sustentabilidade) — modelo B2B2C.

**Região da demonstração:** Aquidabã (SE), agricultura de sequeiro (sem irrigação).

## De onde vêm os dados

> **Estado atual:** os semáforos, o comparador e os relatórios usam **NASA POWER** e **FAO GAEZ**.
> A chuva por satélite (**GPM IMERG**, 2015 a set/2025) já está em `data/rasters/precipitation.nc`
> e aparece só como variável separada na análise: comparada ao POWER em Aquidabã, ela registra
> muito menos chuva de junho a setembro, então **não entra nos semáforos**
> (`satellite_rain_in_signals: false` em `app/config/signals.yaml`). SMAP e MODIS têm o código de
> download pronto, mas ainda não foram baixados (o AppEEARS exige usuário e senha do Earthdata)
> — veja [`pipeline/README.md`](pipeline/README.md).

| Fonte | Produto | Para que serve | Resolução |
|---|---|---|---|
| NASA POWER | Clima diário (chuva, temperatura, umidade do solo na raiz, radiação) | Semáforos, comparador de rotação, normal climatológica 2001–2020 | ~50 km |
| NASA SMAP | Umidade do solo (SPL3SMP_E) | Semáforo de umidade e camada de mapa | ~9 km |
| NASA GPM | Precipitação (IMERG diário) | Semáforo de chuva e camada de mapa | ~10 km |
| NASA MODIS | Vigor vegetativo (NDVI, MOD13Q1) | Saúde do solo no comparador e camada de mapa | 250 m |
| FAO GAEZ v4 | Zonas agroecológicas globais (clima 1981–2010, sequeiro, baixo insumo) | Aptidão e rendimento atingível de cada cultura no local | ~9 km |

O **POWER** é consultado ao vivo (com cache em disco, para a demo funcionar sem internet).
SMAP, GPM e MODIS são baixados **uma vez**, pelo `pipeline/`, para a região de demonstração.

## O caminho de um dado até o semáforo

```
NASA POWER (chuva diária no ponto do talhão)
   └─► soma dos últimos 30 dias até a data de referência
        └─► comparada com a média dos mesmos 30 dias em 2001–2020 (normal climatológica)
             └─► desvio em % (ex.: -64%)
                  └─► cor: verde / amarelo (≤ -20%) / vermelho (≤ -50%)   ← limiares em app/config/signals.yaml
                       └─► frase em português (modelo em app/config/phrases.yaml)
```

Em períodos normalmente secos (média < 20 mm), o percentual não faz sentido; a regra usa o déficit
em milímetros. Os dados da NASA têm ~2 dias de atraso: se a data pedida for mais recente, a API usa o
último dia disponível e avisa em `reference_date_adjusted`.

## Como rodar

Rode sempre a partir da raiz do repositório (os caminhos `data/` e `var/` são relativos).

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn app.main:app --reload          # API em http://localhost:8000
.venv/bin/python -m pipeline.seed_demo           # cria a propriedade de demonstração (API rodando)
# dados do GAEZ e de satélite: veja pipeline/README.md
.venv/bin/pytest                                 # testes
```

A documentação interativa de todas as rotas (Swagger, com **Try it out**) fica em
**http://localhost:8000/docs**; o ReDoc, em **/redoc**. A referência estática, com um exemplo de
fluxo em `curl`, está em [`docs/api.md`](docs/api.md) e o contrato completo em
[`docs/openapi.json`](docs/openapi.json) (para gerar clientes). Para regerar:
`python -m app.export_openapi`.

Sem internet (ex.: na apresentação): `POWER_LIVE=0 .venv/bin/uvicorn app.main:app` usa só os dados
já salvos em `data/cache/power/`.

Variáveis: `DATA_DIR` (padrão `data`), `VAR_DIR` (padrão `var`, onde fica o banco SQLite),
`POWER_LIVE` (`0` desliga as chamadas à NASA).

## Publicar (deploy)

**Back no Render** — o arquivo [`render.yaml`](render.yaml) já descreve o serviço:

1. Em <https://render.com>: *New* → *Blueprint* → escolha este repositório.
2. O Render instala (`pip install -e .`), sobe com `uvicorn` e confere `/health`.
3. Anote o endereço gerado (ex.: `https://earth-br-api.onrender.com`) — o front precisa dele.

O blueprint define `POWER_LIVE=0` (usa só os dados da NASA versionados em `data/cache/power`) e
`SEED_DEMO=1` (recria a propriedade de demonstração quando o banco está vazio). No plano gratuito
o disco é apagado a cada reinício — propriedades e relatórios cadastrados se perdem — e o servidor
"dorme" sem uso: abra o endereço alguns minutos antes de apresentar.

Com `POWER_LIVE=0` os dados "recentes" param na data em que o cache foi gerado. Para atualizar,
rode `python -m pipeline.seed_demo` localmente (com a API no ar e internet) e faça commit de
`data/cache/power/`. Em hospedagem com disco gravável e acesso à internet, use `POWER_LIVE=1`.

**Front no Vercel** — veja o README do repositório do front; ele precisa da variável
`VITE_API_URL` apontando para o endereço do back.

## Estrutura

```
app/        API FastAPI (rotas, regras, clientes das fontes, configuração em YAML)
pipeline/   scripts offline que preparam os dados de satélite e do GAEZ
data/       dados prontos para a API (versionados)
docs/       arquitetura e decisões
tests/      testes automatizados
```

## Limitações conhecidas

- **Resolução do NASA POWER (~50 km):** talhões vizinhos recebem os mesmos números; o mapa varia
  entre regiões, não dentro de uma fazenda.
- **Datas sem dado:** o NASA POWER fica indisponível entre 2024-01-01 e ~400 dias atrás (o
  histórico em cache vai até 2023-12-31 e o recente começa há ~400 dias). Nesse intervalo `/signals`
  responde 422 listando as datas com dado, e `/climate` devolve `null`. Também não há dados antes
  de 2001 no cache.
- **Satélite só na região de demonstração** (Aquidabã/SE). Fora dela, e enquanto o pipeline de
  satélite não for executado, valem o POWER e o GAEZ. O GPM *Final* tem atraso de meses.
- **Coeficientes de cultura e preços** (`app/config/crops.yaml`) são aproximados e ilustrativos.
- **Sem previsão do tempo:** as fontes são históricas; o "risco" compara o período recente com a média
  de 2001–2020.
- **Comparador de rotação:** uma cultura sem dado no GAEZ (palma forrageira) fica sem o critério
  "aptidão" e o total é renormalizado, então opções com critérios diferentes não são
  estritamente comparáveis entre si.
- **Aptidão (GAEZ) é um modelo de potencial**, não uma medição: não há perdas observadas por
  cultura nem estatística de produção. O rendimento é em matéria seca e a grade tem ~9 km.
- **Talhões e relatórios não podem ser apagados ou editados** (só criados e consultados).
- **Sem login nem multiusuário**, e o banco é um SQLite local.

## Próximos passos

Executar o pipeline de satélite (SMAP, MODIS, GPM) e gerar os mapas; usar o NDVI nos anos secos;
trocar os modelos de frase por texto gerado por IA (opcional);
autenticação e várias propriedades por usuário.

Detalhes em [`docs/architecture.md`](docs/architecture.md). Regras (limiares, culturas, frases,
perguntas da trilha) ficam em `app/config/*.yaml` e podem ser ajustadas sem mexer no código.
