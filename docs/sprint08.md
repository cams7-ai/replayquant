# Sprint 08 — Ledger, métricas e referências

**Projeto:** ReplayQuant  
**Nível:** básico  
**Referência:** [Planejamento](planejamento.md), especialmente seções 4, 8, 21 e 23  
**Pré-requisitos:** [Sprint 06](sprint06.md), [Sprint 07](sprint07.md) e seus registros de [validação inicial](sprint06-validacao.md) e [validação SMA](sprint07-validacao.md)  
**Estado:** especificação para implementação; criar este documento não conclui a Sprint 08.

## 1. Objetivo e ponto de partida

Explicar para onde foi cada unidade de capital e medir o resultado do replay por meio de um ledger auditável, curva patrimonial causal, operações encerradas e referências comparáveis. O estudante deverá conseguir reconciliar uma execução desde o saldo inicial até o patrimônio final, distinguindo dinheiro disponível, custo da posição, lucro realizado, variação ainda não realizada e custo hipotético de liquidar.

Trabalhar na raiz `/home/cams7/Dev/Cripto_Tests/replayquant`, evoluindo o código existente. Inspecionar `git status`, instruções `AGENTS.md` aplicáveis, implementação e testes antes de editar. Verificar os pré-requisitos pela suíte atual; os registros anteriores não substituem a conferência do estado real. Preservar alterações existentes e registrar pré-requisito ausente antes do trabalho dependente.

O projeto já possui modo manual, SMA causal, slippage, interrupção por lacunas, relatórios e gráfico Lightweight Charts 5.2.0 incorporado ao HTML. A apresentação atual calcula resultados de pares encerrados, mas isso não substitui o ledger e as métricas desta etapa. Esta sprint formaliza esses resultados em contratos financeiros reutilizáveis, sem recalcular contabilidade no JavaScript.

## 2. Escopo e limites

Implementar ledger de movimentos por ativo, reconstrução de saldos, custo da posição, histórico de trades encerrados, marcação a mercado, curva patrimonial, métricas, referências manter USDT/comprar e manter BTC e exportações JSON/JSONL, CSV e Markdown. Ampliar texto/HTML com fórmulas, unidades, motivos de indisponibilidade e memória de cálculo.

Manter `FICTICIA/BTCUSDT/1m`, BTC inicial zero, posições compradas de quantidade fixa, preenchimentos totais e uma pendência por vez. Preservar os sinais, preços, taxas, decisões e ordem temporal das sprints anteriores. Adicionar análise não pode mudar quando comprar ou vender.

Python >= 3.11, referência 3.12.14, biblioteca padrão e `unittest`; registrar o Python efetivamente usado. Reutilizar o bundle e as licenças já versionados do gráfico. Não instalar pacotes nem atualizar bibliotecas nesta etapa; execução e validação obrigatórias são offline.

Ficam fora: reservas operacionais, risco, stops/alvos, vendas parciais, FIFO para múltiplos lotes, depósitos/retiradas, remuneração de caixa, múltiplos instrumentos, carteira compartilhada, EMA/RSI, dados reais, otimização, anualização, Sharpe/Sortino, intervalos de confiança, banco, web hospedada, AWS e negociação real. Não adicionar liquidação forçada: o único encerramento obrigatório é **KEEP_OPEN**. Uma futura liquidação exigirá regra explícita e evento negociável suportado pelos dados.

## 3. Compatibilidade, precisão e identidade

### 3.1. Ativação da análise

Adicionar `--analise`, opção booleana sem argumento, a `demonstrar` e `executar`. A seleção da estratégia continua igual: demonstração manual por padrão, `demonstrar --estrategia sma` para SMA e `executar` despachando pelo schema da configuração.

Sem `--analise`, preservar schemas, formatos, três artefatos e códigos atuais. Com `--analise`, produzir manifesto/eventos/relatório **schema 3** e as exportações da seção 9. Manter candles schema 1, configuração manual schema 1 e configuração SMA schema 2: análise não altera os schemas de entrada. O modo enriquecido deve declarar `input_config_schema_version` e `simulation_mode: MANUAL|SMA`.

Na API Python, oferecer a mesma opção explícita de análise nos pontos de criação de manifesto e relatório, com validação de tipo booleano. Reutilizar o núcleo de ledger na API incremental e no replay de arquivos. O implementador pode ajustar nomes internos, documentando chamadas completas; não criar um segundo motor financeiro para a CLI.

### 3.2. Números, datas e serialização

Preservar JSON estrito, validação também na API, UTC, candles `[início, fim)`, limites de entrada e strings decimais das sprints anteriores. Valores derivados não herdam o limite de 18 dígitos da entrada, mas precisam ser finitos e representáveis exatamente pelo contexto financeiro local de precisão 40, `ROUND_HALF_EVEN`, com erro em operação inexata antes da mutação. Não alterar contexto, traps ou flags externos.

Movimentos, saldos, taxas, bases de custo e lucros são `Decimal`. Razões de retorno, taxas de acerto, expectativa e drawdown devem preservar numerador/denominador exatos, podendo usar `Fraction`. Somente sua apresentação pode arredondar. Não transformar contas em `float` para contornar divisões periódicas.

Cada métrica numérica é um objeto com `value`, `unit`, `reason`, `numerator`, `denominator`. Valores indefinidos têm `value: null`, motivo estável e razão nula. Contagens/durações válidas usam inteiros e razão nula; valores monetários exatos usam string decimal e razão nula. Razões usam strings de inteiros no numerador/denominador, já na unidade exibida, e `value` decimal com **12 casas**, arredondamento `ROUND_HALF_EVEN`. Não usar esse valor arredondado para classificar ganho/perda, escolher drawdown ou reconciliar contas.

Exemplos de unidades: `USDT`, `USDT/TRADE`, `%`, `SECONDS`, `COUNT`. Ausência de trades não torna o retorno patrimonial indefinido quando há capital e marcações válidas. Zero é válido para retorno zero, custos zero, nenhuma exposição e drawdown zero; taxa de acerto sem trades é indisponível.

Quantidades usam `BTC`. Fixar as chaves escalares de `analysis.metrics` abaixo; cada valor segue o objeto de métrica definido acima:

```text
realized_pnl, unrealized_pnl, final_cash, final_asset_quantity,
final_gross_equity, final_hypothetical_liquidation_equity,
portfolio_return_pct, hypothetical_liquidation_return_pct,
paid_fees, slippage_impact, attributed_execution_costs,
closed_trade_count, win_count, loss_count, break_even_count,
win_rate_pct, expectancy, max_drawdown_pct, max_drawdown_amount,
max_drawdown_duration_seconds, observation_duration_seconds,
time_in_position_seconds, time_in_position_pct
```

O retorno percentual de cada trade é um objeto de métrica em `return_pct` no JSON; no CSV, achatar seu `value`, `numerator` e `denominator` nas colunas especificadas na seção 9.1.

### 3.3. Reprodução

Preservar hashes dos bytes de dados/configuração e a lista ordenada `code_files`, incluindo Python, todos os assets e metadados conforme a implementação atual. No modo enriquecido, acrescentar à identidade canônica usada para `run_id` o campo `analysis_policy: "SPRINT08_V1"`, além de `data_hash`, `config_hash`, `code_hash` e `python_version`. Sem análise, manter a definição anterior da identidade.

O manifesto enriquecido registra essa política, schema original da configuração, modo, regras de amostragem, arredondamento, encerramento, benchmarks e ausência de aportes. A flag precisa participar da identidade: mesma entrada com/sem análise não pode compartilhar `run_id` apesar de gerar contratos de saída diferentes. Caminho de saída e relógio real continuam fora da identidade.

## 4. Ledger e operações encerradas

### 4.1. Fonte das alterações financeiras

O ledger é a fonte auditável dos movimentos da carteira. Integrá-lo ao preenchimento: preparar cálculos, validar ordem/saldo, preparar entrada e novos saldos e então efetivar a transição completa. Não manter um saldo mutável e gerar depois um ledger meramente decorativo. Uma alternativa válida é usar entradas imutáveis e projetar saldos a partir delas, com cache sempre reconciliável.

Criar uma entrada `INITIAL_BALANCE` no início e uma entrada `FILL` para cada execução aceita, contendo simultaneamente os deltas em USDT e BTC. Trata-se de ledger por unidade, sem somar BTC a USDT nem exigir escrituração societária. A taxa registrada é uma explicação do delta de caixa, não um segundo débito.

| Campo da entrada | Contrato |
| --- | --- |
| `schema_version`, `run_id`, `portfolio` | Versão 3, experimento e carteira `STRATEGY`, `HOLD_USDT` ou `BUY_HOLD_BTC` |
| `ledger_id`, `ledger_seq` | ID determinístico e sequência crescente dentro da carteira |
| `at`, `source_event_seq`, `entry_type` | UTC, sequência do evento de origem e tipo `INITIAL_BALANCE` ou `FILL` |
| `order_id`, `execution_id`, `lot_id` | Referências pertinentes; nulas na inicialização |
| `side`, `quantity`, `reference_price`, `effective_price` | Lado e dados da execução; nulos quando inaplicáveis |
| `cash_delta`, `asset_delta`, `gross`, `fee` | Deltas com sinal; bruto/taxa não negativos, em suas unidades |
| `cash_after`, `asset_after`, `fees_after`, `cost_basis_after` | Estado financeiro após a entrada |

Na inicialização, `source_event_seq: 0`, caixa creditado igual ao capital, BTC/taxas/base de custo zero, bruto/taxa zero. Isso registra o saldo de abertura, sem introduzir depósitos ou retiradas durante o experimento. IDs são únicos por experimento/carteira, e `ledger_seq` começa em 1.

```text
BUY:  cash_delta = -(preço efetivo * q + taxa); asset_delta = +q
SELL: cash_delta = +(preço efetivo * q - taxa); asset_delta = -q

caixa atual = soma(cash_delta desde INITIAL_BALANCE)
BTC atual   = soma(asset_delta desde INITIAL_BALANCE)
taxas pagas = soma(fee dos FILL aceitos)
```

Aceitação de ordem, aquecimento, sinal, rejeição e término sem execução não criam movimento financeiro. Reaplicar fill idêntico é inócuo no ledger, saldos e trades; mesmo ID com conteúdo divergente é erro antes da mutação. Falha aritmética ou de validação não pode deixar entrada, taxa, base de custo ou saldo parcialmente atualizado.

### 4.2. Base de custo e trades

Uma compra integral abre um lote identificado por sua execução. `cost_basis = bruto da compra + taxa da compra`. Uma venda integral fecha esse lote: `net_proceeds = bruto da venda - taxa da venda`; `realized_pnl = net_proceeds - cost_basis`. Após a venda, a base de custo da posição é zero. Não criar amortização parcial ou médias de lotes nesta sprint.

Cada trade encerrado contém `trade_id`, referências às duas ordens/execuções e lote, horários de entrada/saída, quantidade, preços de referência/efetivos, brutos, taxas de ambas as pontas, desembolso, recebimento, lucro líquido, retorno sobre desembolso, duração em segundos e classificação `WIN|LOSS|BREAK_EVEN`. Classificar pelo sinal exato do lucro líquido, sem tolerância baseada em apresentação.

Uma compra aberta aparece em `open_position`, com lote, quantidade, horário e base de custo, mas não entra na contagem de operações encerradas nem na expectativa. O resultado realizado acumulado é a soma dos lucros dos trades encerrados, inclusive quando há outra posição aberta. Nenhum trade encerrado significa realizado igual a zero; isso não inventa um trade de resultado zero.

O campo legado `round_trip_result` mantém o significado das sprints anteriores: só existe para exatamente uma ida e volta aplicável. Os novos campos de análise suportam múltiplas operações sem reinterpretar esse campo.

## 5. Patrimônio, marcação e encerramento

### 5.1. Amostragem causal

A curva inclui um ponto inicial antes do primeiro evento e pontos após cada `OPEN`, `FILLED` e `CLOSE` aceitos. No `OPEN`, amostrar o estado anterior ao possível fill; no `FILLED`, amostrar o estado financeiro posterior, usando o mesmo preço de abertura de referência. No `CLOSE`, usar o fechamento recém-disponibilizado. Não usar preço efetivo como marcação de mercado: isso esconderia o impacto inicial do slippage.

Cada ponto tem `point_seq` próprio e crescente por carteira, `at`, `source_event_seq`, fase `INITIAL|OPEN|FILL|CLOSE`, caixa total/disponível/reservado, BTC, preço e horário da marcação, base de custo, realizado acumulado, não realizado bruto, patrimônio bruto e valor líquido hipotético de liquidação. A inicialização usa `source_event_seq: 0`, marcação nula com `NO_MARKET_PRICE_YET`; BTC zero permite patrimônio igual ao caixa.

Eventos com mesmo timestamp continuam distintos por sequência. Duplicatas não criam pontos repetidos. `OPEN` expõe somente seu preço; mudanças em high/low/close/volume futuros não alteram pontos anteriores. Marcação é consulta, sem entrada de ledger ou ordem.

### 5.2. Identidades financeiras

Com caixa total `C`, posição `q`, preço de marcação disponível `m`, base de custo aberta `B` e capital inicial `C0`:

```text
valor bruto da posição = q * m
patrimônio bruto E    = C + q * m
não realizado bruto U = q * m - B                 (zero sem posição)
E                     = C0 + realizado acumulado R + U
```

Nesta sprint não há reservas: `cash_available = cash_total`, `cash_reserved = 0`. Caixa total já inclui qualquer reserva em uma evolução futura; não somá-la novamente ao patrimônio.

Para o valor hipotético líquido de liquidação, com slippage de venda `a` e taxa `f`:

```text
preço hipotético de saída = m * (1 - a)
bruto hipotético          = q * preço hipotético de saída
taxa hipotética           = bruto hipotético * f
patrimônio líquido hipotético = C + bruto hipotético - taxa hipotética
```

São valores de cenário ao preço disponível, sem garantia de execução. Não lançar essa taxa no ledger, gerar fill, zerar BTC ou chamar a posição de encerrada. Sem posição, os dois patrimônios são iguais ao caixa. Exibir separadamente os custos hipotéticos ainda não pagos.

O retorno obrigatório da carteira usa o patrimônio bruto marcado, já afetado pelos custos efetivamente incorridos. O retorno de liquidação hipotética é outra métrica, claramente rotulada; não misturar denominadores ou descontar os mesmos custos duas vezes.

### 5.3. Fim normal e lacunas

O padrão é manter posição aberta e marcar no último fechamento aceito. O horizonte é da primeira abertura ao último fechamento processado. Não criar venda no último close ou em abertura inexistente para obter retorno realizado.

No SMA interrompido por lacuna, conservar ledger, posição e pendência antes da abertura posterior, como na Sprint 07. A análise do prefixo pode ser apresentada com `status: INTERRUPTED`, `scope: ACCEPTED_PREFIX`, `observed_until` e diagnóstico. Benchmarks devem parar no mesmo prefixo. Não publicar uma comparação de período completo ou retomar operações retroativamente. A última marca é do último evento aceito, identificada com seu horário; não é preço negociável atual após a lacuna.

As durações e retornos desse prefixo são descritivos e parciais. Ordem pendente continua `NEW` na interrupção; no término normal sem abertura futura, continua valendo `UNEXECUTED/NO_FUTURE_OPEN`. Preservar códigos 1 e 2 pertinentes.

## 6. Métricas obrigatórias e convenções

### 6.1. Retornos, custos e operações

| Métrica | Regra |
| --- | --- |
| Resultado realizado | Soma exata dos lucros dos trades encerrados, em USDT |
| Resultado não realizado bruto | Valor marcado da posição menos sua base de custo, em USDT |
| Retorno da carteira | `(E_final / C0 - 1) * 100`, em %, incluindo custos efetivamente incorridos |
| Retorno hipotético de liquidação | `(E_liquidação / C0 - 1) * 100`, em %, com rótulo de cenário |
| Retorno de cada trade | `lucro líquido / desembolso da compra * 100`, em % |
| Taxas pagas | Soma das taxas dos fills aceitos, sem custos hipotéticos |
| Impacto de slippage | Soma de `(p_eff - p_ref)*q` nas compras e `(p_ref - p_eff)*q` nas vendas |
| Custos atribuídos à execução | Taxas pagas + impacto de slippage; decomposição explicativa, sem novo débito |
| Operações encerradas | Número de pares compra/venda integralmente preenchidos |
| Ganhos/perdas/empates | Contagens por sinal exato do lucro de cada par |
| Taxa de acerto | `ganhos / operações encerradas * 100`; sem trades: `null/NO_CLOSED_TRADES` |
| Expectativa | Média aritmética dos lucros líquidos dos trades encerrados, em `USDT/TRADE`; sem trades: `null/NO_CLOSED_TRADES` |

Não tratar taxa de acerto como proporção de sinais aprovados. Ordens rejeitadas, não executadas e posições abertas ficam em contagens próprias, sem entrar no denominador dos trades encerrados. Não anualizar, extrapolar retorno ou chamar expectativa amostral de previsão de lucro.

### 6.2. Drawdown e duração

Usar toda a curva da seção 5, incluindo capital inicial, quedas de custo nos fills e informações disponíveis nas aberturas. Para cada ponto `k`:

```text
pico H(k) = máximo E(j), para j <= k
queda absoluta = H(k) - E(k)
drawdown_pct = (H(k) - E(k)) / H(k) * 100
```

O máximo drawdown percentual é o maior valor exato da razão. Informar sua queda absoluta e referências de pico, vale e recuperação em `max_drawdown_episode`. A métrica `max_drawdown_amount` é a maior queda absoluta da curva, que não precisa pertencer ao mesmo episódio do máximo percentual. Empate de magnitude escolhe o primeiro vale pela sequência.

Um episódio começa no último ponto do pico antes de cair e termina no primeiro ponto em que `E >= pico anterior`. Enquanto não há queda, um ponto que iguala o pico atualiza a âncora para o instante mais recente. Dentro do episódio, preservar a âncora até recuperar. Isso evita contar um período de caixa estável anterior como tempo em drawdown.

A duração é tempo UTC decorrido, não número de eventos. Episódio não recuperado tem `recovered: false`, `recovery_at: null`, motivo `NOT_RECOVERED` e duração observada até o fim aceito. Queda em eventos do mesmo timestamp pode ter duração zero. Informar separadamente a maior duração observada e seu episódio; não presumir que corresponde ao máximo drawdown percentual. Empates de duração escolhem o episódio iniciado primeiro.

Curva constante, inclusive sem trades, tem drawdown zero e duração zero; referências de episódio inexistente são nulas com `NO_DRAWDOWN`. Base de pico zero ou inválida não admite divisão silenciosa; rejeitar na validação do componente ou registrar indisponibilidade com motivo conforme a origem, sem infinito. Os experimentos válidos desta sprint partem de capital positivo.

### 6.3. Tempo em posição

Integrar os intervalos entre fill de compra e fill de venda, usando `[entrada, saída)`. Uma posição ainda aberta contribui até o último fechamento aceito, sem se tornar trade encerrado. Abertura de intenção e tempo de aquecimento não contam como exposição.

`time_in_position_seconds` é a soma desses segundos; `time_in_position_pct = segundos em posição / segundos do horizonte * 100`. O horizonte inclui todo o intervalo da primeira abertura ao último fechamento, inclusive aquecimento. Sem posição, tempo e percentual são zero se há horizonte válido; horizonte zero tem percentual `null/ZERO_OBSERVATION_DURATION`.

## 7. Referências comparáveis

Criar duas carteiras virtuais independentes, sem compartilhar saldo com a estratégia. Cada uma começa com o mesmo capital `C0`, primeira abertura, último fechamento aceito e moeda de relatório. Não somar seus saldos como carteira conjunta.

**HOLD_USDT:** manter todo o capital em USDT, sem juros, operações ou taxas. Patrimônio constante `C0`, retorno zero e exposição BTC zero. USDT não é tratado como dólar ou ativo livre de risco garantido.

**BUY_HOLD_BTC:** compra previamente definida na primeira abertura disponível e mantém até o fim. A decisão passiva é anterior ao replay e não exige cruzamento SMA; não antecipar sinais da estratégia para fazer essa compra. Aplicar as mesmas taxas e slippage da configuração. Usar todo o caixa possível, com quantidade derivada abaixo:

```text
preço de compra = primeira abertura * (1 + slippage)
quantidade ideal = C0 / (preço de compra * (1 + fee_rate))
quantidade efetiva = floor(quantidade ideal / 0.000000000001) * 0.000000000001
caixa residual = C0 - quantidade efetiva * preço de compra * (1 + fee_rate)
```

Calcular a divisão e o piso com razões/inteiros exatos; nunca arredondar para cima e deixar caixa negativo. O quantum `1e-12 BTC` é uma hipótese numérica do benchmark, não regra histórica de exchange. Registrar quantum, quantidade e resíduo. Quantidade ideal é memória de cálculo racional, não saldo financeiro arredondado silenciosamente.

Se o piso resultar em zero, o benchmark fica indisponível com `BENCHMARK_SIZE_BELOW_QUANTUM`, sem ordem, taxa ou falsa equivalência com manter caixa. Erro técnico/aritmético não pode ser convertido nesse motivo de política.

O benchmark tem ledger próprio de inicialização/compra e curva nos eventos de abertura/fechamento, incluindo ponto de fill da entrada passiva. Custos da entrada afetam o patrimônio imediatamente. Não vende ao final: reporta patrimônio bruto e liquidação hipotética, igual à política da estratégia. Não cobrar taxa de saída como paga se não houve venda.

Reutilizar as funções de custo e transição financeira do ledger para a entrada passiva. Sua autorização anterior ao replay não remove a exigência de fase de fechamento das submissões manuais/SMA; um adaptador de benchmark deve registrar essa origem explícita.

Comparar retornos sob a mesma convenção de patrimônio e mesma cobertura temporal. Se exibir diferença entre retornos, usar **pontos percentuais** e identificar o benchmark. A estratégia usa quantidade fixa e pode ficar parcialmente em caixa; comprar/manter usa quase todo o capital, portanto as exposições diferem e devem aparecer no relatório. Não esconder a diferença nem tratar o teste curto como ranking de investimento.

## 8. Fixtures e cálculos obrigatórios

### 8.1. Exemplo principal, compatível com a Sprint 06

Criar `data/fixtures/sprint08-candles.json`, envelope `schema_version: 1` e `candles`. Todos os candles têm `source: FICTICIA`, `symbol: BTCUSDT`, `interval: 1m`, `volume: "1"`, `is_closed: true`; data **2026-01-01**, horários com `+00:00`, valores OHLC em strings JSON.

| Candle | Abertura UTC | Fim UTC | open | high | low | close |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 12:00 | 12:01 | 100000 | 100000 | 100000 | 100000 |
| 2 | 12:01 | 12:02 | 100000 | 101000 | 100000 | 101000 |
| 3 | 12:02 | 12:03 | 101000 | 101000 | 101000 | 101000 |

Criar `experiments/sprint08-manual.json`:

```json
{
  "schema_version": 1,
  "source": "FICTICIA",
  "symbol": "BTCUSDT",
  "interval": "1m",
  "initial_cash": "1000",
  "quantity": "0.001",
  "fee_rate": "0.001",
  "slippage_rate": "0",
  "orders": [
    {"id": "compra-01", "at_close": "2026-01-01T12:01:00+00:00", "side": "BUY"},
    {"id": "venda-01", "at_close": "2026-01-01T12:02:00+00:00", "side": "SELL"}
  ]
}
```

Ledger da estratégia: inicialização com caixa 1000; compra com `cash_delta: -100.1`, `asset_delta: 0.001`, taxa `0.1`, base `100.1`; venda com `cash_delta: 100.899`, `asset_delta: -0.001`, taxa `0.101`, base zero. São três entradas, taxas `0.201` e resultado realizado `0.799 USDT`.

| Ponto | Horário UTC | Caixa USDT | BTC | Marca USDT/BTC | Patrimônio USDT | Realizado USDT | Não realizado USDT |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Inicial | 12:00 | 1000 | 0 | Indisponível | 1000 | 0 | 0 |
| OPEN 1 / CLOSE 1 / OPEN 2 antes da compra | 12:00 / 12:01 / 12:01 | 1000 | 0 | 100000 | 1000 | 0 | 0 |
| Após BUY | 12:01 | 899.9 | 0.001 | 100000 | 999.9 | 0 | -0.1 |
| CLOSE 2 / OPEN 3 antes da venda | 12:02 | 899.9 | 0.001 | 101000 | 1000.9 | 0 | 0.9 |
| Após SELL / CLOSE 3 | 12:02 / 12:03 | 1000.799 | 0 | 101000 | 1000.799 | 0.799 | 0 |

Linhas agrupadas representam pontos distintos, totalizando **9 pontos** na curva da estratégia. No vale após a compra, `1000 + 0 - 0.1 = 999.9`. Depois da venda, `1000 + 0.799 + 0 = 1000.799`.

Valores obrigatórios:

- Retorno da carteira: `0.799 / 1000 * 100 = 0.0799%`.
- Retorno do trade: `0.799 / 100.1 * 100`, razão exata `799/1001` em %, apresentação `0.798201798202%`.
- Uma operação encerrada, um ganho, nenhuma perda/empate; acerto 100%; expectativa `0.799 USDT/TRADE`.
- Horizonte 180 s; posição de 12:01 a 12:02, 60 s, exposição `33.333333333333%`.
- Máximo drawdown: queda `0.101 USDT` do pico `1000.9` após a taxa de venda; razão exata `101/10009` em %, apresentação `0.010090918174%`.
- A primeira queda de `0.1 USDT` dura 60 s até recuperar. A queda final dura 60 s observados e não recupera; maior duração observada 60 s. O vale da queda final ocorre no mesmo timestamp de seu pico, mas em sequência posterior.
- HOLD_USDT termina com `1000 USDT`, retorno zero. BUY_HOLD_BTC compra `0.009990009990 BTC`, paga taxa `0.999000999 USDT`, mantém caixa residual `0.000000001 USDT`, termina com patrimônio bruto `1008.991008991 USDT` e liquidação hipotética `1007.98201798201 USDT`.

### 8.2. Variantes obrigatórias

Criar as variantes em testes com dados/configurações locais ou temporários, sem editar a fixture principal:

1. **Roteiro vazio:** caixa/patrimônio 1000, resultado realizado/não realizado zero, zero custos/exposição/drawdown. Acerto e expectativa `null/NO_CLOSED_TRADES`. Benchmarks continuam sendo simulados independentemente.
2. **Compra aberta:** usar somente candles 1 e 2 e somente a compra. Caixa `899.9`, BTC `0.001`, base `100.1`, realizado zero, não realizado `0.9`, patrimônio bruto `1000.9` e liquidação hipotética `1000.799`. Taxa paga `0.1`, taxa hipotética `0.101`, nenhum trade encerrado, 60 s em posição sobre horizonte de 120 s. Nenhuma venda deve aparecer no ledger.
3. **SMA canônico:** fixture/configuração da Sprint 07, com oito candles. Caixa final `999.6`, BTC zero, realizado `-0.4`, taxas `0.2`, impacto de slippage `0.2`, perda única. No fill BUY, patrimônio marcado na abertura `999.7999` e não realizado `-0.2001`; usar preço efetivo como marca apagaria parte do custo e deve falhar no teste.
4. **SMA ampliado atual:** reutilizar os arquivos ampliados existentes, sem redesenhar preços para a análise. Três trades com `+0.73754871919`, `+0.77489849630` e `-0.61089654715 USDT`; realizado `0.90155066834`, caixa `1000.90155066834`, BTC zero, taxas `0.60339361166`, dois ganhos/uma perda. Expectativa `0.300516889447 USDT/TRADE`; acerto `66.666666666667%`; tempo em posição 6120 s sobre 14400 s, exposição 42.5%. Esses preços foram construídos para demonstração visual; não são evidência de desempenho.
5. **Empate e divisão periódica:** no componente de métricas, lucros `[2, -1, 0] USDT` produzem ganho/perda/empate iguais a 1, acerto `33.333333333333%` e expectativa `0.333333333333 USDT/TRADE`, com razões exatas preservadas. Não arredondar lucro antes da classificação.
6. **Drawdown manual:** valores patrimoniais `[1000, 1100, 990, 1050, 1100, 1080]`, um por minuto desde 12:00, produzem máximo de 10%/110 USDT, episódio de 12:01 a 12:04 com duração 180 s e recuperação, seguido de episódio aberto de 60 s. Uma curva constante produz zero, sem inventar pico/vale de episódio inexistente.
7. **Rejeição, última ordem e lacuna:** nenhuma taxa ou entrada financeira para ordem não preenchida; sinal final conserva `NO_FUTURE_OPEN`; lacuna SMA mantém ledger/pendência e todas as curvas no prefixo aceito, sem candle ou benchmark posterior.

## 9. Entregáveis, CLI e exportações

Evoluir módulos existentes e criar somente os necessários, por exemplo `ledger.py`, `metrics.py`, `benchmarks.py` e `tests/test_sprint08.py`. Manter o motor único e a separação entre cálculo financeiro e apresentação. Entregar fixtures/configuração da seção 8.1, README atualizado, `docs/sprint08-validacao.md` e `docs/sprint08-glossario.md`.

O glossário deve explicar ledger, base de custo, realizado/não realizado, patrimônio bruto, liquidação hipotética, curva, pico/vale/recuperação, drawdown, expectativa, exposição, benchmark e pontos percentuais. O roteiro de validação distingue esperado, observado, comandos não executados e pendências.

CLI prevista após implementar, na raiz e com `.venv` ativada:

```bash
source .venv/bin/activate
python --version
python -m replayquant --help
python -m replayquant demonstrar --formato json
python -m replayquant demonstrar --estrategia sma --formato json
python -m replayquant demonstrar --analise --formato texto
python -m replayquant demonstrar --analise --formato json
python -m replayquant demonstrar --analise --formato markdown
python -m replayquant demonstrar --estrategia sma --analise --formato html > /tmp/replayquant-sprint08.html
python -m unittest discover -s tests -v
```

`demonstrar --analise` reutiliza os dados manuais canônicos já existentes e confere os resultados da seção 8.1, numericamente iguais à nova fixture. O modo SMA confere também o realizado negativo, custos e marcação inicial da variante 8.2.3. `demonstrar` não grava diretório de artefatos. Divergência obrigatória é falha, nunca sucesso por atingir lucro.

Adicionar `markdown` a `--formato`, exigindo `--analise` para esse novo formato. Sem a flag, recusá-lo antes do replay com código 2 de sintaxe/combinação inválida. `texto`, `json` e `html` conservam sua disponibilidade anterior. Não adicionar comandos de pesquisa/comparação de estratégias nesta etapa.

### 9.1. Arquivos persistidos

Com `executar --analise`, criar exatamente os nove arquivos abaixo em diretório novo. Preservar política de não sobrescrita, escrita temporária, manifesto por último e marcador `INCOMPLETE` até concluir. Validar entradas antes de criar a saída. Falha de escrita deve ser técnica, sem representar execução persistida com sucesso.

| Arquivo | Conteúdo |
| --- | --- |
| `manifest.json` | Identidade, hashes, versões, políticas e cobertura |
| `events.jsonl` | Eventos do replay, preservando causalidade e referências |
| `report.json` | Relatório schema 3, campos legados e objeto `analysis` |
| `ledger.jsonl` | Entradas das três carteiras com identificação explícita |
| `equity.csv` | Curvas da estratégia e referências, identificadas por carteira |
| `trades.csv` | Trades encerrados da estratégia, sem posição aberta fictícia |
| `metrics.csv` | Métricas da estratégia, unidades, razões e motivos |
| `benchmarks.csv` | Resumo comparável das duas referências |
| `report.md` | Relatório completo em português, fórmulas e memória de cálculo |

Em `analysis`, incluir `policy_version`, `scope`, `position_at_end`, `observation_start`, `observed_until`, `metrics`, `equity_curve`, `closed_trades`, `open_position`, `drawdown_episodes`, `max_drawdown_episode`, `longest_drawdown_episode`, `benchmarks`, `reconciliation` e `rounding_policy`. `policy_version` é `SPRINT08_V1`; `position_at_end` é `KEEP_OPEN`; `scope` é `FULL_RUN` ou `ACCEPTED_PREFIX`. O relatório enriquecido tem `status: COMPLETED|INTERRUPTED`, inclusive no modo manual. `reconciliation` registra deltas reconstruídos, saldos, base de custo e igualdade patrimonial; divergência é erro, não apenas um aviso impresso.

O relatório deve incluir as entradas do ledger ou referências suficientes para reconstruí-las a partir de seus dados e fills, permitindo renderizar os formatos de apresentação sem reler arquivos de mercado. Benchmarks incluem status/motivo, mesma cobertura, parâmetros de entrada, curvas, saldos e métricas, sem misturar execuções passivas com ordens da estratégia.

CSV UTF-8, separador vírgula, ponto decimal, aspas pelo módulo `csv`, terminador `\n`, cabeçalhos fixos e sem índice de DataFrame. Datas UTC canônicas. Valores indefinidos usam célula vazia e coluna de motivo, nunca texto `NaN` ou zero substituto. Arquivo sem trades contém cabeçalho e nenhuma linha de dados. Documentar a ordem completa dos cabeçalhos no README e nos testes.

Contratos mínimos de colunas, nesta ordem; o implementador não deve acrescentar colunas sem registrar a evolução:

```text
equity.csv:
schema_version,run_id,portfolio,point_seq,at,source_event_seq,phase,cash_total,cash_available,cash_reserved,asset_quantity,mark_price,mark_at,mark_reason,cost_basis,realized_pnl,unrealized_pnl,gross_equity,hypothetical_liquidation_equity

trades.csv:
schema_version,run_id,trade_id,lot_id,buy_execution_id,sell_execution_id,buy_at,sell_at,quantity,buy_price,sell_price,buy_gross,sell_gross,buy_fee,sell_fee,cash_outflow,cash_inflow,net_pnl,return_pct,return_numerator,return_denominator,duration_seconds,classification

metrics.csv:
schema_version,run_id,scope,metric,value,unit,reason,numerator,denominator

benchmarks.csv:
schema_version,run_id,portfolio,status,reason,observation_start,observed_until,initial_cash,final_cash,asset_quantity,paid_fees,gross_equity,hypothetical_liquidation_equity,return_pct,return_reason,hypothetical_return_pct,hypothetical_return_reason,time_in_position_seconds,time_in_position_pct
```

Campos adicionais de trades e episódios de drawdown permanecem no JSON. Métricas CSV são uma linha por métrica escalar; detalhes de episódios ficam no JSON/Markdown. Ordenar carteiras `STRATEGY`, `HOLD_USDT`, `BUY_HOLD_BTC`; curvas por `point_seq`, trades pela sequência de saída e métricas por nome. No ledger JSONL, ordenar cronologicamente por `(at, source_event_seq, ordem da carteira, ledger_seq)`; `ledger_seq` é local à carteira. Todas as entradas incluem schema/run_id.

### 9.2. Apresentação e códigos

Texto/Markdown/HTML mostram caixa, patrimônio bruto, liquidação hipotética, realizado/não realizado, custos, retornos, drawdown/durações, exposição e comparação com as duas referências. Exibir fórmulas, dados de entrada, unidades e limites da amostra. JSON stdout contém somente relatório; diagnósticos continuam em stderr.

Preservar o gráfico de candles SMA e seus marcadores. Acrescentar ao HTML enriquecido uma curva patrimonial temporal da estratégia e dos benchmarks, com rótulos de carteira e a mesma convenção de patrimônio. Usar dados calculados no Python, sem recalcular ledger/métricas em JavaScript. Reutilizar a biblioteca incorporada e os avisos de licença; não atualizar o bundle nem buscar CDN. A conversão numérica para desenho não pode alterar strings exatas nas tabelas. Prever alternativa textual sem JavaScript, responsividade, escape e captura para impressão.

Não exibir curva suavizada ou high/low intraperíodo que não integra a amostragem. Pontos com mesmo timestamp precisam preservar sua sequência: não sobrescrever a perda de taxa ou inventar timestamps para a biblioteca. Usar representação compatível com eventos ordenados (por exemplo, eixo por índice e tooltip UTC), explicitando essa escolha. Benchmarks com amostras diferentes podem usar painéis/eixos de índice próprios; comparações numéricas continuam limitadas às mesmas datas. Não selecionar apenas o último ponto do minuto e chamar esse gráfico de curva integral usada no drawdown.

| Código | Com análise |
| --- | --- |
| 0 | Replay e análise concluídos sem bloqueios/rejeições/ordens não executadas; ausência de trades não é erro |
| 1 | Dados/configuração inválidos, falha técnica/aritmética, falha de reconciliação ou interrupção por lacuna com análise parcial identificada |
| 2 | Replay concluído com bloqueio por política, ordem rejeitada ou não executada; análise preservada |

Métrica indefinida por ausência de trades não muda código 0 para erro. `argparse` conserva código 2 para sintaxe/combinações inválidas. Rejeição de ordem esperada não pode encobrir falha do ledger ou cálculo inesperado.

### 9.3. Reprodução de arquivos

Executar na mesma sessão Bash, após implementar, escolhendo saída nova:

```bash
validacao_sprint08_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint08-candles.json --config experiments/sprint08-manual.json --analise --saida "$validacao_sprint08_dir/execucao-a" --formato json
python -m replayquant executar --dados data/fixtures/sprint08-candles.json --config experiments/sprint08-manual.json --analise --saida "$validacao_sprint08_dir/execucao-b" --formato json
for arquivo in manifest.json events.jsonl report.json ledger.jsonl equity.csv trades.csv metrics.csv benchmarks.csv report.md; do
  cmp "$validacao_sprint08_dir/execucao-a/$arquivo" "$validacao_sprint08_dir/execucao-b/$arquivo" || exit 1
done
python -m replayquant executar --dados data/fixtures/sprint07-candles-expandido.json --config experiments/sprint07-sma-expandido.json --analise --saida "$validacao_sprint08_dir/sma-ampliado" --formato html > "$validacao_sprint08_dir/sma-ampliado.html"
git diff --check
```

Todos os comandos principais e cada comparação devem retornar 0. Registrar individualmente os códigos observados; não inferir sucesso dos anteriores pelo último. Casos negativos 1/2 são conferidos pela suíte. Redirecionar HTML fora de `--saida`, pois o shell cria o arquivo antes do programa. Nenhum comando deve apagar saídas para forçar repetição.

## 10. Verificação e critérios de aceite

Implementar testes de comportamento com `unittest`, cobrindo pelo menos:

1. Exemplo principal: três entradas de ledger, nove pontos patrimoniais, saldos, taxas, resultado, retornos, drawdown/duração e exposição da seção 8.1, todos conferidos independentemente.
2. Reconstrução dos saldos a partir do ledger e `E = C0 + R + U` em cada ponto. Marcação sem movimento financeiro, taxa debitada uma vez, custo zerado somente ao fechar a posição e caixa/ativos não negativos.
3. Múltiplos trades, posição aberta, roteiro vazio, ganho/perda/empate e expectativa periódica da seção 8.2; limites e motivos corretos. Preservar `round_trip_result` legado.
4. Patrimônio bruto diferente da liquidação hipotética, taxa hipotética separada de paga, ausência de venda no encerramento e posição aberta fora dos trades encerrados.
5. Quedas de custo em eventos do mesmo timestamp; drawdown exato, episódios recuperados/não recuperados, picos iguais, empates de magnitude/duração e casos em que maior duração e maior percentual pertencem a episódios diferentes.
6. Tempo de exposição pelos fills, não pelos sinais; posição aberta até o fim, aquecimento no horizonte e zero duração sem divisão inválida.
7. Benchmarks isolados com mesmo capital/datas/custos, compra passiva na primeira abertura, quantidade arredondada para baixo por razão exata, resíduo não negativo e falta de quantidade mínima com motivo explícito. HOLD_USDT sem juros, trades ou taxas.
8. Causalidade: alterar sufixo preserva ledger, trades e pontos anteriores; modificar fechamento futuro preserva marca/fill da abertura. IDs/hashes globais e finalização de prefixo podem diferir; não comparar resumos finais de horizontes diferentes como se fossem prefixos.
9. Rejeição, pendência final, idempotência de fill/ledger, conflito de ID e falhas aritméticas sem mutação parcial. API incremental e replay de arquivo devem produzir os mesmos movimentos e resultados lógicos.
10. Lacuna: carteira e pendência preservadas, análise/benchmarks só no prefixo, status parcial, código 1 e nenhuma marca/fill posterior. Preservar pré-validação de lacunas do modo manual.
11. Contextos decimais adversos, JSON inválido, tipos/API, horários e séries de curva inválidos; razões exatas/valores arredondados não contaminam saldo ou classificação. Não aceitar bool como duração/contagem.
12. CLI e API com/sem análise, schemas antigos preservados, flag incluída no `run_id`, nove arquivos válidos, CSV/Markdown determinísticos, ausência com motivo, não sobrescrita e falha de escrita com saída incompleta identificada.
13. Reprodução byte a byte dos nove arquivos em diretórios distintos; revisão dos hashes incluindo assets e política de análise. Sem dependência de rede, data real, caminho absoluto ou laboratórios vizinhos.
14. HTML enriquecido responsivo, alternativa sem JavaScript, valores exatos nas tabelas, escape de conteúdo, gráfico com eventos de mesmo timestamp preservados e nenhuma requisição externa. Reexecutar regressões dos modos manual, SMA e Lightweight Charts; inspecionar o HTML em desktop/tela estreita e sua captura de impressão.

Aceite exige código e documentação completos, suíte relevante aprovada, reconciliação exata, exemplos conferidos, exportações reproduzíveis e limitações explícitas. Não condicionar conclusão técnica a lucro. Não declarar testes ou comandos não executados como aprovados.

## 11. Prompt autossuficiente de execução

Copie o bloco inteiro para um agente com acesso ao repositório. As referências são documentos versionados; não é necessário consultar a conversa original.

````text
Implemente a Sprint 08 — Ledger, métricas e referências do ReplayQuant.

CONTEXTO, DIRETÓRIO E PRÉ-REQUISITOS
Trabalhe em /home/cams7/Dev/Cripto_Tests/replayquant, evoluindo o projeto existente.
Inspecione git status, instruções AGENTS.md aplicáveis, código e testes. Leia
integralmente docs/sprint08.md (seções 1 a 10), docs/planejamento.md e os contratos
das Sprints 06/07 e seus registros de validação. Execute a suíte existente em
.venv para confirmar o ponto de partida. Preserve trabalho alheio. Se faltar um
pré-requisito essencial, registre a lacuna antes do trabalho dependente; não
recrie o projeto nem suponha sucesso com base apenas em documentação anterior.

OBJETIVO E ESCOPO
Implemente, teste e documente ledger auditável, reconstrução de saldos, trades,
patrimônio bruto, liquidação hipotética, realizado/não realizado, métricas e
benchmarks comparáveis. Não entregue somente proposta. Use Python >= 3.11,
referência 3.12.14, biblioteca padrão e unittest. Reutilize o Lightweight Charts
5.2.0 já incorporado; não instale pacotes, atualize o bundle ou use rede. Não
importe laboratórios vizinhos. Não antecipe reservas, risco, stops, parciais,
múltiplos lotes/pares, capital compartilhado, dados reais, otimização, anualização,
Sharpe, banco, web hospedada, AWS ou negociação real. Não redesenhe fixtures para
obter lucro. Preserve sinais, preços, taxas e fases de execução anteriores.

ENTRADAS, COMPATIBILIDADE E IDENTIDADE
Siga exatamente a seção 3: --analise opt-in em demonstrar/executar, schemas de
entrada preservados, saída enriquecida schema 3 e versões anteriores sem a flag.
Valide a opção também na API. Preserve os formatos atuais e acrescente markdown
somente com --analise. A identidade enriquecida inclui analysis_policy
SPRINT08_V1 no JSON canônico, além dos hashes e Python existentes; sem análise
preserve a identidade anterior. Inclua todos os assets no hash de código conforme
a implementação atual, sem hora real ou caminho de saída na identidade.

ARITMÉTICA E LEDGER
Preserve JSON estrito, limites de entrada, datas UTC e validação pela API.
Contabilidade usa Decimal, contexto local precisão 40/ROUND_HALF_EVEN e erro em
aritmética inexata antes de mutar. Razões de métricas usam numerador/denominador
exatos; apresentação com 12 casas HALF_EVEN, fora da contabilidade. Não use float
financeiro ou valores arredondados para classificar ganho/perda/drawdown.
Implemente os campos e invariantes de ledger da seção 4. INITIAL_BALANCE registra
capital inicial; cada FILL aceito registra de uma vez deltas de caixa e BTC,
taxa, referências e saldos posteriores. Ledger e estado financeiro são efetivados
atomicamente e reconciliáveis; não gere ledger decorativo a partir de saldo sem
origem auditável. Rejeições/sinais/ordens não preenchidas não movem dinheiro.
Duplicata idêntica é inócua; conflito falha sem mutação aceita.

Uma compra abre lote com custo bruto+taxa; venda integral fecha esse lote com
realizado = recebimento líquido - custo. Registre trades com referências,
retornos/duração/classificação e posição aberta separada. Mantenha o campo legado
round_trip_result para exatamente uma ida e volta aplicável; novos campos
suportam múltiplas operações sem reinterpretá-lo.

CURVA, ENCERRAMENTO E MÉTRICAS
Siga as seções 5 e 6. Amostre INITIAL, cada OPEN antes de fill, cada FILLED após
fill usando open de referência como marca, e cada CLOSE disponível. Preserve
timestamp/seq; não exponha OHLCV futuro. Patrimônio = caixa + BTC*marca; não
realizado = BTC*marca - custo aberto; reconcilie E = capital + realizado + não
realizado em cada ponto. Reservas são zero nesta sprint e caixa total não pode
ser contado duas vezes.
KEEP_OPEN é a política obrigatória. Calcule liquidação hipotética com slippage
e taxa de venda, sem criar fill, cobrar taxa no ledger ou zerar posição. O retorno
da carteira usa patrimônio bruto marcado; cenário líquido é separado. Exponha
taxas pagas, impacto de slippage e decomposição de custos sem novo desconto.

Implemente retorno patrimonial e por trade com denominadores distintos, número
de trades encerrados, ganhos/perdas/empates, acerto, expectativa em USDT/TRADE,
drawdown absoluto/percentual e durações, tempo e percentual em posição. Sem
trades, acerto/expectativa são null/NO_CLOSED_TRADES; retorno/drawdown zero podem
ser válidos. Preserve motivos e unidades definidos no documento.
Drawdown usa toda a curva, inclusive custos em fills. Pico, vale, recuperação,
episódio não recuperado, desempates e maior duração seguem a seção 6.2; não
confunda a duração máxima com o episódio de maior queda percentual. Integre
exposição entre fills, incluindo posição aberta até o fim, sobre todo o horizonte.
Não anualize ou invente evidência de investimento.

BENCHMARKS E LACUNAS
Implemente HOLD_USDT e BUY_HOLD_BTC em carteiras isoladas, com mesmo capital,
moeda e período aceito. Caixa não rende juros. Comprar/manter compra na primeira
abertura com mesmos custos, quantidade calculada por razões exatas e piso no
quantum 0.000000000001 BTC, resíduo não negativo e motivo quando o piso é zero.
Essa escala é hipótese numérica, não regra de exchange. Não vende no fim; informe
patrimônio bruto e liquidação hipotética, diferenças de exposição e comparação
em pontos percentuais quando pertinente. Não some as três carteiras.
Lacuna SMA interrompe antes do evento posterior, preservando ledger/pendência.
A análise e referências param no mesmo prefixo, scope ACCEPTED_PREFIX e código 1.
Não finalize a pendência como NO_FUTURE_OPEN ou reconstrua operações. Mantenha a
recusa prévia de lacunas no modo manual.

EXEMPLOS OBRIGATÓRIOS
Crie data/fixtures/sprint08-candles.json e experiments/sprint08-manual.json com os
dados completos da seção 8.1. Capital 1000, quantidade 0.001 BTC, taxa 0.001,
slippage zero; compra a 100000 e venda a 101000. Ledger: inicial 1000, compra
-100.1/+0.001 BTC, venda +100.899/-0.001 BTC. Resultado 0.799, taxas 0.201, caixa
1000.799, BTC zero. Curva da estratégia tem 9 pontos; após compra patrimônio
999.9, antes da venda 1000.9, depois 1000.799. Retorno da carteira 0.0799%, trade
0.798201798202%, drawdown máximo 0.010090918174% (0.101/1000.9*100), maior duração
60 s, tempo em posição 60/180 s. BUY_HOLD_BTC compra 0.009990009990 BTC, caixa
residual 0.000000001, patrimônio bruto final 1008.991008991 e liquidação hipotética
1007.98201798201 USDT. Confira tudo independentemente com aritmética exata.

Implemente todas as variantes da seção 8.2: roteiro vazio; compra aberta com
patrimônio 1000.9, não realizado 0.9 e liquidação hipotética 1000.799; SMA canônico
com realizado -0.4 e patrimônio 999.7999 no fill BUY; SMA ampliado já versionado
com três trades, realizado 0.90155066834 e posição zero. Confira empate,
expectativa periódica, drawdown manual, rejeições, ordem final e lacuna. Não
altere dados/esperados para acomodar defeitos ou evidenciar rentabilidade.

CLI, ARTEFATOS E APRESENTAÇÃO
Implemente exatamente a seção 9: --analise nos comandos atuais, saída nova sem
sobrescrita e nove arquivos: manifest.json, events.jsonl, report.json,
ledger.jsonl, equity.csv, trades.csv, metrics.csv, benchmarks.csv, report.md.
JSON financeiro em strings; CSV UTF-8/vírgula/ponto decimal/linhas LF, cabeçalhos
e ordenação fixados na seção 9.1; null com motivo, CSV sem trades só com cabeçalho.
Preserve marcador INCOMPLETE e falhas de escrita como técnicas. JSON stdout é
somente relatório; diagnósticos em stderr. Códigos 0/1/2 seguem seção 9.2;
ausência de trades não é falha de análise.
Amplie texto, Markdown e HTML com reconciliação, fórmulas, métricas e benchmarks.
Mantenha candles/marcadores e acrescente curva patrimonial com dados calculados
no Python, biblioteca/avisos incorporados, sem requisições externas. Não apague
pontos de mesmo timestamp nem invente horários: use eixo por sequência ou outra
representação fiel, declarando a convenção. Preserve valores exatos nas tabelas,
responsividade, escape, alternativa sem JavaScript e captura de impressão.

TESTES, COMANDOS E ENTREGA
Implemente todos os casos da seção 10 com unittest, incluindo atomicidade,
reconstrução independente, prefixo causal, métricas manuais, benchmarks, lacunas,
contexto decimal adverso, CLI/API, versões antigas, nove arquivos e reprodução.
Execute as regressões existentes; corrija falhas sem alterar hipóteses financeiras.
Na raiz, ative .venv, confira Python real e execute todos os comandos das seções
9 e 9.3: ajuda, demonstrações antigas, demonstração enriquecida texto/JSON/Markdown,
HTML SMA, unittest discover, duas execuções novas com os nove cmp, SMA ampliado
enriquecido e git diff --check. Inspecione HTML em desktop/tela estreita e captura
de impressão. Registre cada código observado; cenários negativos são conferidos
pela suíte. Falta do Python de referência não autoriza inventar resultado ou
alterar o sistema silenciosamente.

Entregue código, testes, fixtures/configuração, README atualizado,
docs/sprint08-validacao.md e docs/sprint08-glossario.md em português. A validação
separa esperado, observado, não executado e pendências, com versões e limitações.
Não faça commit, publicação ou alterações externas. Na resposta final informe
arquivos alterados, comandos realmente executados, resultados e limitações.
Não declare a sprint concluída se faltar requisito obrigatório de implementação
ou verificação; lucro não é critério de conclusão técnica.
````
