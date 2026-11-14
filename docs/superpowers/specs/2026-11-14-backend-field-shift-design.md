# Backend Field Shift — Design

Data: 2026-11-14 · Status: aguardando aprovação (revisado por builder check)

## 1. Intenção

Protótipo para o desafio **Field Shift: Adapting Farms with NASA Data** (hackathon, timebox de 48h).

**Problema:** pequenos e médios produtores do Nordeste perdem safra com eventos climáticos extremos porque os dados da NASA existem, mas estão em formatos científicos brutos, inacessíveis para o dia a dia no campo.

**Público:** agricultores familiares e empresas rurais de pequeno/médio porte que precisam de orientação simples; cooperativas e agroindústrias locais que buscam rastreabilidade e sustentabilidade (modelo B2B2C — a cooperativa adota, o produtor usa).

**Recorte:** região Nordeste, com foco em territórios de solo enfraquecido / revitalização. Pergunta de fundo: qual tipo de plantio tem mais desafios e maior perda no Nordeste, e por quais causas ambientais.

Este repositório é **todo o backend** (API + pipeline de dados). Só o frontend fica fora. O repositório **será publicado**, então a organização, o README e a documentação fazem parte da entrega — o júri vai ler.

## 2. Objetivos, não-objetivos, anti-objetivos

**Objetivos (o que a demo precisa mostrar):**
- Cadastrar propriedade e desenhar talhão (polígono) no mapa.
- Dashboard do talhão com **semáforos** (verde/amarelo/vermelho) de umidade do solo e chuva.
- **Comparador de rotação de culturas** baseado no histórico local.
- Texto simples que traduz o dado bruto ("Choveu 35% abaixo da média dos últimos 20 anos; risco alto para milho").
- Dados reais da NASA (POWER, SMAP, GPM, MODIS) cruzados com a geometria do talhão.

**Não-objetivos:**
- Produto completo: sem login/autenticação, sem multiusuário, sem escalabilidade.
- Previsão do tempo (as fontes são históricas / quase tempo real).
- Cobertura de dados de satélite fora da região de demonstração.
- Integração com Banco do Nordeste e Data Sebrae nesta versão (citados como fontes; ficam como evolução — ver §8).

**Anti-objetivos (falha mesmo se "funcionar"):**
- Demo que trava ou demora minutos esperando a NASA ao vivo.
- Dados simulados apresentados como se fossem da NASA.
- Repositório bagunçado / sem explicação de onde cada número vem.
- Regras do comparador e da trilha "chumbadas" no código — o frontend ainda vai redefini-las.

## 3. Restrições

- Python + FastAPI (decidido pelo time).
- 48h de desenvolvimento; papéis separados: Backend, Dados NASA (pipeline), Frontend, UI/UX, Produto/Pitch. Backend e pipeline vivem neste repo.
- **NASA POWER** (testado em 2026-11-14): endpoint `GET https://power.larc.nasa.gov/api/temporal/daily/point`, sem chave, JSON, 1 ponto por chamada, dados desde 1981, ~0,5 s por resposta. Atraso de ~2 dias: datas recentes vêm com `-999` (fill value) e precisam ser tratadas. Resolução ~0,5° (~50 km) — talhões vizinhos recebem os mesmos valores. Parâmetros úteis (`community=AG`): `T2M_MAX`, `T2M_MIN`, `PRECTOTCORR`, `RH2M`, `GWETROOT`, `ALLSKY_SFC_SW_DWN`.
- **SMAP, GPM, MODIS** exigem conta NASA Earthdata e processamento de arquivos grandes — inviável ao vivo numa demo. **Ação imediata do time: criar conta Earthdata.**

## 4. Abordagens consideradas

| | Abordagem | Trade-off |
|---|---|---|
| **A (escolhida)** | **Pré-processado + POWER ao vivo.** Pipeline baixa e recorta SMAP/GPM/MODIS para a região de demonstração uma vez; API serve esses arquivos e consulta o POWER na hora. | Demo rápida e confiável com dado real. Fora da região de demo, só há POWER. |
| B | Tudo ao vivo (AppEEARS/GPM sob demanda para qualquer talhão). | Funciona no Brasil todo, mas cada pedido leva minutos e pode falhar no palco. |
| C | Tudo simulado. | Mais rápido, mas contradiz o desafio: o júri quer dado real da NASA. |

Escolhida pelo time: **A**.

**Geração de texto:** escolhido **modelos de frase com regras** (determinístico, sem custo, sem chave). IA (Claude) fica como extra opcional se sobrar tempo — não faz parte deste design.

## 5. Arquitetura

```
pipeline/  (offline, roda antes da demo)          app/  (FastAPI, roda na demo)
  SMAP ─┐                                           clients/power.py ── NASA POWER (ao vivo, com cache)
  GPM  ─┼─► recorte pela região ─► data/ ◄───────── repositories/ (lê data/ + SQLite)
  MODIS─┤                                           services/ (semáforos, comparador, textos, relatórios)
  IBGE ─┘                                           api/ (rotas)  ──► Frontend
                                                    config/ (culturas, regras, trilha, frases — YAML/JSON)
```

### Estrutura do repositório (proposta)

```
app/
  main.py              criação da app, CORS, rotas
  api/                 rotas por recurso
  services/            regras de negócio (semáforos, comparador, textos, relatórios)
  clients/             NASA POWER, IBGE (SIDRA)
  repositories/        acesso a SQLite e aos arquivos de data/
  models/              esquemas Pydantic de entrada/saída
  config/              culturas.yaml, semaforos.yaml, trilha.yaml, frases.yaml
pipeline/              scripts por fonte + README de como rodar
data/                  saídas pequenas do pipeline, versionadas
docs/                  arquitetura, fontes de dados, decisões
tests/
README.md              o que é, fontes NASA, caminho do dado até o semáforo, como rodar
```

### Decisões do how (chamadas do assistente, corrigíveis)

- **SQLite** para propriedades, talhões e relatórios salvos.
- **Sem autenticação.**
- **Configuração em arquivos** (YAML) para culturas, limiares dos semáforos, perguntas da trilha e modelos de frase — o frontend vai redefinir regras e isso não pode exigir mudança de código.
- **Cache local** das respostas do POWER (por ponto + intervalo), para a demo não depender da rede a cada clique.
- **Região de demonstração (decisão do time):** **Aquidabã (SE)** e entorno. O pipeline recebe a área (bbox) como parâmetro. O modelo de risco hídrico assume **agricultura de sequeiro** (sem irrigação), coerente com o público de agricultura familiar.
- **Execução na demo (decisão do time):** backend roda **no notebook** do apresentador, num primeiro momento. SQLite e cache local em disco são suficientes. Para não depender da internet do local, as respostas do POWER dos talhões de demonstração ficam pré-baixadas e versionadas no cache do repositório; a chamada ao vivo é tentada e, se falhar, usa o cache.
- **Contrato com o frontend:** o backend publica primeiro. Nas primeiras horas sobem todas as rotas com respostas de exemplo no formato final (OpenAPI/Swagger gerado pelo FastAPI em `/docs`), para o front trabalhar em paralelo; depois as respostas de exemplo são trocadas por dados reais sem mudar o formato.
- **Regras "redefinidas pelo frontend"** = o time edita os arquivos de `config/` (carregados na inicialização). Não há edição de regras pela interface em tempo de execução. O comparador aceita, por requisição, quais culturas/sequências comparar, mas pesos e calendários vêm da config.
- **Data de referência:** semáforos e comparador recebem um parâmetro `data_referencia` (padrão: último dia com dado disponível). Isso permite à demo mostrar a estação chuvosa, já que em novembro o semiárido está na seca e percentuais sobre uma normal quase zero não significam nada. Quando a normal do período é muito baixa, o semáforo de chuva usa limiar absoluto (mm) em vez de percentual.
- **Camadas de mapa:** PNG pré-gerado pelo pipeline + bounds geográficos (funciona com Leaflet e MapLibre como image overlay), em composições mensais. Sem servidor de tiles.
- **Culturas fora do IBGE PAM** (ex.: palma forrageira, feijão-caupi): critério "perda regional" aparece como "sem dado" e não entra na pontuação.

## 6. Componentes

### 6.1 Propriedades e talhões
- Propriedade: nome, município/UF, responsável (texto livre).
- Talhão: nome, cultura atual (opcional), geometria GeoJSON `Polygon` (WGS84). O centroide é usado para consultar o POWER; o polígono é usado para recortar os rasters do pipeline.
- Indicar na resposta se o talhão está **dentro da região de demo** (tem dados de satélite) ou não (só POWER).

### 6.2 Clima (NASA POWER, ao vivo)
- Série diária para o centroide do talhão, em intervalo informado.
- **Normal climatológica**: média de um período histórico longo (ex.: 20 anos) para o mesmo ponto/janela, para comparação.
- Tratar `-999` como ausente; nunca exibir como valor.

### 6.3 Semáforos
- **Chuva:** acumulado recente (ex.: 30 dias) vs. normal histórica do mesmo período. Fonte: GPM (pipeline) quando disponível, senão POWER `PRECTOTCORR`.
- **Umidade do solo:** valor recente vs. histórico. Fonte: SMAP (pipeline) quando disponível, senão POWER `GWETROOT`.
- Cada semáforo retorna: cor, valor, referência histórica, desvio %, fonte do dado, e frase explicativa (via modelos de frase).
- Limiares em `config/semaforos.yaml`.

### 6.4 Comparador de rotação de culturas
Entrada: talhão + 2 ou mais sequências de culturas (ex.: `milho → feijão` vs `sorgo → feijão-caupi`). Para cada opção:
- **Risco hídrico:** chuva histórica mês a mês no local vs. necessidade de água da cultura no seu calendário (necessidade estimada por coeficiente de cultura × evapotranspiração; ET0 calculada a partir de dados do POWER).
- **Vigor do solo:** NDVI histórico do talhão (MODIS, pipeline).
- **Perda regional:** taxa de perda da cultura no município (IBGE PAM: área plantada vs. colhida, rendimento).
- **Veredito** em linguagem simples (modelos de frase) + pontuação por critério.
- Culturas, calendários, coeficientes e pesos em `config/culturas.yaml`. Conjunto inicial sugerido: milho, feijão, feijão-caupi, sorgo, mandioca, palma forrageira.

O time aceitou essa forma como ponto de partida; o frontend pode redefinir — por isso tudo parametrizado.

### 6.5 Panorama regional
- **Ranking de culturas com maior perda no Nordeste inteiro** (IBGE PAM), filtrável por estado e município. Decisão do time.
- **Causas ambientais** (cruzamento dos anos de maior perda com anomalias de chuva/umidade) **só para a região de demo** (Aquidabã / Sergipe) — fazer isso para o Nordeste inteiro exigiria clima de centenas de municípios. Responde a pergunta de fundo do pitch.

### 6.6 Mapa
- Camadas da região de demo (NDVI, umidade, chuva) para sobrepor ao mapa do frontend, em uma data/período escolhido.
- O mapa reage ao recorte selecionado (período, camada, talhão).

### 6.7 Partida rápida / trilha de perguntas
- Perguntas vêm de `config/trilha.yaml`; respostas + dados do talhão → regras → relatório final (impacto ambiental/financeiro estimado e sugestões de contenção).
- Conteúdo ainda **não definido** pelo time; o backend entrega o mecanismo genérico e um conteúdo de exemplo.

### 6.8 Relatórios
- Gerados pela trilha ou pela análise de dados; salvos e listáveis ("Relatórios prontos").
- Exportação em PDF.

### 6.9 Pipeline de dados
- Um script por fonte, parametrizado pela bbox da região: SMAP (umidade do solo), GPM IMERG (precipitação), MODIS (NDVI), IBGE PAM (produção/perdas).
- Saída em `data/` em formato pequeno, versionável e documentado (cada arquivo com fonte, produto, período, resolução).
- README do pipeline: como reproduzir, credenciais necessárias (Earthdata), tempo esperado.

## 7. Prioridade dentro das 48h

- **P0 (demo mínima):** talhões + POWER + semáforos (via POWER) + comparador (com POWER + IBGE) + README.
- **P1:** pipeline SMAP/GPM/MODIS enriquecendo semáforos/comparador/mapa; panorama regional; relatórios salvos.
- **P2:** trilha de perguntas; PDF.

Se o pipeline de satélite não ficar pronto, tudo P0 continua funcionando só com POWER (fallback explícito, marcado na resposta pela `fonte`).

## 8. Deixado para o builder / evolução

- Escolha de produtos exatos e forma de acesso (ex.: AppEEARS vs. download direto) para SMAP/GPM/MODIS.
- Formato dos arquivos em `data/`.
- Biblioteca de PDF.
- Fórmulas exatas de ET0 e pontuação, desde que documentadas.
- Banco do Nordeste e Data Sebrae: fora do MVP; documentar como evolução.
