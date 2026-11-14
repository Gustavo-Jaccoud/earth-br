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

> **Estado atual:** os semáforos, o comparador e os relatórios usam **NASA POWER** e **IBGE**.
> SMAP, GPM e MODIS têm o código de download pronto (`pipeline/`), mas **os arquivos ainda não
> foram baixados**: não há `data/rasters` nem `data/maps` nesta versão, e as rotas de satélite e de
> mapa respondem 404 até o pipeline rodar. O AppEEARS (SMAP e MODIS) exige usuário e senha do
> Earthdata e o GPM exige aceitar os termos do GES DISC — veja [`pipeline/README.md`](pipeline/README.md).

| Fonte | Produto | Para que serve | Resolução |
|---|---|---|---|
| NASA POWER | Clima diário (chuva, temperatura, umidade do solo na raiz, radiação) | Semáforos, comparador de rotação, normal climatológica 2001–2020 | ~50 km |
| NASA SMAP | Umidade do solo (SPL3SMP_E) | Semáforo de umidade e camada de mapa | ~9 km |
| NASA GPM | Precipitação (IMERG diário) | Semáforo de chuva e camada de mapa | ~10 km |
| NASA MODIS | Vigor vegetativo (NDVI, MOD13Q1) | Saúde do solo no comparador e camada de mapa | 250 m |
| IBGE | Produção Agrícola Municipal (SIDRA, tabela 5457) | Perda por cultura, ranking regional | município |

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
# dados do IBGE e de satélite: veja pipeline/README.md
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

## Estrutura

```
app/        API FastAPI (rotas, regras, clientes das fontes, configuração em YAML)
pipeline/   scripts offline que preparam os dados de satélite e do IBGE
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
  satélite não for executado, valem o POWER e o IBGE. O GPM *Final* tem atraso de meses.
- **Coeficientes de cultura e preços** (`app/config/crops.yaml`) são aproximados e ilustrativos.
- **Sem previsão do tempo:** as fontes são históricas; o "risco" compara o período recente com a média
  de 2001–2020.
- **Comparador de rotação:** uma cultura sem dado no IBGE (palma, feijão-caupi) fica sem o critério
  "perda regional" e o total é renormalizado, então opções com critérios diferentes não são
  estritamente comparáveis entre si.
- **Perda por cultura** é estimada contra o rendimento mediano do território (não é seguro agrícola
  nem dado oficial de sinistro); o IBGE municipal é grosseiro.
- **Talhões e relatórios não podem ser apagados ou editados** (só criados e consultados).
- **Sem login nem multiusuário**, e o banco é um SQLite local.
- Banco do Nordeste e Data Sebrae ficaram fora desta versão.

## Próximos passos

Executar o pipeline de satélite (SMAP, MODIS, GPM) e gerar os mapas; ampliar as causas ambientais
para outros municípios; trocar os modelos de frase por texto gerado por IA (opcional); integrar
Banco do Nordeste e Data Sebrae; autenticação e várias propriedades por usuário.

Detalhes em [`docs/architecture.md`](docs/architecture.md). Regras (limiares, culturas, frases,
perguntas da trilha) ficam em `app/config/*.yaml` e podem ser ajustadas sem mexer no código.
