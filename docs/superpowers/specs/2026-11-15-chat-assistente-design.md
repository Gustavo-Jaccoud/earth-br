# Chat de perguntas (assistente de demonstração) — Design

Data: 2026-11-15 · Status: aguardando aprovação

## Intenção

Um popup de chat dentro do site onde a pessoa pergunta, em texto livre, sobre o que o sistema já
mostra nos relatórios e na análise. **Não há IA**: não há tempo para integrar uma. As respostas são
textos prontos, escolhidos por palavras-chave, preenchidos com os **dados reais** da propriedade
ativa. Decisões do time:

- Aceita qualquer pergunta; pergunta fora do assunto recebe uma resposta genérica.
- As respostas são abertas, para servir a várias perguntas parecidas.
- Respostas com dados reais; se o dado faltar ou vier inconsistente, responde o **texto fixo sem
  números** daquele assunto.

## Objetivos, não-objetivos, anti-objetivos

- **Objetivos:** chat disponível nas telas internas do app; respostas coerentes com o que os
  relatórios e a análise mostram; textos editáveis pelo time sem mexer em código; caminho pronto
  para trocar por uma IA real depois.
- **Não-objetivos:** IA de verdade; memória da conversa (cada pergunta é respondida sozinha);
  histórico salvo no servidor; respostas em português; chat na página inicial.
- **Anti-objetivos:** número inventado; resposta que contradiz o painel ou o relatório; a tela dar a
  entender que é uma IA.

## Abordagens consideradas

| | Abordagem | Trade-off |
|---|---|---|
| A | Tudo no front (palavras-chave e modelos no front, dados pela API atual) | Não mexe no back, mas o front não tem testes e os textos ficam longe das outras frases |
| **B (escolhida)** | Rota de chat no back; assuntos, palavras-chave e respostas em arquivo de configuração; o front só desenha a janela | Testável, editável pelo time, e trocar por IA real muda só a rota. Um pouco mais de trabalho |

## Back

**Rota:** `POST /plots/{plot_id}/chat` com `{"message": "texto"}` (1 a 500 caracteres) →

```json
{"topic": "rain", "answer": "It rained 15.2 mm ...", "used_data": true,
 "sources": ["NASA POWER"], "suggestions": ["Which crops suit my land?", "..."]}
```

- `topic`: id do assunto casado, ou `"generic"`.
- `used_data`: `false` quando caiu no texto fixo (dado ausente/inconsistente) ou no genérico.
- `suggestions`: 3 perguntas sugeridas (de outros assuntos), para os botões do chat.
- `GET /chat/suggestions` → perguntas iniciais, para o chat aberto vazio.
- Talhão inexistente → 404; mensagem vazia ou longa demais → 422. Falha de dado **nunca** vira erro:
  vira texto fixo.

**Configuração:** `app/config/chat.yaml`, um bloco por assunto: `id`, `keywords`, `answer` (modelo
com campos a preencher), `fallback` (texto fixo, sem números), `sources`, `question` (a pergunta
sugerida). Mais `generic` (resposta genérica) e `greeting`.

**Casamento:** a pergunta é normalizada (minúsculas, sem acentos); cada assunto pontua pelo número
de palavras-chave encontradas; vence o de maior pontuação (empate: o primeiro do arquivo); sem
nenhuma palavra-chave → genérico. Palavras-chave em **inglês e português**; respostas em **inglês**
(o site é em inglês).

**Assuntos (chamada do assistente, editável):**

| id | Responde com | Dado |
|---|---|---|
| `rain` | chuva dos últimos 30 dias contra a média | semáforo de chuva |
| `soil_moisture` | umidade do solo contra a média | semáforo de umidade |
| `temperature` | temperatura do último mês completo contra a normal | série mensal |
| `risk` | situação geral: quantos alertas e qual o pior | os dois semáforos |
| `dry_years` | anos mais secos e estação chuvosa do local | anos secos |
| `crops` | culturas mais aptas para o local | aptidão (GAEZ) |
| `rotation` | cultura atual comparada com a alternativa mais apta (cereal → leguminosa) | comparador |
| `financial` | perda média estimada por falta de água na cultura atual | mesma conta da trilha |
| `reports` | como gerar e baixar relatórios | texto fixo |
| `sources` | de onde vêm os dados e suas limitações | texto fixo |
| `help` | o que dá para perguntar | texto fixo |
| `greeting` | saudação | texto fixo |

"Inconsistente" = fonte indisponível, valor ausente, ou resposta sem os campos que o modelo usa.
Os números são formatados do mesmo jeito que no painel, para não haver divergência.

## Front

Botão flutuante no canto inferior direito, em todas as telas internas (`/app/...`). Abre um painel
(no celular, ocupa a largura toda):

```
┌─────────────────────────────────────┐
│ earth + BR assistant            [x] │
│ Demo assistant · pre-written        │
│ answers from your property's data   │
├─────────────────────────────────────┤
│        How is the rain this month?  │  ← pergunta
│ It rained 15.2 mm in the last 30    │
│ days, 64% below average (41.7 mm).  │  ← resposta
│ Source: NASA POWER                  │
│ [Which crops suit my land?] [...]   │  ← sugestões clicáveis
├─────────────────────────────────────┤
│ Ask about your land…          [▶]   │
└─────────────────────────────────────┘
```

- Aviso fixo no topo de que é um assistente de demonstração com respostas prontas, não uma IA.
- Aberto vazio: saudação e perguntas sugeridas.
- Usa o talhão da propriedade ativa; a conversa fica só na memória (some ao recarregar) e é
  reiniciada ao trocar de propriedade. Sem propriedade cadastrada, o chat pede para cadastrar uma.
- Erro de rede: mensagem no próprio chat, com a pergunta mantida para reenviar.

## Testes

- Back (pytest): cada assunto casa em inglês e em português; resposta com dados traz os números do
  semáforo; fonte fora do ar → texto fixo e `used_data: false`; pergunta estranha → genérico;
  validação de mensagem; configuração carrega e todo assunto tem `fallback`.
- Front: compilação e captura de tela do chat aberto com uma resposta real.

## Deixado para quem implementa

Lista final de palavras-chave e redação dos textos; pequena espera visual ("digitando") antes da
resposta; detalhes de estilo seguindo os componentes existentes.
