# Chat de perguntas (assistente de demonstração) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Popup de chat no app que responde perguntas livres com textos prontos, preenchidos com os dados reais do talhão, sem IA.

**Architecture:** O back ganha `POST /plots/{plot_id}/chat` e `GET /chat/suggestions`; assuntos, palavras-chave e respostas ficam em `app/config/chat.yaml`. O casamento é por palavras-chave (inglês e português); cada assunto tem um construtor de dados que reaproveita os serviços existentes; qualquer falha de dado cai no texto fixo. O front só desenha o painel e chama a rota.

**Tech Stack:** Back: FastAPI, Pydantic, PyYAML, pytest. Front: React 19, TypeScript, Tailwind v4.

**Spec:** `docs/superpowers/specs/2026-11-15-chat-assistente-design.md`

## Global Constraints

- Respostas em inglês; palavras-chave em inglês e português, comparadas sem acento e em minúsculas.
- Nenhum número inventado: sem dado, usa o `fallback` do assunto (sem números) e `used_data: false`.
- Falha de dado nunca vira erro HTTP na rota de chat. Só 404 (talhão) e 422 (mensagem inválida).
- Mensagem: 1 a 500 caracteres depois de aparar espaços.
- Textos, palavras-chave e perguntas sugeridas só em `app/config/chat.yaml`.
- A tela diz que é um assistente de demonstração com respostas prontas, não uma IA.
- Commits em inglês `tipo: descrição`, terminando com `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- Repositórios: back `/home/emerson/projetos/hackathon` (branch `feat/chat`), front `/home/emerson/projetos/earth-br--frontend` (branch `feat/chat`). Node: `export PATH=$HOME/.nvm/versions/node/v24.21.0/bin:$PATH`.

## Review Focus

1. **Palavra curta dentro de outra** ("hi" em "this", "oi" em "soil"): não pode casar saudação — casamento por palavra inteira. → teste na Task 1.
2. **Pergunta que casa dois assuntos** ("rain and soil moisture"): vence o de mais palavras-chave; empate, o primeiro do arquivo; resposta única e coerente. → teste na Task 1.
3. **NASA fora do ar / talhão fora da área do GAEZ**: resposta 200 com o texto fixo, `used_data: false`. → teste na Task 2.
4. **Propriedade sem cultura atual** perguntando de rotação ou prejuízo: texto fixo, sem erro. → teste na Task 2.
5. **Mensagem só com espaços, emoji ou muito longa**: 422 para vazia/longa; emoji/pontuação → genérico. → teste na Task 2.

---

### Task 1: Configuração e casamento de perguntas (back)

**Files:**
- Create: `app/config/chat.yaml`, `app/services/chat.py`, `tests/test_chat_match.py`
- Modify: `app/config_loader.py`

**Interfaces:**
- Produces: `ChatTopic(id: str, question: str | None = None, keywords: list[str], answer: str | None = None, fallback: str, sources: list[str] = [])`; `ChatConfig(generic: str, topics: list[ChatTopic])`; `AppConfig.chat: ChatConfig`.
- `chat.normalize(text: str) -> list[str]` — minúsculas, sem acentos, só letras/dígitos, em palavras.
- `chat.match(message: str, cfg: ChatConfig) -> ChatTopic | None` — pontuação = nº de palavras-chave presentes. Palavra-chave simples casa por palavra inteira; terminada em `*` casa por prefixo (`chuv*` casa "chuva", "chuvoso"); com espaço casa a sequência de palavras. Maior pontuação vence; empate → primeiro do arquivo; zero → `None`.
- `chat.suggestions(cfg: ChatConfig, after: str | None, n: int = 3) -> list[str]` — `question` dos assuntos seguintes ao assunto `after` na ordem do arquivo (dando a volta), pulando os sem `question`; `after=None` começa do primeiro.
- Assuntos (ordem do arquivo): `rain`, `soil_moisture`, `temperature`, `risk`, `dry_years`, `crops`, `rotation`, `financial`, `reports`, `sources`, `help`, `greeting`. Os quatro últimos têm `answer: null` (só `fallback`). `greeting` e `help` não têm `question`.

- [ ] **Step 1: Testes que falham** em `tests/test_chat_match.py`
  - `test_config_has_all_topics_with_fallback`: ids na ordem acima; todo assunto tem `fallback` não vazio e ao menos uma palavra-chave; `generic` não vazio.
  - `test_fallbacks_and_generic_have_no_digits`: nenhum `fallback` nem `generic` contém dígito.
  - `test_normalize`: `normalize("Como está a CHUVA, hoje?!") == ["como", "esta", "a", "chuva", "hoje"]`.
  - `test_match_english_and_portuguese` (parametrizado): "How is the rain this month?"→rain; "choveu pouco?"→rain; "is my soil dry?"→soil_moisture; "umidade do solo"→soil_moisture; "how hot is it"→temperature; "qual a temperatura"→temperature; "am I at risk?"→risk; "worst drought years"→dry_years; "anos de seca"→dry_years; "which crops suit my land?"→crops; "o que plantar"→crops; "compare rotation options"→rotation; "rotação de culturas"→rotation; "how much money could I lose?"→financial; "prejuízo"→financial; "download the pdf report"→reports; "where does the data come from?"→sources; "what can you do?"→help; "hello"→greeting; "oi"→greeting.
  - `test_short_keywords_do_not_match_inside_words`: "this soil"→soil_moisture (não greeting); "history"→`None`.
  - `test_most_keywords_win_and_tie_goes_to_first`: "rain and soil moisture"→soil_moisture (2 palavras-chave contra 1); "rain temperature"→rain.
  - `test_unknown_question_is_none`: "what is the capital of France?", "🙂", "???" → `None`.
  - `test_suggestions_skip_topic_and_wrap`: `suggestions(cfg, "rain")` = perguntas de soil_moisture, temperature, risk; `suggestions(cfg, "sources")` dá a volta e começa em rain; nenhuma lista contém `None`.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_chat_match.py -q` → FAIL (import).
- [ ] **Step 3:** Implementar modelos, `chat.yaml` e as três funções.
- [ ] **Step 4:** `.venv/bin/pytest -q` → tudo PASS; `.venv/bin/ruff check .` limpo.
- [ ] **Step 5:** Commit `feat: chat topics config and keyword matching`.

### Task 2: Respostas com dados reais e rotas (back)

**Files:**
- Create: `app/models/chat.py`, `app/api/chat.py`, `tests/test_chat_api.py`
- Modify: `app/services/chat.py`, `app/main.py`, `app/api_docs.py`, `tests/test_contract.py`, `README.md` (uma linha na lista do que a API faz, se houver), `docs/api.md` e `docs/openapi.json` (regerar)

**Interfaces:**
- Consumes: `signals.build_signals(plot, None, power, rasters)`; `monthly.normals/last_months` + `last_available_date`; `regional.suitability_ranking(plot, gaez)`; `regional.dry_years_report(plot, power)`; `rotation.compare(plot, farm, RotationRequest, power, rasters, gaez)`; `quiz._financial(plot, power, gaez)` (tornar público como `financial_section`); `get_config().crops`.
- Produces: `ChatMessage(message: str)` (aparada, 1–500); `ChatAnswer(topic: str, answer: str, used_data: bool, sources: list[str], suggestions: list[str])`; `ChatIntro(greeting: str, suggestions: list[str])`.
- `chat.reply(message: str, plot: Plot, farm: Farm, power, rasters, gaez) -> ChatAnswer`.
- Construtores de dados por assunto: `dict[str, Callable[[Context], dict[str, str] | None]]`; devolvem os campos do modelo já formatados, ou `None` sem dado. `reply` usa `fallback` quando o assunto não tem `answer`, o construtor devolve `None`, levanta qualquer exceção, ou falta um campo do modelo.
- Campos por assunto: `rain`/`soil_moisture`: `message` (frase do semáforo), `date`; `temperature`: `month` (ex.: "October 2026"), `value`, `normal`, `diff`, `direction` (above/below); `risk`: `alerts` (0–2), `rain_status`, `soil_status` (normal / below average / well below average); `dry_years`: `season` ("April to August"), `message`; `crops`: `items` ("Sorghum (46 out of 100), ..." — 3 primeiras); `rotation`: `verdict`, `current`, `current_total`, `alternative`, `alternative_total` (sem cultura atual ou sem alternativa → `None`); `financial`: `text` (só quando a seção trouxe estimativa).
- Alternativa da rotação: cultura não leguminosa mais apta (diferente da atual) seguida da leguminosa (`soil_restoring`) mais apta.
- Rotas: `POST /plots/{plot_id}/chat` → `ChatAnswer`; `GET /chat/suggestions` → `ChatIntro` (saudação = `fallback` do assunto `greeting`; 4 sugestões).

- [ ] **Step 1: Testes que falham** em `tests/test_chat_api.py` (fixtures de `tests/helpers.py`: `make_plot(client, crop="milho")`, `install_power`)
  - `test_rain_answer_uses_real_signal`: resposta contém a `message` do sinal de chuva de `/plots/{id}/signals`; `topic == "rain"`, `used_data is True`, `sources == ["NASA POWER"]`, 3 sugestões.
  - `test_each_data_topic_answers_with_data` (parametrizado: soil_moisture, temperature, risk, dry_years, crops, rotation, financial): 200, `used_data is True`, resposta contém ao menos um dígito e nenhum `{`.
  - `test_crops_answer_lists_most_suitable_first`: "which crops suit my land?" → contém "Sorghum (46 out of 100)".
  - `test_fixed_topics`: reports, sources, help, greeting → `used_data is False`, resposta = `fallback` da config.
  - `test_generic_answer_for_unknown_question`: "what is the capital of France?" e "🙂" → `topic == "generic"`, resposta = `generic`, `used_data is False`, 3 sugestões.
  - `test_power_outage_falls_back_to_fixed_text`: sem cache do POWER, "how is the rain?" → 200, `used_data is False`, resposta = `fallback` de rain, sem dígitos.
  - `test_outside_gaez_area_falls_back`: talhão em (-45, -5), "which crops suit my land?" → `fallback` de crops.
  - `test_no_current_crop_falls_back`: talhão sem cultura, "compare rotation options" e "how much could I lose?" → `fallback`, 200.
  - `test_invalid_messages_422`: `""`, `"   "`, 501 caracteres, corpo sem `message`.
  - `test_unknown_plot_404`.
  - `test_chat_intro`: `GET /chat/suggestions` → saudação da config e 4 sugestões.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_chat_api.py -q` → FAIL.
- [ ] **Step 3:** Implementar construtores, `reply`, modelos, rotas, resumo no `api_docs.SUMMARIES` e caminhos em `tests/test_contract.py`.
- [ ] **Step 4:** `.venv/bin/pytest -q` → tudo PASS; `ruff` limpo; `python -m app.export_openapi`.
- [ ] **Step 5:** Com o servidor local, `curl -X POST localhost:8000/plots/1/chat -H 'content-type: application/json' -d '{"message":"como está a chuva?"}'` → resposta com os números reais.
- [ ] **Step 6:** Commit `feat: chat endpoint answering from real field data`.

### Task 3: Janela de chat (front)

**Files:**
- Create: `src/components/ChatWidget.tsx`
- Modify: `src/lib/api.ts`, `src/components/AppShell.tsx`

**Interfaces:**
- `api.ts`: `type ChatAnswer = { topic: string; answer: string; used_data: boolean; sources: string[]; suggestions: string[] }`; `type ChatIntro = { greeting: string; suggestions: string[] }`; `api.chat(plotId: number, message: string)`; `api.chatIntro()`.
- `ChatWidget` (sem props; usa `useStore().activeProperty`): botão flutuante no canto inferior direito; painel com cabeçalho "earth + BR assistant" e o aviso "Demo assistant · pre-written answers built from your property's data. Not an AI."; lista de mensagens; fontes abaixo de cada resposta; sugestões clicáveis; campo de texto (máx. 500) com envio por Enter; indicador "typing" enquanto a chamada roda; erro de rede mostrado no chat com a pergunta mantida no campo; conversa reiniciada ao trocar de propriedade; sem propriedade → mensagem com link para `/propriedades/nova`; fecha com Esc; no celular ocupa a largura toda.
- Montado uma vez em `AppShell`, para todas as rotas `/app`.

- [ ] **Step 1:** Implementar `api.ts`, `ChatWidget.tsx` e montar no `AppShell`.
- [ ] **Step 2:** `npx tsc --noEmit` → 0 erros; `npx vite build` → ok.
- [ ] **Step 3:** Com front e back locais, captura de tela do chat aberto depois de perguntar "How is the rain?" (computador e celular): a resposta mostra os números reais e o aviso de demonstração aparece.
- [ ] **Step 4:** Commit `feat: demo assistant chat popup`.
