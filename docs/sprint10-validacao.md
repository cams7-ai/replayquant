# Validação da Sprint 10 — Estratégias modulares

## 1. Ambiente e estado verificado

Implementação verificada em 12/11/2026 no repositório ReplayQuant, partindo de HEAD `5c4d490`, que contém a especificação da Sprint 10. O estado inicial da árvore estava limpo. O hash efetivo de código de cada execução está no manifesto, incluindo os módulos e o controlador novos.

Python **3.12.14**, ambiente local `.venv` criado com `python -m venv .venv`, biblioteca padrão e `unittest`. Nenhuma dependência Python ou asset externo foi instalado. Para inspeção visual, foi usado o Playwright já disponível no ambiente com seu Node compatível e Chrome headless local. O Node do sistema foi usado para `node --check`.

A suíte de entrada passou com **136 testes**. A versão Python, ajudas principal/de `executar` e demonstrações manual/SMA com risco foram verificadas individualmente. Os cinco comandos iniciais retornaram 0. Registros auxiliares em `/tmp/replayquant-sprint10/base-commands.json` e `/tmp/replayquant-sprint10-base.log`.

## 2. Resultado da implementação

O schema 5 usa `mode: STRATEGY`, risco e análise obrigatórios. `StrategySpec` e seus parâmetros são imutáveis. O registro explícito cria instâncias independentes de SMA_CROSS/1, EMA_CROSS/1 e RSI_REVERSION/1. A SMA modular adapta o indicador existente. EMA e RSI usam recorrências racionais exatas e as sementes especificadas.

A sessão continua sendo `RiskSession`. Ela aplica o mesmo orçamento, exposição, filtros, reservas, revalidação, proteções e ledger das estratégias anteriores. O schema exportado novo é 5, com políticas financeiras herdadas `SPRINT09_V1`. O núcleo de reservas mantém seus contratos internos da Sprint 09, enquanto a projeção serializada nova usa schema 5. CSVs mantêm as colunas financeiras, incluindo disponível/reservado do modo de risco.

Cada avaliação identifica estratégia, versão, parâmetros, política numérica, candle, disponibilidade, contagem, prontidão e valores anteriores/atuais. Médias/RSI exportam numerador e denominador exatos, unidade e valor de apresentação com 12 casas HALF_EVEN. Sinais, decisões e ordens são ligados por IDs determinísticos. A API de ações aceita CANCEL para pendências do modo STRATEGY e conserva a liberação idempotente do coordenador.

Schemas 1, 2 e 4 e saída de análise 3 passaram nas regressões. A identidade inclui nome/versão/parâmetros e política dos indicadores no caminho novo, além dos hashes existentes. `--analise` redundante produziu os mesmos onze arquivos e identidade.

## 3. Comandos efetivamente executados

A rodada final gerou artefatos em **`/tmp/replayquant-sprint10-final-rfdgda2d`**. Seu `commands.json` registra argumentos completos, retorno esperado, código observado e stderr de **39 comandos**. As receitas de CLI estão na seção 8 de [Sprint 10](sprint10.md) e no README. Cada retorno foi capturado individualmente em subprocesso, inclusive os retornos 2 esperados.

| Grupo executado com `.venv/bin/python` quando aplicável | Quantidade | Esperado e observado |
| --- | --- | --- |
| `--version`, `-m replayquant --help`, `-m replayquant executar --help` | 3 | 0 |
| `demonstrar --formato json`, manual/SMA com e sem `--risco` | 4 | 0 |
| `executar`, SMA/EMA/RSI na fixture comum, formatos HTML/JSON/Markdown/texto | 12 | 2 |
| Repetição desses três cenários em JSON com `--analise` | 3 | 2 |
| RSI com `sprint10-candles-rsi.json`, quatro formatos e repetição com `--analise` | 5 | 0 |
| `-m replayquant.warmup`, três estratégias e suas repetições | 6 | 0 |
| Exemplos expandidos Sprint 07 e Sprint 09 equivalente, formato HTML | 2 | 0 |
| `node --check replayquant/assets/chart.js` e `indicators.js` | 2 | 0 |
| `-m unittest discover -s tests -v` | 1 | 0, 151 testes |
| `git diff --check` | 1 | 0 |

Os 15 testes da Sprint 10 também foram executados isoladamente. Eles cobrem tabela manual, igualdade, diferença abaixo da apresentação, janela/período 1, sequências planas/monotônicas, registro, JSON/API inválidos, identidade, resultado financeiro, reconciliação, prefixos, replay incremental, isolamento, duplicatas, lacuna, rollback antes/depois da recorrência, mínimos, cancelamento idempotente, custos/proteções, contexto decimal hostil, aquecimento e artefatos. Os testes anteriores continuam cobrindo limites de risco, prioridades de proteção e demais contratos financeiros.

Para cada um dos quatro cenários, os onze arquivos da primeira execução foram comparados por bytes com a execução repetida com `--analise`. Todos foram idênticos. Os três diagnósticos financeiros previstos na fixture comum apareceram em stderr e no relatório, com os códigos esperados. As exportações são geradas antes da apresentação de stdout.

## 4. Indicadores e comparação financeira observados

Todos os cenários têm capital próprio de 1000 USDT, sete candles fechados, cobertura de 01/01/2026 12:00 a 12:07 UTC, taxas e slippage zero. A tabela exata da seção 6 da especificação foi conferida pelos testes.

| Cenário independente | Fills | Trades encerrados | Caixa USDT | BTC final | Patrimônio bruto USDT | Retorno % | Drawdown máximo % | Código |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SMA 2/3, fixture comum | 1 | 0 | 983.4 | 0.000166 | 996.68 | −0.332 | 0.332 | 2 |
| EMA 2/3, fixture comum | 1 | 0 | 983.4 | 0.000166 | 996.68 | −0.332 | 0.332 | 2 |
| RSI 2, fixture comum | 0 | 0 | 1000 | 0 | 1000 | 0 | 0 | 2 |
| RSI 2, aberturas contínuas | 2 | 1 | 1000 | 0 | 1000 | 0 | 0.398406374502 | 0 |

SMA e EMA produziram BUY no quinto fechamento e SELL no sétimo. Na aprovação BUY, referência 120000, orçamento 10 USDT, stop 60000 e alvo 228000. A quantidade bruta é 10/60000 BTC e o piso de step 0.000001 dá **0.000166 BTC**, perda planejada **9.96 USDT** e reserva **19.92 USDT**. A abertura seguinte a 100000 revalida perda **6.64 USDT**, consome **16.6 USDT** e devolve a diferença da reserva. O SELL final fica `UNEXECUTED/NO_FUTURE_OPEN`. A posição é conservada e marcada a 80000, com valor 13.28 USDT, não realizado −3.32 USDT e realizado zero. Reservas são liberadas no encerramento normal.

RSI produziu BUY no quarto fechamento e SELL no sexto. Valores a partir do terceiro fechamento foram exatamente **0, 200/3, 600/7, 40 e 600/31**. No BUY, a referência 100000 define stop 50000, alvo 190000, orçamento 10 USDT e q=0.0002 BTC. Na fixture comum, a abertura a 120000 exigiria perda planejada `0.0002 × (120000 − 50000) = 14 USDT`, gerando `RISK_BUDGET_EXCEEDED`. A reserva de 20 USDT é liberada sem fill ou taxa. O SELL posterior gera `INSUFFICIENT_ASSET`.

Na fixture RSI contínua, o mesmo sinal compra a 100000 na abertura 5, com desembolso 20 USDT, e vende a 100000 na abertura 7, recebendo 20 USDT. Lucro e taxas são zero. O drawdown positivo decorre da queda após o pico patrimonial durante a posição. A reconciliação financeira e de reservas passou nos quatro cenários, incluindo as carteiras passivas independentes.

O texto da especificação foi esclarecido para descrever as aberturas RSI como eventos elegíveis sujeitos à revalidação, pois a fixture comum rejeita a compra antes de qualquer fill.

### Regressão dos exemplos expandidos

Sprint 07 e Sprint 09 equivalente conservaram seis fills iguais em horário, lado, quantidade, preço e taxa. Ambos encerraram com **1000.90155066834 USDT**, BTC zero, taxas **0.60339361166 USDT**, lucro **0.90155066834 USDT** e código 0. Hashes/IDs refletem o código atual.

## 5. Estabilidade do aquecimento

O módulo `replayquant.warmup` executa somente indicadores. A receita usa a fixture expandida já versionada da Sprint 07, identificada por hash, comparando os candles de índices 50 a 79 após históricos anteriores de 0, 10 e 50 candles. A referência tem 50 candles anteriores. Foram usados SMA/EMA 9/21 e RSI 14 com limiares 30/70. Cada combinação foi repetida e o JSON comparado por bytes.

```bash
python -m replayquant.warmup --config experiments/sprint10-sma.json --saida /tmp/aquecimento-sma-novo.json
python -m replayquant.warmup --config experiments/sprint10-ema.json --saida /tmp/aquecimento-ema-novo.json
python -m replayquant.warmup --config experiments/sprint10-rsi.json --saida /tmp/aquecimento-rsi-novo.json
```

| Indicador | Histórico anterior contra referência 50 | Comparáveis | Indisponíveis | Pontos com diferença exata no indicador | Divergências de sinais |
| --- | --- | --- | --- | --- | --- |
| SMA 9/21 | 0 | 9 | 21 | 0 | 0 |
| SMA 9/21 | 10 | 19 | 11 | 0 | 0 |
| EMA 9/21 | 0 | 9 | 21 | 9 | 0 |
| EMA 9/21 | 10 | 19 | 11 | 19 | 0 |
| RSI 14 | 0 | 15 | 15 | 15 | 0 |
| RSI 14 | 10 | 25 | 5 | 25 | 0 |

Os JSONs `warmup-sma.json`, `warmup-ema.json` e `warmup-rsi.json` registram diferenças absolutas por timestamp como razões exatas e os lados nas duas inicializações. A SMA coincidiu após a prontidão comum. EMA/RSI conservaram influência da semente. A amostra não apresentou divergências de sinais, inclusive nos pontos com diferenças numéricas. A comparação exclui pontos sem prontidão de sinal em qualquer lado e registra `WARMUP` para eles.

## 6. Verificação visual e offline

Os quatro HTMLs foram abertos no Chrome headless com Playwright já instalado no ambiente. A rodada final verificou desktop 1400×1000 e tela 390×900, com **zero exceções JavaScript e zero requisições HTTP externas**. Em tela estreita, largura da página e `scrollWidth` coincidiram em 390 px. Tabelas largas têm rolagem horizontal.

Foram inspecionadas capturas dos indicadores em desktop e tela estreita, com as três estratégias, e em mídia de impressão. O gráfico RSI fixa a escala em 0–100 e exibe os limiares 30/70. Redimensionar reenquadra os indicadores. A captura de impressão é preparada pelo evento `beforeprint` e conferida com mídia print. O gráfico de indicadores mantém dimensões válidas mesmo quando seu elemento é ocultado pelo CSS de impressão.

As cinco imagens de gráficos de cada relatório tiveram conteúdo e dimensões verificadas, incluindo candles, três carteiras e indicadores. A alternativa sem JavaScript conserva identidade, parâmetros, avaliações, sinais e decisões nas tabelas. Foram conferidos o texto de `noscript` e suas três tabelas da estratégia.

Registros em `visual.json`, capturas `*-desktop.png`, `*-mobile.png` e `*-print.png`, junto dos relatórios no diretório final. A inspeção foi de navegador e mídia CSS, sem impressão física. A primeira inicialização do Chrome no sandbox foi bloqueada por `setsockopt`; a permissão de ferramenta para execução local permitiu concluir. O Node 18 do sistema não executa a versão disponível de Playwright, por isso a inspeção usou o Node já fornecido pelo ambiente. Não houve instalação.

## 7. Limites e situação final

A implementação permanece sequencial, com snapshots completos para atomicidade e histórico de deduplicação em memória. Razões exatas recursivas podem aumentar de tamanho com o histórico. Não foi medida capacidade para grandes conjuntos. Apenas Python 3.12.14 e este ambiente foram executados.

O experimento compara regras em fixtures fictícias, com carteiras independentes e cobertura declarada. O diagnóstico de aquecimento compara indicadores em um sufixo comum. Custos, risco e hipóteses de execução seguem as sprints anteriores. Lucratividade não foi usada como condição de aprovação.

As entregas obrigatórias verificadas estão concluídas. Não houve commit, publicação ou negociação externa. Os arquivos auxiliares de `/tmp` podem ser removidos pelo sistema. Este documento preserva os resultados observados e o README fornece as receitas para reproduzi-los.

## 8. Exemplos expandidos lucrativos de SMA, EMA e RSI

Revisão em 12/11/2026, solicitada após a conclusão da sprint. Criadas as configurações
`experiments/sprint10-ema-expandido.json` e `experiments/sprint10-rsi-expandido.json`,
com os 240 candles existentes da Sprint 07. A fixture foi comparada por bytes com
HEAD e permaneceu idêntica. Estes exemplos foram ajustados na própria fixture
sintética, originalmente construída para demonstrar SMA com resultado positivo.

### Triagem de sinais e tentativas

A inspeção usou os indicadores reais do projeto, sem alterar suas regras, em uma
lista pequena de parâmetros. Foi examinada EMA 9/21 e as quatro variantes RSI abaixo.
Esta etapa calculou somente sinais, sem simular carteiras para as variantes descartadas.

| RSI período / sobrevenda / sobrecompra | BUY | SELL | Observação da sequência de sinais |
| --- | --- | --- | --- |
| 14 / 30 / 70 | 2 | 3 | SELL adicional às 15:28 |
| 14 / 30 / 90 | 2 | 2 | Dois pares BUY/SELL |
| 21 / 30 / 70 | 2 | 2 | Dois pares BUY/SELL, limiares 30/70 |
| 14 / 40 / 80 | 4 | 2 | Duas compras adicionais após os dois pares iniciais |

Foi escolhido RSI 21 com limiares 30/70. A EMA 9/21 apresentou três pares BUY/SELL.
As duas configurações foram inicialmente executadas com o risco do exemplo
`sprint09-sma-expandido.json`, step/mínimo de 0.000001 BTC e risco de 1%.

| Tentativa financeira inicial | Lucro realizado USDT | Caixa final USDT | Código | Diagnóstico |
| --- | --- | --- | --- | --- |
| EMA 9/21 | 1.20704256627577 | 1001.20704256627577 | 2 | Terceira compra rejeitada por RISK_BUDGET_EXCEEDED, SELL posterior sem ativo |
| RSI 21, 30/70 | 1.90667847574062 | 1001.90667847574062 | 0 | Duas operações encerradas |

Para os exemplos finais, foram adotados os mesmos filtros e risco do exemplo
`sprint09-sma-equivalente-sprint07.json`. O risco de 1,1% e step/mínimo de 0.001 BTC
produzem lotes de 0.001 BTC e margem para revalidar as aberturas deste cenário.
A EMA final inclui a terceira operação perdedora e encerra com código 0. A escolha
não foi feita pelo maior lucro observado.

### Configuração e resultados finais

Capital inicial de 1000 USDT em cada carteira. Taxa e slippage de 0.001 por execução,
exposição máxima de 100%, stop de 10%, alvo de 20%, perda diária de 3%, drawdown de
5% e preço com idade máxima de 60 segundos. `min_notional=0`. Indicadores, custos,
execução e regras financeiras permanecem os implementados na sprint.

| Resultado | EMA 9/21 | RSI 21, 30/70 |
| --- | --- | --- |
| Avaliações / sinais / fills | 240 / 6 / 6 | 240 / 4 / 4 |
| Operações encerradas | 3 | 2 |
| Caixa final USDT | 1000.71085163730 | 1001.93754109984 |
| Realizado líquido USDT | 0.71085163730 | 1.93754109984 |
| Retorno % | 0.071085163730 | 0.193754109984 |
| Taxas USDT | 0.60322322270 | 0.40114808016 |
| Impacto de slippage USDT | 0.60322514 | 0.40115082 |
| Drawdown máximo % | 0.106425847313 | 0.050896550140 |
| BTC final / código | 0 / 0 | 0 / 0 |

As cinco saídas ocorreram por sinal, sem gatilho protetivo. As duas carteiras e seus
benchmarks reconciliaram. As operações individuais e os comandos para reproduzir
os relatórios estão no README, em “Exemplos lucrativos de EMA e RSI com 240 candles”.
Os resultados líquidos já incluem taxas e slippage.

### Verificação desta revisão

As execuções HTML finais usaram os comandos abaixo e retornaram individualmente 0.

```bash
.venv/bin/python -m replayquant executar --dados data/fixtures/sprint07-candles-expandido.json --config experiments/sprint10-ema-expandido.json --saida runs/sprint10-ema-expandido --formato html > runs/sprint10-ema-expandido.html
.venv/bin/python -m replayquant executar --dados data/fixtures/sprint07-candles-expandido.json --config experiments/sprint10-rsi-expandido.json --saida runs/sprint10-rsi-expandido --formato html > runs/sprint10-rsi-expandido.html
```

Cada configuração foi repetida em JSON com `--analise` e diretório novo. Os onze
artefatos foram comparados por bytes, com igualdade em ambas as estratégias.
Foram conferidos código 0, lucro realizado positivo, BTC final zero, ausência de
rejeições, reconciliação, soma dos trades e os valores exibidos no README.
Os 15 testes existentes da Sprint 10 passaram nesta revisão. `git diff --check`
também passou. A implementação e os assets não foram alterados nesta revisão.

Os relatórios finais ficam em `runs/sprint10-ema-expandido.html` e
`runs/sprint10-rsi-expandido.html`, com os respectivos diretórios de artefatos.
Tentativas iniciais e repetições ficaram em
`/tmp/replayquant-exemplos-ema-rsi-sbdvd288`, com configurações iniciais e resultados
em `tentativas.json`. A conferência desta revisão é financeira e estrutural.
A inspeção visual da seção 6 corresponde à implementação original da sprint.

### Inclusão do SMA na receita expandida

A receita do README passou a incluir `experiments/sprint10-sma-expandido.json`.
A seção foi atualizada para apresentar três configurações, os parâmetros reais,
a coluna de resultados SMA e suas três operações. O diretório de saída do comando
SMA é próprio, `sma`, evitando colisão com a saída `ema`.

O arquivo SMA adicionado usa janelas 9/21, capital de 1000 USDT, taxa/slippage zero,
step e mínimo de 0.000001 BTC, nocional mínimo zero, risco de 1%, exposição de 100%,
stop de 50%, alvo de 90%, perda diária e drawdown de 90% e idade máxima de preço de
60 segundos. Esses parâmetros foram conservados. O README distingue esses valores
dos filtros, custos e limites usados pelos exemplos EMA/RSI.

Comando efetivamente executado, com retorno **0** e stderr vazio.

```bash
.venv/bin/python -m replayquant executar --dados data/fixtures/sprint07-candles-expandido.json --config experiments/sprint10-sma-expandido.json --saida runs/sprint10-sma-expandido --formato html > runs/sprint10-sma-expandido.html
```

Foram observadas 240 avaliações, seis sinais e seis fills, três operações encerradas,
BTC final zero e caixa **1000.42208230 USDT**. Lucro realizado **0.42208230 USDT**,
retorno **0.042208230000%**, taxas e slippage zero, drawdown máximo **0.010099486656%**.
Todas as saídas ocorreram por sinal. As quantidades e resultados foram 0.000200 BTC
com +0.22783800 USDT, 0.000200 BTC com +0.23526000 USDT e 0.000198 BTC com
−0.04101570 USDT. A soma reconcilia com o lucro e o saldo final. As reconciliações
financeira e de reservas passaram. Os onze artefatos e o HTML foram gerados.

A revisão conferiu os parâmetros das três configurações e os valores do README
contra os relatórios correspondentes. `git diff --check` passou. A diferença entre
os três resultados inclui custos e dimensionamento distintos, além das regras dos
indicadores. A revisão alterou documentação e preservou as configurações fornecidas.
