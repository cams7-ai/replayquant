# Sprint 09 — Risco e saídas protetivas

**Projeto:** ReplayQuant  
**Nível:** intermediário  
**Referência:** [Planejamento](planejamento.md), especialmente seções 4, 9, 21 e 23  
**Pré-requisitos:** [Sprint 06](sprint06.md), [Sprint 07](sprint07.md) e [Sprint 08](sprint08.md), com seus registros de validação  
**Estado:** especificação preservada como referência; implementação e verificações registradas em [sprint09-validacao.md](sprint09-validacao.md).

## 1. Objetivo e ponto de partida

Dimensionar uma compra pelo risco planejado, caixa disponível e exposição permitida; reservar recursos de ordens pendentes e simular stop/alvo sem prometer preço ou perda máxima garantidos. O estudante deverá explicar a diferença entre aprovação, reserva, ordem e preenchimento, reconstruir cada liberação e identificar por que a perda efetiva pode superar o orçamento.

Trabalhar em `/home/cams7/Dev/Cripto_Tests/replayquant`, evoluindo o projeto existente. Inspecionar `git status`, instruções `AGENTS.md` aplicáveis, código, testes e contratos anteriores. Conferir a suíte de entrada na `.venv`; os registros de validação anteriores não substituem essa verificação. A referência consultada para esta especificação é o commit `6cc6a37`, da Sprint 08; não exigir esse HEAD exato, nem descartar alterações posteriores. Se faltar pré-requisito essencial, registrar a lacuna antes do trabalho dependente.

O projeto já possui modo manual/SMA, slippage adverso, execução causal por abertura, ledger imutável, trades, métricas, benchmarks, exportações e HTML com Lightweight Charts incorporado. Esses componentes serão ampliados; não criar outro motor financeiro para o risco. RiskGate serve como referência de conceitos e cálculos, sem importação ou dependência do projeto vizinho.

## 2. Escopo e exclusões

Implementar dimensionamento, filtros fictícios de quantidade/nocional, avaliação causal de risco, reservas em USDT/BTC, cancelamento de pendências, bloqueios diário/drawdown e saídas protetivas simplificadas com resolução OHLC. Integrar tudo ao ledger, curva, métricas, manifesto e apresentação.

Manter apenas `FICTICIA/BTCUSDT/1m`, posição comprada única, uma entrada/saída comum pendente por vez e preenchimentos totais. A quantidade passa a ser calculada por entrada e preservada até a saída integral do lote. Reutilizar SMA_CROSS, sem introduzir EMA, RSI ou catálogo multipar. Taxa única em USDT nas duas pontas e slippage percentual adverso continuam configuráveis.

Python >= 3.11, referência 3.12.14, biblioteca padrão e `unittest`. Não instalar pacotes, atualizar assets ou depender de rede. Preservar bundle, licenças, escape, visualização offline e alternativa sem JavaScript.

Ficam fora: limitadas, stop-limit, fila, livro, preenchimentos parciais, latência positiva, execução detalhada da Sprint 17, pirâmide de posições, trailing stop, venda descoberta, derivativos, múltiplos instrumentos/estratégias, capital compartilhado, depósitos/retiradas, reativação operacional após reinício, banco, dados reais, otimização, anualização, infraestrutura externa e ordens reais. Stop/alvo são convenções fictícias, não emulação integral de uma exchange.

## 3. Compatibilidade, schemas e configuração

### 3.1. Ativação e identidade

Criar configuração **schema 4**, distinguindo `mode: MANUAL|SMA`, com risco obrigatório. Os schemas manuais 1 e SMA 2 continuam com o comportamento anterior; `--analise` continua gerando saída schema 3 nesses modos. Não acrescentar reservas, stops ou quantidade variável silenciosamente às configurações antigas.

Configuração schema 4 sempre ativa análise e saída schema 4: manifesto, eventos, ledger, relatório e exportações. `--analise` pode ser informado de forma redundante, sem mudar identidade ou resultados desse modo. Na API, a configuração de risco implica a mesma análise obrigatória; validar tipos de opções e impedir combinação que desative essa análise.

Acrescentar à identidade canônica já existente `risk_policy: "SPRINT09_V1"` e `analysis_policy: "SPRINT09_V1"` no modo novo. Preservar hashes de bytes de dados/configuração, lista ordenada de código/assets, Python real e ausência de hora real/caminho de saída. Registrar também versões de configuração, regras de risco, reserva, proteção e benchmark. Sem schema 4, manter as definições anteriores da identidade. Não afirmar igualdade dos hashes antigos após alterar o código; preservar seu algoritmo e semântica.

### 3.2. Configuração manual canônica

Criar futuramente `experiments/sprint09-manual.json` com exatamente:

```json
{
  "schema_version": 4,
  "mode": "MANUAL",
  "source": "FICTICIA",
  "symbol": "BTCUSDT",
  "interval": "1m",
  "initial_cash": "1000",
  "fee_rate": "0.001",
  "slippage_rate": "0",
  "instrument_filters": {
    "step": "0.000001",
    "min_quantity": "0.000001",
    "min_notional": "0"
  },
  "risk": {
    "risk_fraction": "0.01",
    "exposure_fraction": "1",
    "stop_fraction": "0.1",
    "target_fraction": "0.2",
    "daily_loss_fraction": "0.03",
    "drawdown_fraction": "0.05",
    "max_price_age_seconds": "60"
  },
  "orders": [
    {"id": "entrada-01", "at_close": "2026-01-01T12:01:00+00:00", "side": "BUY"}
  ]
}
```

As chaves da raiz são exatamente as exibidas. Não incluir `quantity`: ela será derivada por ordem. Para `mode: SMA`, substituir somente `orders` por `strategy` com os campos existentes `name: SMA_CROSS`, `short_window`, `long_window`; não admitir ambos. A quantidade da venda é a posição integral, nunca um novo dimensionamento por risco. Conservar contratos de aquecimento, igualdade, sinais e idempotência da Sprint 07.

`instrument_filters` e `risk` têm exatamente as chaves exibidas. `step`, `min_quantity` > 0, `min_notional` >= 0. Frações de risco, exposição, perda diária e drawdown em `(0, 1]`; `stop_fraction` em `(0, 1)`; `target_fraction` em `(0, 1]`; idade máxima > 0 em segundos. `fee_rate`/`slippage_rate` em `[0, 1)`. Valores financeiros e segundos de configuração são strings decimais sob as regras de entrada existentes; booleanos não são números. Regras são fictícias, sem identificação como filtros históricos de exchange. Tick size e catálogo temporal de instrumentos ficam para evolução posterior.

Ordens manuais BUY/SELL mantêm `id`, `at_close`, `side` e ordem cronológica explícita. Acrescentar somente no schema 4 a variante de cancelamento com exatamente `id`, `at_close`, `side: CANCEL`, `target_order_id`. Alvo deve ser uma ordem comum pendente; cancelamento não é fill. Processar ações no mesmo fechamento na ordem do arquivo, permitindo BUY seguido de CANCEL antes da abertura. Não permitir cancelar isoladamente o stop ou alvo pelo roteiro. ID de ação repetido com conteúdo normalizado idêntico é inócuo; conflito é erro. Datas devem corresponder a fechamentos presentes, como no modo manual existente.

### 3.3. Validação e precisão

Preservar JSON estrito, campos exatos, versões inteiras reais, UTC, `[início, fim)`, validação também na API e limites de representação de entrada. Contabilidade, reservas, preços e taxas usam `Decimal`, contexto local novo de precisão 40/ROUND_HALF_EVEN e erro em aritmética financeira inexata antes da mutação.

Razões de dimensionamento, contagem de incrementos e comparação com limites podem usar `Fraction` construída diretamente de `Decimal`. Não dividir com arredondamento para depois aplicar floor. Converter a quantidade final e valores financeiros para `Decimal` apenas se exatamente representáveis. Preservar numerador/denominador das razões de risco e métricas; apresentação periódica usa 12 casas HALF_EVEN, como na Sprint 08, sem decidir pela versão exibida.

## 4. Dimensionamento e revalidação

### 4.1. Snapshot causal e fórmulas

Na avaliação BUY, usar patrimônio bruto marcado `P`, caixa disponível `B`, exposição nominal atual marcada `X`, referência de mercado conhecida `m`, entrada efetiva estimada `E = m*(1+a)`, alíquota `f`, risco `r` e limite de exposição `x`. Não usar a abertura futura para aprovar a ordem no fechamento.

Definir preços absolutos de proteção no momento da aprovação:

```text
S = E * (1 - stop_fraction)       [USDT/BTC]
T = E * (1 + target_fraction)     [USDT/BTC]
R = P * r                        [USDT]
L = E * (1 + f) - S * (1 - f)     [USDT/BTC]
q_risco     = R / L               [BTC]
q_exposição = max(0, P*x - X) / E  [BTC]
q_saldo     = B / (E*(1+f))        [BTC]
q_bruta     = min(q_risco, q_exposição, q_saldo)
n           = floor(q_bruta / step)
q           = n * step
```

`S`, `T`, `R` e a quantidade aprovados ficam congelados na ordem. O orçamento planejado inclui as duas taxas, mas não o slippage de venda em S; explicitar essa limitação e mostrar separadamente a perda de cenário com slippage. Não redefinir o stop depois de conhecer a abertura para acomodar uma entrada que deixou de ser válida.

Recalcular desembolso, perda planejada e exposição após o piso. Reduzir incrementos se um limite financeiro ainda for excedido; nunca aumentar para cumprir mínimo. `q=0`, quantidade abaixo do mínimo ou `q*E < min_notional` recusam a entrada. Igualdade com mínimos e limites é válida. Registrar todos os limitadores ativos, inclusive empates. Exposição usa nocional sem taxa; caixa precisa cobrir a taxa.

### 4.2. Ordem de decisão e origem de preço

Validar estrutura e coerência do snapshot antes de políticas. Precedência BUY: bloqueio diário, bloqueio drawdown, preço ausente/futuro/desatualizado, pendência, posição aberta, vedação de reentrada no candle, patrimônio sem base positiva, exposição sem espaço, saldo zero, candidato/mínimos, aprovação. Apresentar todos os bloqueios patrimoniais ativos, mesmo que o motivo primário seja diário.

Preço futuro em relação ao evento avaliado é dado inválido; ausente ou com idade maior que o limite produz rejeição por política. Idade exatamente no limite é válida. Derivar idade do relógio simulado e do horário de disponibilidade da marca, não de `datetime.now()`. Preço carregado para marcação após interrupção não é dado negociável novo. O avaliador puro deverá permitir testar snapshots sem preço ou com idade excessiva, mesmo quando os arquivos canônicos liberam preço a cada evento.

Motivos estáveis mínimos: `DAILY_LOSS_BLOCKED`, `DRAWDOWN_BLOCKED`, `PRICE_MISSING`, `PRICE_STALE`, `ORDER_PENDING`, `POSITION_OPEN`, `REENTRY_SAME_CANDLE`, `NON_POSITIVE_EQUITY`, `EXPOSURE_LIMIT`, `INSUFFICIENT_CASH`, `BELOW_MINIMUMS`. Uma candidata recusada aparece separada da quantidade aprovada, que será zero. Cálculos não executados ficam nulos com motivo; não inventar quantidades.

SELL não passa pelo orçamento BUY, mínimos de nova compra ou bloqueios de entrada. Exige posição disponível e coordenação com a reserva do grupo protetivo. Rejeição de BUY não impede marcar a carteira, atualizar indicadores, acompanhar a posição ou solicitar saída integral.

### 4.3. Revalidação na abertura

Antes de preencher BUY, atualizar marca/patrimônio/bloqueios pela abertura disponível. Usar o preço efetivo da abertura, sem olhar o restante do candle. Revalidar idade, bloqueios, saldo, exposição, mínimos, `S < E_fill < T` e perda planejada `q*(E_fill*(1+f)-S*(1-f)) <= R` congelado. O limite de exposição usa o patrimônio marcado atual; o orçamento não aumenta se P subir.

A quantidade aceita não cresce nem é reduzida na abertura: caso qualquer condição falhe, rejeitar integralmente e liberar sua reserva, sem execução parcial. Usar `ENTRY_OUTSIDE_BRACKET` para relação inválida com stop/alvo e `RISK_BUDGET_EXCEEDED` para perda acima do orçamento. Aplicar primeiro bloqueios/preço/posição, depois bracket, orçamento, caixa, exposição e mínimos, registrando os valores efetivos. Não duplicar taxa/slippage: o custo usa o preço efetivo uma única vez.

## 5. Reservas, ledger e cancelamentos

### 5.1. Contas e atomicidade

Para caixa e BTC, distinguir total, disponível e reservado:

```text
cash_total = cash_available + cash_reserved
asset_total = asset_available + asset_reserved
patrimônio = cash_total + asset_total * marca
```

Aprovar risco puro não cria reserva. No motor, aceitação e reserva formam uma única transição lógica preparada/validada antes de efetivar. Compra pendente reserva `q*E*(1+f)` USDT. Criar reserva só transfere disponível para reservado: não é despesa, taxa ou redução do patrimônio. Ao preencher, consumir o desembolso da reserva; eventual diferença favorável retorna ao disponível. Se a abertura exigir complemento, pode usar somente caixa livre real, atomicamente e após todas as revalidações. Não usar reserva de outra ordem ou debitar taxa de ordem não executada.

A venda reserva BTC, sem retirar a posição do patrimônio. Stop e alvo pertencem a um único grupo de proteção que reserva a posição **uma vez**; não reservar q BTC para cada perna. Saída por sinal transfere a titularidade dessa mesma reserva para a ordem comum, mantendo a proteção até resolver a prioridade da abertura. Cancelar essa saída restaura a titularidade do grupo; nunca deixa a posição silenciosamente desprotegida.

Criar operações auditáveis `RESERVE`, `RELEASE` e `TRANSFER`, além de `INITIAL_BALANCE`/`FILL`. Evoluir o ledger schema 4 com os campos da Sprint 08 e acrescentar `reservation_id`, `reservation_owner_id`, `cash_available_delta`, `cash_reserved_delta`, `asset_available_delta`, `asset_reserved_delta` e os quatro saldos correspondentes após cada entrada. Quantidades reservadas e totais são não negativas. Transferência de titularidade pode ter deltas zero, mas identifica origem/destino no registro de reserva. Cada `source_event_seq` aponta para seu evento, IDs determinísticos e deduplicação incluem conteúdo completo.

Nos eventos não financeiros, `cash_delta=asset_delta=fee=gross=0`; não alterar base de custo ou realizado. No FILL, os deltas de disponível/reservado somam os deltas totais. Reserva e fill precisam ser reconstruíveis independentemente e reconciliados em cada prefixo, sem um saldo mutável com log decorativo. Preparar ledger, ordens, titularidade, taxas, proteção e estado antes do commit; falha aritmética não deixa efeitos parciais.

### 5.2. Liberação e término

Rejeição posterior à aceitação, cancelamento e término normal sem abertura futura liberam a reserva da ordem exatamente uma vez. Rejeitar uma solicitação concorrente não libera a reserva da ordem anterior. Nova ação CANCEL sobre alvo inexistente/terminal é recusada com `ORDER_NOT_PENDING`, sem desfazer preenchimentos anteriores; repetição idêntica da ação já aplicada é inócua. Adicionar estado `CANCELED`, somente no modo novo, com motivo `MANUAL_CANCEL` ou `PROTECTIVE_EXIT_PREEMPTED`.

No fim normal, pendência comum continua `UNEXECUTED/NO_FUTURE_OPEN`, com liberação. Posição aberta permanece KEEP_OPEN; encerrar o grupo como `ENDED_WITH_OPEN_POSITION` e liberar a reserva de BTC, sem vender ou lançar taxa hipotética. Preservar stop/alvo finais no relatório como histórico, sem alegar proteção ativa após o experimento.

Na interrupção SMA por lacuna, preservar posição, ordens e reservas do prefixo aceito: não chamar a finalização normal nem simular cancelamento/saída através do intervalo ausente. Relatório e referências usam `ACCEPTED_PREFIX`, com diagnóstico, reserva ainda retida e última marca identificada. Recuperação exige conjunto corrigido/versionado e nova execução, nunca reconstrução retroativa de ordens na sessão interrompida.

## 6. Bloqueios patrimoniais em tempo de execução

Atualizar o estado de risco dentro do núcleo quando uma marca ou fill é aceito; não calcular os bloqueios só no relatório após negociar. Usar os mesmos patrimônios auditáveis da curva, incluindo custos em fills, sem considerar saldo reservado como perda. Razões e comparações de limiar são exatas.

Primeira observação da sessão deve ser positiva para formar pico. Primeira observação positiva de cada dia UTC forma base diária `D`, com `daily_base_at` e indicação de base parcial se posterior à meia-noite. O dia muda às 00:00 UTC do relógio simulado. Sem aportes/retiradas:

```text
perda_diária_fracionária = max(0, (D - P) / D)
pico = max(pico anterior, P)
drawdown_fracionário = (pico - P) / pico
```

Atingir ou ultrapassar limite diário bloqueia novas entradas pelo restante do dia, mesmo após recuperação. Novo dia redefine somente a base e o bloqueio diário. Atingir limite de drawdown bloqueia até o fim da sessão, inclusive após recuperação, novo pico ou virada UTC. Não criar nova sessão no mesmo experimento para limpar bloqueios.

P=0 após início aciona ambos os bloqueios; drawdown=100%. Se um dia começar em zero, base/perda diária ficam nulas com `NO_POSITIVE_DAILY_BASE`; observação positiva posterior cria a base sem limpar o bloqueio diário já acionado. Não dividir por zero nem zerar artificialmente valor de posição sem preço.

Registrar observações por `(at, source_event_seq, phase)` e ordem lógica: dois estados diferentes no mesmo timestamp, por exemplo antes/depois de uma taxa, são válidos. Repetição idêntica da mesma chave é inócua; conflito ou regressão temporal é erro sem mutação. Isso amplia o contrato didático por timestamp do RiskGate para o relógio de eventos do ReplayQuant.

## 7. Stop, alvo e ordem dos eventos

### 7.1. Proteção do lote

Após BUY, vincular um grupo ao lote e à quantidade preenchida, com S/T absolutos aprovados. Sua reserva de BTC é criada junto com o fill. **Proteção elegível apenas a partir da abertura do candle seguinte ao da entrada**: não consultar o OHLC do candle de entrada para decidir sua saída, mesmo que depois ele toque S/T. O relatório deve identificar essa janela sem atuação da proteção; não prometer proteção imediata.

O stop é saída a mercado simulada; o alvo é saída a mercado condicionada a toque, sem ordem limitada, garantia de preço ou fila. Vender sempre a posição integral. Um preenchimento de saída encerra o grupo, consome/libera a reserva e invalida a outra perna. Não manter ordens órfãs. Sinal SELL, stop e alvo não podem vender o mesmo BTC duas vezes.

### 7.2. Prioridade na abertura

Na abertura contígua, sem acesso ao restante do candle:

1. Registrar OPEN e marca, atualizar patrimônio e bloqueios de entrada.
2. Para posição com proteção elegível, verificar `open <= S` ou `open >= T` (igualdade conta). Se houver gap/toque, saída protetiva tem prioridade; cancelar eventual saída comum pendente com `PROTECTIVE_EXIT_PREEMPTED`, transferindo a reserva sem duplicá-la.
3. Sem gatilho de abertura, executar eventual SELL comum; encerrar seu grupo protetivo.
4. Se houver BUY pendente e posição vazia, revalidar risco/reserva e preencher ou rejeitar. Proteção nova não atua nesse candle.

Para gap, referência de execução é o próprio open, para stop e alvo; preço efetivo de venda = referência × `(1-a)`, taxa = bruto × f. Stop não preenche ficticiamente em S se o open já estiver abaixo dele.

### 7.3. Resolução pelo intervalo OHLC

Na recepção do candle completo, executar **antes de expor CLOSE à estratégia**:

1. Validar candle e emitir `BAR_RANGE`, liberando OHLC somente ao resolvedor de execução.
2. Se a posição já era protegida na abertura e ainda existe, verificar `low <= S` e `high >= T`. Só stop tocado: referência S. Só alvo tocado: referência T. Ambos: selecionar **STOP_FIRST**, referência S e `ambiguous: true`. Ausência de toque não gera saída.
3. Se houver saída, emitir `PROTECTION_TRIGGER` com referência selecionada e amostrar essa marca causal de resolução; preencher venda com slippage/taxa e atualizar ledger/curva/risco.
4. Emitir CLOSE, marcar no fechamento conhecido, atualizar bloqueios e só então avaliar SMA ou ações manuais desse fechamento.

O OHLC não revela qual gatilho ocorreu primeiro. STOP_FIRST é convenção conservadora fixa, não reconstrução do caminho real. Para range intraperíodo, `fill.at` é o fechamento do intervalo, com `execution_time_model: BAR_CLOSE_RESOLUTION`, início/fim do intervalo e `intrabar_time_known: false`. Para gap, usar `execution_time_model: OPEN_EVENT`. Não inventar segundos intraperíodo nem retroagir ledger ou indicadores. Duração/exposição de trades resolvidos pelo range segue esse horário modelado e deve ser rotulada como aproximação.

A marca do gatilho entra antes do fill; a marca CLOSE entra depois. Isso evita marcar uma posição no preço de fechamento como se ainda existisse após a saída resolvida. A curva não incorpora high/low como se fossem uma trajetória conhecida; suas métricas são condicionadas à convenção de resolução. Preservar múltiplos pontos no mesmo timestamp por sequência e atualizar projeção/gráfico para os novos tipos de evento.

Depois de qualquer saída no candle k, impedir BUY decidido no fechamento de k com `REENTRY_SAME_CANDLE`, inclusive se a saída ocorreu na abertura. Uma nova entrada requer solicitação/cruzamento posterior; não reenviar automaticamente sinal recusado ou cancelado. SELL do fechamento após saída informa ausência de posição sem lançar outra venda. Perda diária/drawdown nunca impede saída nem desativa proteção existente.

## 8. Fixtures e exemplos de aceite

Todos os dados abaixo são fictícios. Criar somente durante a implementação os arquivos indicados; nesta etapa de especificação, os valores são **esperados, não resultados executados**.

### 8.1. Stop canônico

Revisão de escala em 11/11/2026: OHLC na referência de 100000 USDT/BTC,
como nas sprints 06–08. Step/mínimo de 0.000001 BTC preservam os fluxos em
USDT dos exemplos manuais; não houve mudança de unidade nem dados reais.

Criar `data/fixtures/sprint09-candles.json` com o mesmo envelope schema 1 e campos exatos de candle da Sprint 06. Para cada linha, usar `source=FICTICIA`, `symbol=BTCUSDT`, `interval=1m`, `is_closed=true`, `volume="1"`; converter todos os OHLC em strings. Horários em 01/01/2026 UTC:

| open_time | close_time | open | high | low | close |
| --- | --- | --- | --- | --- | --- |
| 12:00 | 12:01 | 100000 | 100000 | 100000 | 100000 |
| 12:01 | 12:02 | 100000 | 105000 | 95000 | 102000 |
| 12:02 | 12:03 | 102000 | 106000 | 89000 | 95000 |
| 12:03 | 12:04 | 95000 | 96000 | 94000 | 95000 |

Usar a configuração completa da seção 3.2. No fechamento 12:01: P=B=1000, X=0, E=100000, S=90000, T=120000, R=10 e L=10190. `q_risco=1/1019 BTC`; q após piso em 0.000001 = **0.000981 BTC**. O próximo incremento viola o orçamento. Perda planejada = **9.99639 USDT**.

| Fase | Caixa total USDT | Caixa reservado USDT | BTC total | BTC reservado | Taxas pagas USDT |
| --- | --- | --- | --- | --- | --- |
| Inicial | 1000 | 0 | 0 | 0 | 0 |
| BUY aceito e reservado | 1000 | 98.1981 | 0 | 0 | 0 |
| BUY preenchido na abertura 12:01 | 901.8019 | 0 | 0.000981 | 0.000981 | 0.0981 |
| Stop do intervalo 12:02–12:03 resolvido em 12:03 | 990.00361 | 0 | 0 | 0 | 0.18639 |

BTC reservado inclui somente uma reserva compartilhada da proteção. No stop: bruto 88.29, taxa 0.08829, recebimento 88.20171 USDT. Trade líquido = **-9.99639 USDT**, final BTC zero. Ambos os bloqueios patrimoniais permanecem falsos nesse exemplo. O fechamento 12:02, antes da saída, marca patrimônio **1001.8639 USDT**. A reserva inicial não altera patrimônio e não cria trade.

### 8.2. Variantes obrigatórias

1. **Gap desfavorável:** substituir somente o terceiro candle por O=80000, H=85000, L=75000, C=80000. Stop executa na abertura 12:02 a 80000, sem esperar o range. Recebimento 78.40152, perda realizada **19.79658**, taxas totais 0.17658 e caixa final **980.20342 USDT**. Excede R=10; não limitar a perda artificialmente ao orçamento. O gap também evidencia que stop não garante preço.
2. **Alvo:** terceiro candle O=102000, H=121000, L=101000, C=115000. Alvo resolve a 120000 na recepção do fechamento; recebimento 117.60228, lucro **19.40418**, taxas 0.21582 e caixa final **1019.40418 USDT**.
3. **Ambiguidade:** terceiro candle O=102000, H=121000, L=89000, C=100000. Resultado igual ao stop canônico; marcar ambos os toques, STOP_FIRST e `ambiguous=true`, sem afirmar sequência real.
4. **Candle de entrada:** alterar o segundo candle para O=100000, H=121000, L=89000, C=102000. Nenhuma proteção atua nesse candle; saída continua pelo terceiro candle. Registrar início de elegibilidade na abertura 12:02.
5. **Cancelamento:** depois do BUY canônico no mesmo fechamento 12:01, acrescentar `{"id":"cancelar-01","at_close":"2026-01-01T12:01:00+00:00","side":"CANCEL","target_order_id":"entrada-01"}`. Reserva 98.1981 volta ao disponível; caixa 1000, BTC/taxas zero, sem trade. Status da ordem CANCELED, código 0; cancelar não é falha financeira.
6. **Concorrência/mínimos:** segunda BUY no fechamento 12:01 é recusada por pendência sem consumir a primeira reserva. Em avaliação isolada, usar step `0.000000003`, mínimo superior à candidata, saldo zero e igualdade com mínimos/limites; não arredondar casas decimais nem aumentar q. O componente puro também deve conferir E=100000, S=98000, P=B=1000, X=0, r=0.01, x=1, f=0.001 e step=0.000001: L=2198, q=0.004549, desembolso 455.3549 e perda 9.998702 USDT.
7. **Revalidação desfavorável:** segundo candle O=101000, H=105000, L=95000, C=102000. A aprovação usou E=100000; a perda efetiva planejada de q=0.000981 com S=90000 sobe para **10.978371**, acima de R. Rejeitar BUY e liberar 98.1981, sem fill/taxa/BTC. Não redimensionar ou reancorar S.
8. **Bloqueios:** observações causais de patrimônio 1000 → 970 → 1000 no mesmo dia, limite diário 0.03: bloquear na igualdade e manter até a virada UTC. Com limite drawdown 0.05, 1000 → 1050 → 990 → 1050: queda 60/1050 ultrapassa limite; bloquear até fim da sessão, inclusive no dia seguinte. Conferir zero, base diária ausente/parcial e dois pontos distintos no mesmo timestamp. Esses vetores são testes do componente, não injeção de depósitos no motor.
9. **SELL e prioridade:** posição canônica com SELL manual solicitado em 12:02 e gap no terceiro candle: proteção vence, SELL comum é cancelada e há uma única venda/taxa. Sem gap/toque de abertura, SELL comum preenche antes de inspecionar o range. Com bloqueio BUY ativo, ambas as formas de saída permanecem possíveis.
10. **SMA e interrupção:** criar `experiments/sprint09-sma.json` a partir da configuração da seção 3.2, substituindo modo/ordens por SMA_CROSS de janelas 2/3. Usar os candles canônicos já versionados da Sprint 07; conferir sinais/aquecimento iguais ao modo antigo e decisões de risco separadas. Incluir testes de pendência final, reserva retida em lacuna, ausência de operações retroativas e proteção/ledger causais na API incremental e nos arquivos.

Para variantes CLI de gap/alvo/ambiguidade, criar `sprint09-candles-gap.json`, `sprint09-candles-alvo.json` e `sprint09-candles-ambiguo.json`. A configuração manual é a mesma; as alterações são as da tabela/variantes, sem dados reais ou escolhas pelo lucro. Demais variantes podem ser construídas em testes temporários, sem multiplicar arquivos desnecessariamente.

## 9. Análise, benchmarks e exportações

Preservar métricas e identidades da Sprint 08: realizado, base de custo, marcação bruta, liquidação hipotética e KEEP_OPEN. Substituir a hipótese de reserva zero pela projeção real. Reconciliar `E = capital + realizado + não realizado`, caixa e BTC disponíveis/reservados e propriedade de cada reserva em cada ponto. Amostrar também transições de reserva/liberação/transferência, além de OPEN, marca do gatilho, FILL e CLOSE; não registrar transferência como taxa ou trade.

No modo novo, relatório schema 4 contém `analysis` com política SPRINT09_V1 e objeto `risk` com `policy_version`, `parameters`, `evaluations`, `reservations`, `protection_groups`, `equity_observations`, `blocks`, `execution_conventions` e `reconciliation`. Cada avaliação identifica evento/sinal/ordem, snapshot, estimativas E/S/T, R/L, candidatos/razões, incrementos, limitadores, candidata, quantidade aprovada e motivo. Proteções e trades incluem origem da saída, intervalo, referência/efetivo, ambiguidade e horário modelado. Nunca relatar stop aprovado como preço garantido.

Manter os nove arquivos enriquecidos da Sprint 08 e acrescentar exatamente `risk.jsonl` e `reservations.jsonl`: **onze arquivos** em saída nova. `risk.jsonl` contém avaliações, observações/bloqueios e gatilhos, cada linha com `schema_version`, `run_id`, `record_type`, `at`, `source_event_seq` e payload; `reservations.jsonl` contém o histórico de titularidade/quantidade/status de reservas com referências ao ledger. Vazio gera arquivo vazio válido; o relatório mantém listas vazias com significado explícito.

Nos CSVs antigos, preservar nomes, ordem e significado das colunas da Sprint 08, alterando a versão para 4. `equity.csv` já possui caixa total/disponível/reservado; acrescentar **ao final**, nessa ordem, `asset_available,asset_reserved`. BTC total continua em `asset_quantity`. Os outros cabeçalhos anteriores permanecem iguais. Novos detalhes de risco/proteção ficam em JSONL/relatório/Markdown; não inventar colunas variantes por cenário. Preservar razões exatas, strings decimais, UTC e motivos de indisponibilidade.

Referências HOLD_USDT e BUY_HOLD_BTC continuam independentes, com mesmo capital, datas aceitas, taxa e slippage. Aplicar ao BUY_HOLD_BTC somente filtros fictícios de instrumento (piso por step, min_quantity/min_notional), sem orçamento de risco, bloqueios ou stops/alvos da estratégia. Declarar essa diferença de política, a maior exposição da referência e não somar carteiras. Não passar configuração de risco ao modo passivo como se fosse uma estratégia gerenciada. Preservar regras antigas do benchmark nos schemas antigos.

Texto, Markdown e HTML devem mostrar memória de cálculo de q e reservas, perda planejada versus realizada, bloqueios e vigência, janela sem proteção, saídas canceladas e ambiguidade. Manter candles/marcadores/curva offline com valores calculados em Python; marca de resolução no fechamento deve ser rotulada como horário modelado, sem inserir timestamp intraperíodo inventado. Inspecionar desktop, tela estreita e impressão durante a implementação.

## 10. CLI, entregáveis e validação futura

Adicionar `--risco` somente a `demonstrar`: sem estratégia usa os arquivos manuais canônicos da Sprint 09; com `--estrategia sma`, usa os candles da Sprint 07 e a nova configuração SMA de risco. Não alterar demonstrações antigas sem a flag. `executar` ativa o modo novo pelo schema 4, sem exigir flag adicional. Aceitar texto/JSON/HTML/Markdown no modo de risco, com ou sem `--analise` redundante. Markdown nos modos antigos continua exigindo `--analise`.

Códigos: 0 para replay concluído sem rejeições/não execuções (stop, alvo e cancelamento previsto são operações normais); 2 para rejeição de entrada/cancelamento inválido/ordem sem evento futuro; 1 para dados inválidos, erro técnico/aritmético ou interrupção por lacuna. O argparse continua retornando 2 por sintaxe inválida. Um bloqueio observado sem uma tentativa de entrada recusada não é, por si, erro. `demonstrar --risco` confere os esperados canônicos antes de sucesso; no SMA, confere coerência e valores independentes registrados pelo implementador, sem exigir lucro.

Preservar validação antes de criar saída, não sobrescrita, arquivos temporários, manifesto por último e INCOMPLETE. JSON em stdout contém somente relatório; diagnósticos em stderr. Não acrescentar endpoints, comandos de pesquisa ou conexões de negociação.

Entregar código e testes nos módulos necessários (por exemplo `risk.py`, `reservations.py`, `protection.py`, evoluindo engine/ledger/analysis existentes), fixtures/configurações, README, `docs/sprint09-validacao.md` e `docs/sprint09-glossario.md`. Não criar versões novas do projeto nem módulos vazios para sprints futuras. Explicar orçamento, perda unitária, passo, disponibilidade/reserva, grupo de proteção, bloqueio persistente, preço antigo, gap, ambiguidade e risco residual.

Comandos a executar **durante a implementação**, na raiz, com códigos individuais registrados:

```bash
source .venv/bin/activate
python --version
python -m unittest discover -s tests -v
python -m replayquant --help
python -m replayquant demonstrar --formato json
python -m replayquant demonstrar --estrategia sma --analise --formato json
python -m replayquant demonstrar --risco --formato texto
python -m replayquant demonstrar --risco --formato json
python -m replayquant demonstrar --risco --formato markdown
python -m replayquant demonstrar --risco --estrategia sma --formato json
```

Comparação e HTML, na mesma sessão Bash; usar uma saída nova por execução:

```bash
validacao_sprint09_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint09-candles.json --config experiments/sprint09-manual.json --saida "$validacao_sprint09_dir/a" --formato json
python -m replayquant executar --dados data/fixtures/sprint09-candles.json --config experiments/sprint09-manual.json --saida "$validacao_sprint09_dir/b" --formato json
for arquivo in manifest.json events.jsonl report.json ledger.jsonl equity.csv trades.csv metrics.csv benchmarks.csv report.md risk.jsonl reservations.jsonl; do
  cmp "$validacao_sprint09_dir/a/$arquivo" "$validacao_sprint09_dir/b/$arquivo" || exit "$?"
done
python -m replayquant executar --dados data/fixtures/sprint09-candles-gap.json --config experiments/sprint09-manual.json --saida "$validacao_sprint09_dir/gap" --formato json
python -m replayquant executar --dados data/fixtures/sprint09-candles-alvo.json --config experiments/sprint09-manual.json --saida "$validacao_sprint09_dir/alvo" --formato json
python -m replayquant executar --dados data/fixtures/sprint09-candles-ambiguo.json --config experiments/sprint09-manual.json --saida "$validacao_sprint09_dir/ambiguo" --formato json
python -m replayquant demonstrar --risco --formato html > "$validacao_sprint09_dir/relatorio.html"
python -m replayquant demonstrar --risco --estrategia sma --formato html > "$validacao_sprint09_dir/sma.html"
python -m unittest discover -s tests -v
git diff --check
```

Esperado 0 nos cenários manuais normais/gap/alvo/ambíguo e nos onze cmp; perda acima do orçamento não torna inválida uma saída que foi corretamente simulada. O SMA canônico retorna 0, com q=0.000962 BTC, caixa 999.8076 USDT e taxas 0.1924 USDT. Filtros maiores podem produzir código 2 por decisões legítimas de risco; esses casos são cobertos por testes separados. Casos negativos da seção 11 são conferidos na suíte com códigos pertinentes. Redirecionar HTML para fora de `--saida`; conferir stderr e código antes de usar o arquivo.

## 11. Critérios de aceite

1. Regressões existentes preservadas; modos antigos e schemas/artefatos anteriores continuam válidos. Confirmar o ponto de partida real antes de alterar, sem presumir que a contagem documentada de testes ainda é atual.
2. Dimensionamento confere valores da seção 8, empate de limitadores, frações periódicas, step não potência de dez, mínimos e igualdade. Nenhum aumento para atender filtro ou uso de quantidade arredondada para ultrapassar risco/saldo/exposição.
3. Aceitação/reserva atômicas; segunda ordem não gasta saldo já comprometido. Fill, release, transferência, cancelamento, rejeição e término reconciliam totais/disponíveis/reservados, ledger, lotes e taxas.
4. Repetir ação/candle/sinal/fill/reserva é inócuo; ID conflitante e falha aritmética preservam estado aceito. Nenhuma taxa duplicada ou ordem órfã. Falha técnica não vira recusa de política.
5. Revalidação com gap de entrada não reancora S/T nem aumenta R/q; rejeita e libera reserva. Avaliar caixa incluindo somente sua própria reserva e saldo livre real.
6. Bloqueios exatos na igualdade, recuperação no mesmo dia, virada UTC, drawdown persistente, patrimônio zero, base parcial/ausente e pontos com mesmo timestamp. BUY bloqueado não impede SELL, proteção ou marcação.
7. Stop/alvo somente após elegibilidade; gap usa open, range usa referência S/T com slippage, ambos toques usam STOP_FIRST e ambiguidade. Duração e horário da resolução são declarados; nenhum OHLC futuro chega ao indicador.
8. Prioridade proteção/SELL/BUY, uma única venda por lote, transferência de reserva e bloqueio de reentrada no candle da saída. Saída não é rejeitada por mínimos/orçamento de compra.
9. Causalidade por prefixo: alterar sufixo não muda decisões, reservas, ledger ou pontos anteriores; alterar OHLC futuro não muda aprovação/fill da abertura anterior. Igualdade lógica entre API incremental e replay de arquivo.
10. Fim normal libera pendências/grupo sem liquidar posição; lacuna conserva reservas e carteira do prefixo sem cancelamentos retroativos, benchmarks param juntos e retorno parcial é rotulado.
11. Reconstrução independente de ledger/reservas/patrimônio e métricas, benchmarks isolados com filtros e política passiva explícita, nenhum custo hipotético debitado ou reserva somada duas vezes.
12. JSON/API estritos, configurações inválidas, preço ausente/antigo/futuro, limites de tipo/magnitude e contexto decimal externo adverso; sem float financeiro ou razões exibidas influenciando decisões.
13. CLI com códigos 0/1/2, --analise redundante no risco, onze arquivos válidos, CSVs fixos, não sobrescrita, falha de escrita/INCOMPLETE e reprodução byte a byte em saídas distintas.
14. Texto/Markdown/HTML explicam cálculo, perdas, reservas, bloqueios, ambiguidade e limites; gráfico não inventa caminho intraperíodo; visualizações desktop/estreita/impressão verificadas e sem requisições externas.

Aprovação técnica não exige lucro. A documentação de validação deve separar resultados esperados, realmente observados, não executados e pendências, com Python/versões/comandos reais. Escrever esta especificação não significa que a Sprint 09 foi implementada ou testada.

## 12. Prompt autossuficiente de execução

Copie o bloco inteiro para um agente com acesso ao repositório. Os contratos detalhados estão nas seções 1 a 11 deste documento versionado, cuja leitura é obrigatória; o prompt não depende da conversa original.

````text
Implemente a Sprint 09 — Risco e saídas protetivas do ReplayQuant.

CONTEXTO E PRÉ-REQUISITOS
Trabalhe em /home/cams7/Dev/Cripto_Tests/replayquant, evoluindo o projeto atual.
Inspecione git status, AGENTS.md aplicáveis, implementação e testes. Leia
integralmente docs/sprint09.md (seções 1 a 11), docs/planejamento.md e os contratos
Sprints 06/07/08 com seus registros de validação. A referência desta especificação
é 6cc6a37; não force checkout nem descarte trabalho posterior. Confirme a base
pela suíte em .venv antes de editar. Se faltar pré-requisito essencial, registre
a lacuna antes do trabalho dependente. Preserve código e alterações existentes.

Implemente, teste e documente; não entregue apenas proposta. Use Python >=3.11,
referência 3.12.14, biblioteca padrão e unittest, sem instalar dependências,
usar rede, atualizar bundle/licenças do gráfico ou importar laboratórios vizinhos.
Não antecipe parciais, limitadas, stop-limit, trailing, catálogo multipar, carteira
compartilhada, dados reais, pesquisa, AWS ou negociação real.

COMPATIBILIDADE E ENTRADAS
Implemente exatamente o schema 4 da seção 3, modo MANUAL ou SMA, sem quantity fixa:
initial_cash, custos, instrument_filters, risk e orders ou strategy exclusivos.
Use JSON estrito, tipos reais, Decimal de strings, datas UTC, validação também
na API e limites existentes. Configurações 1/2 e saídas antigas com/sem --analise
continuam com comportamento anterior. Risco sempre inclui análise e saída schema 4;
--analise é redundante nesse modo e não altera sua identidade. A identidade nova
inclui risk_policy e analysis_policy SPRINT09_V1, hashes de entradas/código/assets
e Python; exclua hora real e caminho de saída. Não prometa hashes antigos iguais
após mudar o código. Não adicione reservas ou stops às configurações antigas.

DIMENSIONAMENTO E REVALIDAÇÃO
Siga a seção 4: P patrimonial bruto, B disponível, X exposição nominal marcada,
E=marca*(1+slippage), S=E*(1-stop_fraction), T=E*(1+target_fraction), R=P*r,
L=E*(1+f)-S*(1-f). q_bruta=min(R/L,max(0,P*x-X)/E,B/(E*(1+f))). Use razões exatas
e floor de incrementos por step, inclusive 0.000000003; não arredonde casas para
simular step. Recalcule e reduza se necessário; mínimos nunca autorizam aumentar.
Igualdade com limites é válida. Preserve candidatos, limitadores empatados,
razões e memória de cálculo; candidata rejeitada não é quantidade aprovada.
Contabilidade/reserva usa Decimal local precisão 40/HALF_EVEN com erro em inexatidão
antes de mutar; razões podem usar Fraction. Não use float financeiro.

Congele q, S, T e R na aprovação. Na abertura revalide limites com preço efetivo
atual, bloqueios, caixa e filtros; exija S<E_fill<T e perda planejada <=R.
Não reancore proteções, aumente orçamento ou reduza quantidade na abertura:
rejeite integralmente e libere a reserva se falhar. Inclua duas taxas na perda
planejada, declarando que o slippage de saída não está garantido nesse orçamento.
Respeite precedência/motivos da seção 4; preço futuro é dado inválido, ausente
ou desatualizado rejeita entrada, idade exatamente no limite é válida.

RESERVAS E ESTADO
A aprovação pura não reserva. No motor, aceitar/reservar é uma transição atômica.
Compra reserva q*E*(1+f); disponível+reservado=total, sem mudar patrimônio.
Fill consome a reserva, devolve diferença ou complementa com caixa livre real
após revalidar; nunca use fundos de outra ordem. Venda reserva BTC. O grupo stop/
alvo compartilha uma reserva única da posição, transferida para saída comum
quando necessário; cancelar essa saída devolve a titularidade ao grupo.

Amplie o ledger conforme seção 5 com RESERVE/RELEASE/TRANSFER e deltas/saldos de
disponível/reservado, referências e propriedade. Não gere log decorativo nem
some reserva duas vezes. Rejeição de outra solicitação não libera a primeira.
Implemente CANCEL manual de pendência, CANCELED e motivos definidos; cancelamento
não desfaz fill. Repetições idênticas são inócuas; conflitos falham sem mutação.
No fim normal libere pendências e grupo, mantendo posição KEEP_OPEN sem venda;
na lacuna SMA preserve posição/pendência/reservas do prefixo, sem finalizar ou
retomar operações retroativas. Saídas e marcações continuam permitidas sob
bloqueio BUY; vendas usam quantidade integral do lote, nunca novo sizing.

BLOQUEIOS E PROTEÇÕES
Atualize bloqueios no núcleo a cada ponto causal, não apenas no relatório.
Base diária é primeira observação positiva do dia UTC; perda=max(0,(D-P)/D).
Pico é máximo da sessão; DD=(pico-P)/pico. Limiar atingido bloqueia. Diário
persiste até virar o dia, drawdown até fim da sessão, mesmo com recuperação.
Trate zero/base ausente/parcial sem divisão inválida. Eventos distintos no mesmo
timestamp são válidos por seq/phase; mesma chave conflitante é erro. Não reinicie
sessão dentro do experimento para limpar bloqueios.

Implemente exatamente as prioridades da seção 7. Proteção só é elegível no candle
seguinte ao de entrada; declare a janela sem atuação. Na abertura: marca/bloqueios,
proteção por gap, SELL comum, BUY revalidado. Gap usa open e slippage de venda.
Proteção vence SELL pendente quando houver gatilho; uma venda/taxa por lote.
Na recepção do candle completo: BAR_RANGE para execução, resolver low<=S/high>=T,
PROTECTION_TRIGGER/marca selecionada, fill, CLOSE e só depois estratégia/ações.
Ambos os toques: STOP_FIRST, ambiguous=true. Range preenche com referência S ou T,
slippage/taxa; fill.at=close_time e BAR_CLOSE_RESOLUTION com intervalo e horário
intrabar desconhecido. Não retroaja ledger nem exponha OHLC ao indicador antes
do fechamento. No candle da saída não aceite nova BUY decidida nesse fechamento.

EXEMPLOS E ARQUIVOS
Crie a configuração JSON exata da seção 3.2 e os candles completos definidos
pela tabela da seção 8.1, usando os campos schema 1 existentes. Capital 1000,
f=0.001, a=0, E=100000, S=90000, T=120000, R=10, L=10190, step=0.000001, q=0.000981.
Reserve 98.1981; compra na abertura 12:01 UTC de 01/01/2026 deixa caixa 901.8019,
BTC 0.000981 e taxa 0.0981. Stop do terceiro candle resolve a 90000 no fechamento
12:03, recebimento 88.20171, perda 9.99639, taxa total 0.18639 e caixa 990.00361.
Não aplique stop/alvo no candle da entrada.
Crie variantes gap/alvo/ambígua da seção 8.2 com os nomes fixados: gap a 80000
produz caixa 980.20342 e perda 19.79658 acima de R; alvo a 120000 produz caixa
1019.40418; ambos toques reproduzem o stop com ambiguidade. Não limite perda ao
orçamento nem altere dados para obter lucro. Confira CANCEL sem fill, concorrência,
step não decimal, mínimos, revalidação a 101000 (perda 10.978371 rejeitada), bloqueios,
prioridade SELL/proteção e integração SMA com fixtures antigas. Crie configuração
sprint09-sma conforme seção 8.2.10, sem modificar os candles antigos.

RELATÓRIOS, CLI E VERIFICAÇÃO
Amplie análise/curva/métricas para reservas e marcas de gatilho, sem alterar
semântica financeira da Sprint 08. Reconcile ledger/reservas em cada prefixo.
Benchmarks usam mesmo horizonte/custos e filtros de instrumento, mas sem política
de risco/proteção da estratégia; explicite a diferença. Não some carteiras.
Implemente objeto risk e onze arquivos conforme seção 9, incluindo risk.jsonl e
reservations.jsonl, CSVs com colunas fixadas e análise schema 4. Preserve saída
nova sem sobrescrita, INCOMPLETE e manifesto por último. Texto/Markdown/HTML e
gráficos devem explicar custos, reservas, bloqueios, ambiguidade e horário
modelado, sem requisições externas ou cálculos financeiros novos no JavaScript.

Adicione demonstrar --risco, com opção SMA; executar despacha pelo schema 4.
Preserve CLI antiga. Siga códigos 0/1/2 da seção 10; stop/alvo/cancelamento normal
não são falha, rejeição de entrada é código 2, lacuna/erro técnico é 1. JSON stdout
é só relatório; diagnósticos em stderr. Implemente todos os testes da seção 11,
incluindo regressões, atomicidade, idempotência, prefixo causal, contexto externo,
reconstrução independente, onze arquivos e reprodução byte a byte.

Execute os comandos completos da seção 10: suíte de entrada, ajuda, modos antigos,
demonstrações de risco texto/JSON/Markdown/SMA, duas execuções canônicas, onze cmp,
variantes gap/alvo/ambígua, HTML manual/SMA, suíte final e git diff --check.
Ative .venv, registre Python real e código de cada comando; documente previamente
os motivos/código esperado do SMA em vez de exigir sucesso/lucro artificial.
Inspecione HTML desktop/estreito/impressão e preserve assets/licenças existentes.
Falta de Python de referência não autoriza instalar/alterar sistema silenciosamente
ou inventar validação. Corrija falhas sem alterar hipóteses para passar testes.

Entregue código, testes, fixtures/configurações, README, docs/sprint09-validacao.md
e docs/sprint09-glossario.md em português. Registre decisões e limitações; separe
esperado, observado, não executado e pendências. Não faça commit, publicação ou
alterações externas. Na resposta final informe arquivos alterados, comandos
realmente executados, resultados e limites. Não declare concluída a sprint se
faltar requisito obrigatório; lucratividade não é critério de aprovação técnica.
````
