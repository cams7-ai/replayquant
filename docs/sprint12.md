# Sprint 12 — Carteira compartilhada

**Projeto** ReplayQuant  
**Nível** intermediário  
**Referência** [Planejamento](planejamento.md), especialmente seções 4, 12, 21 e 23  
**Pré-requisitos** Sprints 06 a 11 implementadas e verificadas  
**Estado** implementada; execução, resultados observados e limitações em [sprint12-validacao.md](sprint12-validacao.md). O texto abaixo conserva os contratos e a memória de cálculo da especificação.

## 1. Objetivo e ponto de partida

Simular estratégias e pares concorrendo por um caixa físico comum, com limites por carteira, instrumento e estratégia. O resultado deve explicar quem é dono de cada lote, quais recursos cada ordem comprometeu e como as contribuições individuais reconciliam com o patrimônio total.

Trabalhar em `/home/cams7/Dev/Cripto_Tests/replayquant`, evoluindo o projeto existente. A referência consultada é o commit `82128c8`. Inspecionar HEAD, `git status` e instruções `AGENTS.md` aplicáveis. Preservar alterações existentes e posteriores. Ler os contratos e registros anteriores, em especial [Sprint 09](sprint09.md), [Sprint 10](sprint10.md), [Sprint 11](sprint11.md) e [validação da Sprint 11](sprint11-validacao.md). Conferir a suíte e as demonstrações de entrada antes de implementar.

A base tem catálogo imutável, schema 6, ativos genéricos, indicadores exatos, risco/reservas, API incremental e matriz independente. `AssetBalance` representa um ativo por sessão e o ledger conserva um `open_fill` e uma base de custo por carteira. O coordenador novo precisa suportar vários lotes e ativos no mesmo livro, compartilhando a aritmética e as políticas existentes. A matriz da Sprint 11 continua sendo comparação de sessões independentes.

## 2. Escopo

Entregar sessão de carteira, relógio global, lotes atribuídos, subcontas de orçamento, reservas comuns, arbitragem determinística, limites hierárquicos e relatório reconciliado. Usar FICTICIA, cotação USDT, candles de um minuto e catálogo da Sprint 11, inicialmente com BTCUSDT/ETHUSDT. As estratégias continuam SMA_CROSS/1, EMA_CROSS/1 e RSI_REVERSION/1, com seus parâmetros e sementes.

A política obrigatória é `ALLOCATED_BUDGETS_V1`, com frações iniciais de orçamento por estratégia. Combinação por voto ou consenso fica registrada como extensão opcional após esta entrega, sem constituir requisito de aceite. O relatório deve identificar a política efetivamente executada.

Cada estratégia pode acompanhar vários pares, com indicador próprio por `(strategy_id, source, symbol, interval)`. Permitir um lote aberto e uma intenção comum pendente por estratégia/par, mas vários lotes de estratégias diferentes no mesmo ativo físico. Quantidades de entrada são dimensionadas e congeladas até a saída integral daquele lote.

Preservar schemas 1, 2, 4, 5 e 6, `executar`, `comparar` e seus resultados. Usar Python >= 3.11, biblioteca padrão, `unittest`, Decimal financeiro em contexto local e razões exatas. Manter assets/licenças e funcionamento offline. Dados reais, banco, conversão de cotação, margem, parciais, novas frequências, otimização, execução paralela e recuperação após reinício pertencem a outras etapas.

## 3. Propriedade e reconciliação

### 3.1. Caixa físico e orçamentos

Existe um caixa físico USDT e uma posição física por ativo base. Na inicialização, a estratégia i recebe atribuição virtual `A_i = initial_cash × allocation_fraction_i`. Frações positivas somam no máximo 1, por comparação exata. O residual pertence à subconta `UNALLOCATED`, reservada pelo sistema e indisponível para novas compras nesta política.

As subcontas são atribuições auditáveis do mesmo caixa. Seus saldos são atualizados pelos próprios fills, taxas e reservas. Ganhos/perdas alteram o patrimônio da estratégia e não provocam redistribuição de orçamento. Não há empréstimo entre subcontas ou realocação automática do residual.

Para cada estratégia i, `C_i` é caixa atribuído total, `C_i_disponível` exclui suas reservas BUY e `P_i = C_i + soma(q_lote × marca_do_ativo)` inclui somente seus lotes. O patrimônio global é `P = C + soma(Q_ativo × marca_do_ativo)`.

```text
C = C_UNALLOCATED + soma(C_i)
C_disponível = C_UNALLOCATED + soma(C_i_disponível)
C_reservado = soma(C_i_reservado)
C = C_disponível + C_reservado

Q_ativo = soma(q_lote do mesmo ativo)
Q_ativo = Q_ativo_disponível + Q_ativo_reservado
P = C_UNALLOCATED + soma(P_i)
```

Somar quantidades somente dentro da mesma moeda base. Reservas integram os totais e não são somadas novamente ao patrimônio.

### 3.2. Lotes e titularidade

Cada lote contém `lot_id`, `strategy_id`, instrumento, quantidade, referência/fill de entrada, base de custo com taxa, stop/alvo, risco planejado e estado. Cada SELL comum ou protetivo encerra somente o lote de sua estratégia/par. Rejeitar tentativa explícita de atingir lote de outro titular com `OWNERSHIP_MISMATCH`. Ausência de lote próprio gera `INSUFFICIENT_ASSET`, mesmo se houver quantidade física pertencente a outra estratégia.

A proibição de acumular posição é por estratégia/par. A posição física agregada positiva não impede outra estratégia de abrir seu próprio lote dentro dos limites. O ledger precisa conservar bases de custo e realizado por lote, estratégia e ativo. Reutilizar os cálculos de bruto, taxa, deltas e PnL existentes, ampliando o controle de múltiplos lotes.

Cada lote tem uma reserva compartilhada de base para suas proteções, criada uma vez. Uma SELL comum transfere o detentor dessa reserva do grupo protetivo para a ordem, mantendo `strategy_id` e `lot_id`. Cancelar restaura o grupo. Uma proteção preempta somente a saída comum do mesmo lote, com uma venda/taxa por lote e invalidação de sua outra perna.

IDs de ordem, execução, reserva, avaliação e sinal incluem vínculo inequívoco com a instância estratégia/par. `strategy_id` identifica o titular; detentor temporário da reserva identifica ordem ou grupo. Repetição idêntica é inócua. Conflito, venda excessiva, moeda divergente ou titularidade inválida preservam o estado aceito.

### 3.3. Contribuições

Para cada titular, `PnL_i = realizado_i + não_realizado_i = P_i − A_i`. Manter a parcela de UNALLOCATED em caixa. A soma deve reconciliar em cada ponto observado.

```text
P = initial_cash + soma(PnL_i)
retorno_carteira_% = (P − initial_cash) / initial_cash × 100
contribuição_i_% = PnL_i / initial_cash × 100
retorno_próprio_i_% = PnL_i / A_i × 100
```

Contribuições percentuais usam o capital global inicial como denominador. Os retornos próprios usam atribuições iniciais diferentes e não são somados como retorno da carteira.

## 4. Relógio global e causalidade

### 4.1. Fronteiras e ordem de fases

O relógio percorre fronteiras de minuto da janela comum. A API incremental deve aceitar lotes tipados de fechamentos e aberturas por fronteira, com contrato equivalente a `on_boundary(at, closes, openings)`. O arquivo usa o mesmo coordenador. Na primeira fronteira não há fechamento anterior; na última não há nova abertura negociável.

Aplicar a ordem abaixo, registrando fase e sequência global, inclusive para eventos com mesmo timestamp.

1. Validar identidades, tempos, duplicatas e composição do lote recebido. Liberar os OHLC completos dos candles encerrados e atualizar suas marcas de fechamento como um lote comum.
2. Resolver saídas OHLC de lotes que já tinham proteção elegível no início desses candles. Aplicar STOP_FIRST por lote quando necessário, com BAR_CLOSE_RESOLUTION no fechamento.
3. Avaliar todos os indicadores dos fechamentos liberados. Registrar os sinais antes de decidir a ordem financeira. Processar cancelamentos e solicitações SELL próprios, transferindo suas reservas.
4. Arbitrar novos BUY na ordem da seção 4.2, usando somente marcas já liberadas e o estado das reservas. Cada aprovação compromete capacidade para o candidato seguinte.
5. Verificar as aberturas esperadas para os instrumentos disponíveis. Uma lacuna encerra o prefixo com diagnóstico global antes de consumir qualquer abertura dessa fronteira.
6. Liberar todas as cotações OPEN elegíveis como um lote comum, atualizando patrimônio, bloqueios e limites.
7. Resolver gaps protetivos, executar SELL comuns remanescentes e então revalidar/executar BUY pendentes, nessa ordem. Recursos liberados por saídas ficam disponíveis para a revalidação de ordens já aprovadas.

Uma BUY rejeitada no fechamento não é reenviada automaticamente porque uma venda na abertura liberou caixa. Ela exige novo cruzamento, conforme as sprints anteriores. Abertura seguinte pode compartilhar timestamp com o sinal, mas pertence a fase posterior. Alterar suas cotações não pode alterar a aprovação/reserva anterior.

### 4.2. Prioridade e idempotência

A ordem entre candidatos é `(priority, strategy_id, symbol, signal_id)`, com menor prioridade numérica primeiro. Configurações declaram a prioridade. Empates restantes usam ordem lexicográfica dos identificadores. A política é explícita e não representa garantia de equidade econômica. A ordem das listas e dos arquivos não participa da decisão.

Aplicar a mesma ordem estável entre saídas da mesma fase, usando `lot_id` como desempate final. Gap protetivo prevalece sobre SELL comum do próprio lote. Prioridade de novos candidatos não autoriza consumir reserva de outra ordem previamente aprovada.

Normalizar e ordenar o conteúdo das fronteiras por suas identidades de domínio, deduplicando eventos equivalentes antes do digest. Registrar ID/digest da fronteira recebida e suas fases. Repetir a mesma fronteira não repete indicadores, ordens ou efeitos financeiros. Conteúdo divergente na mesma chave ou nova fronteira fora de ordem falha sem mutação. Validação e preparação da fronteira acontecem em estado isolado; falha técnica ou aritmética não compromete parte dela. Interrupção por DATA_GAP é um resultado controlado que conserva o prefixo de fechamentos/sinais anterior à fase OPEN da própria fronteira.

### 4.3. Marcação comum e proteções

No caminho novo, usar política `BOUNDARY_MARKS_V1`. As marcas CLOSE de todos os ativos do lote são publicadas juntas antes das resoluções OHLC; marcas OPEN são publicadas juntas antes dos fills de abertura. Nenhum extremo high/low vira trajetória de mercado para marcar outros lotes. O preço condicionado do stop/alvo continua sendo referência do fill, com slippage e taxa, e fica separado da marca comum.

Essa é uma convenção específica schema 7 para valorar conjuntamente vários lotes. Os caminhos anteriores mantêm sua amostragem. A curva inclui ponto inicial, lotes de marcas, cada fill, transições de reserva e término, com sequências distintas. Bloqueios patrimoniais observam esses pontos na ordem registrada. Duração, drawdown e exposição são condicionados a essa sequência modelada, sem reconstrução intraperíodo.

Stop/alvo são definidos na aprovação e congelados. A proteção começa somente no candle seguinte ao da entrada do lote. Após saída, impedir reentrada no mesmo candle para a mesma estratégia/par; outras instâncias continuam sujeitas a seus próprios estados e limites.

## 5. Limites, dimensionamento e revalidação

### 5.1. Capacidade comprometida

Cada estratégia possui os RiskParameters da Sprint 09, aplicados ao seu patrimônio atribuído `P_i`. A carteira tem limites globais de exposição, perda diária, drawdown, idade de marcas e risco aberto planejado. Cada instrumento tem teto de exposição relativo a `P`.

A exposição comprometida soma posições abertas às marcas atuais e nocionais estimados de BUY pendentes, sem contar uma ordem duas vezes. Calcular `X_total`, `X_instrumento` e `X_i` nesses três níveis. O risco comprometido `K` soma perdas planejadas de lotes abertos e BUY pendentes. Na passagem de pendência para lote, substituir a estimativa pela perda aprovada no fill, sem duplicar compromisso. Saída/cancelamento libera a parcela apropriada.

O risco de um lote aberto usa o preço efetivo de entrada e o stop absoluto, com as duas taxas, conservando o cálculo planejado inicial. Não é recalculado para aparentar um teto garantido à medida que o preço muda. Gaps e slippage de saída podem superar esse valor. Identificar lotes sem proteção negociável após fim de disponibilidade.

### 5.2. Fórmulas BUY

Com referência causal `m`, slippage `a`, taxa `f`, stop fracionário `s_i`, alvo `t_i` e fração de risco `r_i` da estratégia:

```text
E = m × (1 + a)
S = E × (1 − s_i)
T = E × (1 + t_i)
L = E × (1 + f) − S × (1 − f)
R_i = P_i × r_i

q_risco_estratégia = R_i / L
q_risco_carteira = max(0, P × max_open_risk_fraction − K) / L
q_exposição_carteira = max(0, P × portfolio.exposure_fraction − X_total) / E
q_exposição_instrumento = max(0, P × instrument_limit − X_instrumento) / E
q_exposição_estratégia = max(0, P_i × risk_i.exposure_fraction − X_i) / E
q_caixa = min(C_global_disponível, C_i_disponível) / (E × (1 + f))
q_bruta = mínimo dos seis candidatos
q = floor(q_bruta / step_do_instrumento) × step_do_instrumento
```

Registrar todos os candidatos, limitadores ativos e empates como razões exatas. Validar mínimos sem aumentar a quantidade. Aprovar e reservar `q×E×(1+f)` USDT atomicamente, vinculando titular e instância. Reserva virtual e física representam o mesmo compromisso e não dois débitos.

Precedência BUY obrigatória, após validação estrutural: disponibilidade, bloqueios globais diário/drawdown, bloqueios da estratégia diário/drawdown, preço do alvo ausente/antigo, marcas de ativos detidos ausentes/antigas, pendência própria, posição própria, reentrada própria, patrimônios não positivos, caixa disponível, candidatos/limites e mínimos. Preço futuro é erro de domínio. Registrar bloqueios ativos e motivo primário estável.

Usar motivos específicos como PORTFOLIO_DAILY_LOSS_BLOCKED, PORTFOLIO_DRAWDOWN_BLOCKED, STRATEGY_DAILY_LOSS_BLOCKED, STRATEGY_DRAWDOWN_BLOCKED, PORTFOLIO_PRICE_STALE, OWNERSHIP_MISMATCH e os motivos anteriores pertinentes. Um candidato zero após o cálculo usa BELOW_MINIMUMS e conserva sua memória de limitadores.

### 5.3. Preenchimento e bloqueios

Antes de cada BUY, revalidar disponibilidade, marcas/bloqueios, orçamento congelado `R_i`, caixa físico e atribuído, mínimos, S < E_fill < T e todos os tetos hierárquicos. Para verificar o compromisso, excluir a reserva/candidatura própria e reinseri-la com o preço real simulado. Outras reservas permanecem comprometidas. Não redimensionar quantidade, orçamento ou proteção na abertura.

Limites usam os patrimônios atualizados, inclusive custos de fills anteriores na mesma fase. Se qualquer condição falhar, rejeitar integralmente e liberar a reserva uma vez. Usar EXPOSURE_PORTFOLIO, EXPOSURE_INSTRUMENT, EXPOSURE_STRATEGY ou OPEN_RISK_LIMIT para o limite que falhou, respeitando essa ordem depois de bracket, orçamento e caixa. Queda de patrimônio pode deixar posições já abertas acima de um teto; conservar a posição, bloquear novo aumento e reportar o excesso.

Bloqueios globais e por estratégia seguem as regras diárias UTC e de drawdown persistente da Sprint 09. Caixa reservado não é perda. Atingir limiar conta como bloqueio. SELL e saídas protetivas próprias continuam habilitadas. Não reiniciar sessão ou redistribuir orçamento para apagar bloqueios.

## 6. Catálogo, lacunas e preços

Cada dataset tem um instrumento e é validado integralmente antes do recorte. Resolver catálogo, janela e unidades como na Sprint 11. Dados excluídos não aquecem indicadores. Cada par de bindings usa seu histórico elegível, sem misturá-lo a outro símbolo ou titular.

A política compartilhada é `GLOBAL_GAP_INTERRUPT_V1`. Em cada minuto, exigir abertura para todos os datasets com instrumento disponível e vinculado à carteira naquele instante. Uma ausência interna ou de borda durante essa disponibilidade interrompe a carteira inteira antes de publicar o lote OPEN. Preservar caixa, lotes, ordens, reservas e último conjunto de marcas aceito. Não executar outro ativo no mesmo lote incompleto. Essa política é distinta das execuções independentes de comparar.

Um instrumento fora de disponibilidade não gera abertura esperada e seus bindings ficam inativos, com motivo/cobertura registrados. Se nenhum instrumento tiver observações elegíveis na janela, retornar PORTFOLIO_UNAVAILABLE, código 2, com desempenho nulo e capital preservado.

Ao fim da disponibilidade de um instrumento, não aceitar novos fills OPEN. Pendências sem evento elegível terminam com INSTRUMENT_UNAVAILABLE e liberação apropriada. Conservar posições físicas e propriedade dos lotes. Encerrar grupos sem execução possível com estado explícito de indisponibilidade e liberar sua reserva de base, preservando o risco planejado histórico e o alerta de proteção indisponível. Um candle válido ainda pode resolver proteção em seu fechamento coincidente com esse fim.

A marca conservada de um ativo detido aparece com horário/idade. Se faltar marca ou sua idade exceder portfolio.max_price_age_seconds, bloquear novas BUY da carteira com motivo próprio, sem impedir saídas elegíveis. O alvo de uma compra também respeita a disponibilidade e idade de preço da sua estratégia. Não gerar venda de ativo indisponível nem usar um preço carregado como nova cotação negociável.

No fim normal da janela, manter KEEP_OPEN, liberar pendências/grupos sem cobrar taxa hipotética e separar patrimônio bruto de liquidação hipotética por lote/ativo. Na interrupção por lacuna, conservar reservas. Finalização e repetição são idempotentes.

## 7. Configuração schema 7 e CLI

Introduzir comando futuro `carteira --config --saida --formato`, com texto, JSON, Markdown e HTML. Schema 7 implica análise; `--analise` pode ser redundante. Na API, exigir catálogo e configuração tipados, sem fallback global. Preservar executar/comparar e seus schemas.

Criar futuramente `experiments/sprint12-compartilhada.json` com o exemplo completo abaixo. Caminhos são relativos à receita. O catálogo existente da Sprint 11 autoriza os ativos e fornece filtros, sem overrides locais.

```json
{
  "schema_version": 7,
  "mode": "SHARED_PORTFOLIO",
  "source": "FICTICIA",
  "quote_asset": "USDT",
  "interval": "1m",
  "catalog": "../data/catalogo/sprint11-instrumentos.json",
  "window": {"start": "2026-01-01T12:00:00+00:00", "end": "2026-01-01T12:08:00+00:00"},
  "initial_cash": "1000",
  "fee_rate": "0.001",
  "slippage_rate": "0",
  "signal_policy": "ALLOCATED_BUDGETS_V1",
  "portfolio": {
    "exposure_fraction": "0.8",
    "max_open_risk_fraction": "0.03",
    "daily_loss_fraction": "0.9",
    "drawdown_fraction": "0.9",
    "max_price_age_seconds": "60"
  },
  "instrument_limits": {"BTCUSDT": {"exposure_fraction": "0.03001"}},
  "datasets": [{"symbol": "BTCUSDT", "path": "../data/fixtures/sprint12-btc-candles.json"}],
  "strategies": [
    {
      "id": "sma",
      "priority": 0,
      "allocation_fraction": "0.5",
      "symbols": ["BTCUSDT"],
      "strategy": {"name": "SMA_CROSS", "version": 1, "parameters": {"short_window": 2, "long_window": 3}},
      "risk": {
        "risk_fraction": "0.02", "exposure_fraction": "1", "stop_fraction": "0.5", "target_fraction": "0.9",
        "daily_loss_fraction": "0.9", "drawdown_fraction": "0.9", "max_price_age_seconds": "60"
      }
    },
    {
      "id": "ema",
      "priority": 1,
      "allocation_fraction": "0.5",
      "symbols": ["BTCUSDT"],
      "strategy": {"name": "EMA_CROSS", "version": 1, "parameters": {"short_window": 2, "long_window": 3}},
      "risk": {
        "risk_fraction": "0.02", "exposure_fraction": "1", "stop_fraction": "0.5", "target_fraction": "0.9",
        "daily_loss_fraction": "0.9", "drawdown_fraction": "0.9", "max_price_age_seconds": "60"
      }
    }
  ]
}
```

Validar JSON estrito e API, versões inteiras reais, tipos, finitude, limites de representação, UTC, janela e regras dos indicadores. IDs seguros são únicos e diferentes de UNALLOCATED. Prioridades são inteiros >= 0, sem booleanos. Alocações e frações de limites são positivas e <= 1; stop continua < 1; idades são positivas. Somar alocações por razão exata.

Datasets e símbolos de cada binding são únicos. Cada símbolo usado possui dataset, autorização de catálogo e limite; cada dataset possui ao menos um binding. Recusar campos inesperados, cotação incompatível, filtros locais e referências inexistentes antes de criar saída. Interpretar listas por seu conteúdo canônico, conservando hash original da receita como proveniência.

A saída nova usa `balances.cash_total`, `cash_available`, `cash_reserved` e `assets` indexados por base, com total/disponível/reservado. Inclui lotes e contribuições por titular. Não reinterpretar o saldo agregado como um único AssetBalance nem alterar payloads legados.

## 8. Fixtures e memória de cálculo

### 8.1. Dois titulares no mesmo BTC

Criar `data/fixtures/sprint12-btc-candles.json` com oito candles fechados de 01/01/2026 12:00–12:08 UTC, volume base "1" e fechamentos **100000, 90000, 80000, 100000, 120000, 100000, 80000, 80000**. Primeira abertura 100000; cada abertura seguinte é o fechamento anterior; high=max(open,close) e low=min(open,close). Envelope de candles schema 1 e metadados FICTICIA/BTCUSDT/1m.

SMA/EMA 2/3 geram BUY no quinto fechamento e SELL no sétimo, sem outro cruzamento no oitavo. Compram às 12:05 a 120000 e vendem às 12:07 a 80000. Stop 60000 e alvo 228000 ficam sem toque. Cada atribuição inicial é 500 USDT. Cada orçamento de risco é `500×0.02 = 10 USDT`. A perda unitária é `120000×1.001 − 60000×0.999 = 60180 USDT/BTC`.

O teto BTC inicial é `1000×0.03001 = 30.01 USDT`. SMA tem prioridade e recebe piso de 10/60180 para **0.000166 BTC**, nocional 19.92. Para EMA, o espaço restante é 10.09 USDT; seu candidato por instrumento é 10.09/120000 e o piso resulta em **0.000084 BTC**, nocional 10.08. Compromisso total de risco planejado é **15.045 USDT**, abaixo do teto global de 30 USDT.

O limite de 3.001% foi escolhido para conservar pequena folga após as taxas da primeira compra. Na abertura, o patrimônio já afetado por essa taxa reduz o teto para **30.0094022008 USDT**, ainda suficiente para o nocional total de 30 USDT. A revalidação continua obrigatória.

| Cálculo em USDT, salvo quantidade | SMA | EMA | Total físico |
| --- | --- | --- | --- |
| Quantidade BTC | 0.000166 | 0.000084 | 0.000250 |
| Compra bruta | 19.92 | 10.08 | 30 |
| Taxa de compra | 0.01992 | 0.01008 | 0.03 |
| Desembolso | 19.93992 | 10.09008 | 30.03 |
| Venda bruta | 13.28 | 6.72 | 20 |
| Taxa de venda | 0.01328 | 0.00672 | 0.02 |
| Recebimento | 13.26672 | 6.71328 | 19.98 |
| Resultado realizado | −6.67320 | −3.37680 | −10.05 |
| Caixa atribuído/físico final | 493.32680 | 496.62320 | 989.95 |

Expectativa de oito avaliações por binding, quatro sinais, quatro fills, dois lotes encerrados, BTC zero, taxas **0.05 USDT**, caixa/patrimônio final **989.95 USDT**, retorno global **−1.005%** e código **0**. Contribuições são −0.66732% e −0.33768% do capital global. Retornos próprios são −1.33464% e −0.67536%. A soma das quantidades dos lotes deve reconstruir a posição física em cada prefixo.

### 8.2. Concorrência entre BTC e ETH

Criar a fixture ETH correspondente, com os mesmos tempos/volume e preços BTC/50, em `data/fixtures/sprint12-eth-candles.json`. Criar `experiments/sprint12-multipar.json` derivado do canônico. Manter SMA somente em BTC; vincular EMA somente a ETH; incluir ambos os datasets; usar portfolio.exposure_fraction=0.03001 e limites por instrumento de 0.8 para ambos. As demais condições permanecem as do exemplo.

A competição passa a ocorrer no teto global de 30.01 USDT. A SMA recebe 0.000166 BTC e a EMA recebe 0.00420 ETH a 2400. As vendas ocorrem a 80000 e 1600, respectivamente. Os valores financeiros da tabela anterior e o resultado 989.95 USDT continuam iguais, com quatro fills e código 0. As quantidades BTC e ETH permanecem separadas. A exposição conjunta dura 120 segundos, entre as duas aberturas de entrada e saída.

### 8.3. Variantes obrigatórias

- Inverter a ordem de strategies, datasets, limites e eventos dentro das fronteiras. Identidade lógica, quantidades, prioridade, ledger e resultado permanecem iguais, com proveniência textual registrada separadamente.
- Trocar as prioridades do exemplo 8.1. As quantidades e contribuições dos titulares se invertem; o resultado físico continua 989.95 USDT nesta fixture, pois seus sinais coincidem.
- Reduzir o teto BTC de 0.03001 para 0.03, em `experiments/sprint12-limite.json`. A primeira compra permanece válida. A segunda foi aprovada por 0.000084 BTC, mas a taxa do primeiro fill reduz o teto a 29.9994024 USDT e causa rejeição EXPOSURE_INSTRUMENT na revalidação. A reserva é liberada; o SELL EMA posterior é recusado por ausência de lote. Esperar uma operação encerrada, caixa 993.32680 USDT, taxas 0.03320 USDT e código 2, conferindo o resultado observado.
- Exercitar cancelamento de BUY e SELL, propriedade incorreta, lote inexistente, saída de apenas um titular no mesmo ativo e restauração/consumo único de reserva.
- Exercitar gap protetivo preemptando SELL do próprio lote, ambos os toques STOP_FIRST, grupos com níveis diferentes no mesmo ativo e proteção ignorada no candle de entrada.
- Bloquear novas entradas por perda diária/drawdown global e de estratégia, inclusive igualdade, recuperação e virada UTC, mantendo saídas próprias habilitadas.
- Listagem tardia, deslistagem com lote aberto, marca antiga de ativo detido, ausência de preço, preço futuro, ausência inicial de um stream ativo, lacuna interna global e carteira sem observações elegíveis.
- Validar soma de alocações inválida, residual UNALLOCATED, limites concorrentes empatados, mínimos, caixa físico/atribuído insuficiente e patrimônio nulo de titular.

## 9. Relatórios, referências e identidade

O relatório distingue carteira física, lotes, subcontas e atribuições. Mostrar capital global uma vez, saldos totais/disponíveis/reservados por moeda, custos, risco comprometido, limites/excessos, arbitragem, motivos e contribuições reconciliadas. Curvas por estratégia são parcelas do patrimônio global. Comparações independentes continuam identificadas pelo modo da Sprint 11.

Associar operações, marcadores e linhas de compra/venda por lot_id e titular. Gerar um gráfico de candles por ativo, com sua unidade, e uma curva global em USDT. Indicadores por binding e detalhes de fills com mesmo timestamp conservam seus vínculos.

Mostrar exposição por instrumento e titular, frações sobre patrimônio, períodos de coexistência BTC/ETH, exposição conjunta e duração. Posições compradas simultâneas expõem a carteira conjuntamente a esses ativos. Não inferir hedge nem coeficiente de correlação estatística da fixture curta.

Criar referências isoladas HOLD_USDT e BUY_HOLD_BASKET. Ambas começam com o mesmo capital global e seguem o horizonte aceito. A cesta destina fração exata 1/N a cada ativo único da receita, investindo na primeira abertura elegível daquele ativo, com taxa/slippage e filtros. Usar razões exatas até o piso da quantidade. A parcela sem instrumento elegível permanece em caixa, com motivo e cobertura próprios. Não aplicar bloqueios, stops ou orçamento das estratégias à cesta. Em carteira sem observações, desempenho fica indisponível. No canônico de um BTC, a cesta compra 0.00999 BTC, conserva 0.001 USDT e termina com patrimônio bruto 799.201 USDT.

Gerar **15 artefatos**: manifest.json, events.jsonl, report.json, ledger.jsonl, reservations.jsonl, risk.jsonl, equity.csv, trades.csv, metrics.csv, benchmarks.csv, allocations.csv, lots.csv, contributions.csv, exposure.csv e report.md. O HTML é emitido em stdout, fora do diretório exclusivo de artefatos.

O ledger schema 7 separa account_scope PHYSICAL e ATTRIBUTION. Somente linhas PHYSICAL movem os totais físicos; linhas ATTRIBUTION reconstruem titularidade/subcontas e não são somadas novamente ao caixa global. A atribuição inicial transfere orçamento de UNALLOCATED para os titulares sem criar novo capital. Cada movimento identifica proprietário, lote, ativo, ordem, fill, fase e sequência global. Pode haver linhas por conta sob um transaction_id comum; seus deltas devem reconstruir caixa/ativos físicos e atribuições. reservations.jsonl reconstrói compromissos físicos/virtuais e seus detentores sem duplicação. allocations.csv descreve atribuições e saldos por titular; lots.csv descreve lotes e vínculos; contributions.csv projeta PnL/patrimônio por ponto/titular; exposure.csv projeta exposição por ponto/instrumento/titular. Todas são projeções do mesmo estado auditável.

Manifesto e identidade lógica incluem configuração normalizada, catálogo completo/hash, datasets associados aos símbolos, estratégia/versão/parâmetros, alocações, prioridades, limites e políticas de relógio/arbitragem/marcação/risco, código/assets e Python. Listas equivalentes têm ordem canônica e os caminhos de saída/relógio de parede ficam fora da identidade. Registrar hash original da receita como proveniência distinta. Repetição da mesma entrada deve produzir artefatos e HTML idênticos por bytes.

Usar JSON estrito, decimais em strings, UTC e indisponibilidades nulas com motivo. Validar entrada e diretório exclusivo antes da gravação. Preservar INCOMPLETE em falha parcial e publicar manifesto por último. Códigos são 0 para conclusão sem rejeições/pendências, 2 para rejeições/não execuções/indisponibilidade previstas e 1 para entrada inválida, interrupção ou falha técnica.

## 10. Entregáveis e validação futura

Entregar coordenador e ledger compartilhados, API de fronteiras, configuração schema 7, comando carteira, reservas/propriedade, limites, relatórios, fixtures/receitas e testes de comportamento. Atualizar README e planejamento. Criar `docs/sprint12-glossario.md` e `docs/sprint12-validacao.md`, documentando decisões, fórmulas, unidades, esperado/observado, comandos, inspeção visual, limitações e pendências.

Na raiz do projeto, usar `.venv` existente ou criá-la com `python3 -m venv .venv`. Conferir versão concreta e dependências. As receitas abaixo são futuras e exigem a implementação desta etapa.

```bash
source .venv/bin/activate
python --version
python -m unittest discover -s tests -v
python -m replayquant --help
python -m replayquant executar --help
python -m replayquant comparar --help
python -m replayquant demonstrar --formato json
python -m replayquant demonstrar --risco --estrategia sma --formato json
```

Após implementar, a ajuda e os exemplos canônico/multipar devem retornar 0. A variante de limite deve retornar 2. Capturar cada retorno individualmente, sem inferir sucesso pelo último comando.

```bash
python -m replayquant carteira --help
sprint12_dir=$(mktemp -d)
python -m replayquant carteira --config experiments/sprint12-compartilhada.json --saida "$sprint12_dir/compartilhada" --formato html > "$sprint12_dir/compartilhada.html"
python -m replayquant carteira --config experiments/sprint12-multipar.json --saida "$sprint12_dir/multipar" --formato html > "$sprint12_dir/multipar.html"
python -m replayquant carteira --config experiments/sprint12-limite.json --saida "$sprint12_dir/limite" --formato json > "$sprint12_dir/limite.json"
python -m replayquant carteira --config experiments/sprint12-compartilhada.json --saida "$sprint12_dir/repeticao" --analise --formato html > "$sprint12_dir/repeticao.html"
python -m replayquant comparar --config experiments/sprint11-matriz.json --saida "$sprint12_dir/matriz-legada" --formato json > "$sprint12_dir/matriz-legada.json"
python -m unittest discover -s tests -v
node --check replayquant/assets/chart.js
node --check replayquant/assets/equity.js
node --check replayquant/assets/indicators.js
git diff --check
```

A comparação legada da Sprint 11 retorna 2 pelos casos já documentados. Conferir também os individuais e exemplos expandidos das Sprints 07, 09 e 10. Comparar os 15 artefatos/HTML repetidos por bytes e as receitas permutadas por identidade lógica/eventos, preservando diferenças de proveniência. Testar os quatro formatos, outra cwd com caminhos relativos à receita, saída existente e falha de escrita.

## 11. Critérios de aceite

1. Um caixa físico e posições por ativo reconciliam com atribuições e lotes em cada prefixo. Reservas não duplicam patrimônio nem capacidade de compra.
2. Os exemplos 8.1 e 8.2 produzem quatro fills, dois lotes encerrados, caixa 989.95 USDT, taxas 0.05 e código 0, com quantidades e contribuições exatas.
3. Prioridades e desempates são auditáveis. Permutar arquivos/listas/eventos de uma fronteira preserva a política e a identidade lógica. Trocar prioridade produz a mudança documentada de titularidade econômica.
4. Uma estratégia vende somente seu lote. Cancelamento, transferência de reserva e proteção de um lote não consomem nem liberam recursos de outro.
5. Dimensionamento/revalidação aplicam limites em três níveis, incluindo compromissos pendentes, orçamento físico/atribuído e risco aberto. A variante 0.03 reproduz a rejeição pós-taxa sem redimensionar.
6. Sinais/reservas anteriores não usam OPEN futuro ou OHLC indisponível. Arquivo e API global têm paridade. Duplicata é inócua, conflito/falha técnica preserva estado e indicadores.
7. Prioridades entre ranges, sinais, gaps, SELL e BUY são conferidas, inclusive múltiplos lotes no mesmo ativo e preços de proteção diferentes.
8. Bloqueios e marcação obedecem ao relógio global; idade de preço, catálogo, lacunas e fronteiras de disponibilidade têm motivos e cobertura explícitos. Posição aberta permanece identificada e atribuída.
9. Realizado, não realizado, taxas, contribuições e curvas reconciliam com o total. Benchmarks usam capital/horizonte próprios comparáveis. Exposição conjunta aparece sem inferência de hedge.
10. Schemas/comandos anteriores conservam seus contratos, unidades e resultados. A matriz independente permanece identificável e executável.
11. Os 15 artefatos e quatro formatos incluem políticas, unidades, titularidade e limitações. HTML offline é inspecionado em desktop, tela estreita, impressão e sem JavaScript.
12. Validação/glossário/README registram comandos realmente executados e esperado/observado. Amostra negativa ou ausência de trades são resultados válidos de correção.

## 12. Prompt autossuficiente de execução

Copiar o bloco inteiro para implementar a etapa. Os contratos completos estão nas seções 1 a 11 deste documento versionado e devem ser lidos antes de alterar o projeto.

```text
Implemente a Sprint 12 — Carteira compartilhada do ReplayQuant em
/home/cams7/Dev/Cripto_Tests/replayquant. Evolua o projeto até concluir implementação,
exemplos, testes e documentação desta etapa.

Inspecione git status, HEAD, AGENTS.md aplicáveis e alterações existentes. A referência
consultada é 82128c8. Preserve trabalho existente e posterior. Leia integralmente
docs/sprint12.md, seções 1 a 11, docs/planejamento.md e contratos/validações anteriores,
especialmente Sprints 09 a 11. Confira a suíte e comandos de entrada da seção 10.
Registre lacunas essenciais antes do trabalho dependente. Use ambiente isolado,
Python >=3.11, biblioteca padrão e unittest, com versão concreta registrada.

Implemente schema 7 mode SHARED_PORTFOLIO e comando carteira --config --saida --formato,
com análise obrigatória e --analise redundante. Use o JSON completo da seção 7, catálogo
imutável da Sprint 11, caminhos relativos à receita, bindings e prioridades explícitos.
Valide JSON estrito e API, tipos/faixas/UTC, moedas, indicadores, soma exata de alocações,
referências e ausência de filtros conflitantes. Preserve schemas 1/2/4/5/6, executar,
comparar e seus resultados.

Implemente caixa físico USDT único, posição física por base e lotes virtuais por
strategy_id/instrumento. Atribua orçamento inicial por fração, com residual UNALLOCATED,
sem empréstimo ou redistribuição automática. Indicadores são instâncias por estratégia/par.
Permita um lote e uma intenção comum por binding, com múltiplos titulares no mesmo ativo.
Generalize o ledger e reaproveite a aritmética existente. Cada fill tem proprietário,
lote, instrumento, referência, preço efetivo, taxa, fase e sequência global.

Aplique as identidades da seção 3. Reconcilie caixa físico com subcontas, ativos com
lotes e reservas compartilhadas com seus detentores. Uma SELL encerra apenas o lote
próprio. Rejeite OWNERSHIP_MISMATCH ou INSUFFICIENT_ASSET conforme o caso. CANCEL libera
ou restaura somente a reserva própria. Uma proteção preempta somente a SELL do seu lote.
Guarde base de custo, realizado/não realizado e contribuições por titular. Use o capital
global inicial como denominador das contribuições percentuais.

Implemente relógio global e API equivalente a on_boundary(at, closes, openings), seguindo
as sete fases da seção 4. Marcas CLOSE comuns, saídas OHLC, indicadores/sinais, SELL e
BUY por prioridade precedem a publicação do próximo lote OPEN. Depois vêm gaps protetivos,
SELL e revalidação BUY. Use prioridade numérica crescente, strategy_id, símbolo e IDs
como desempates estáveis. Registre ALLOCATED_BUDGETS_V1 e BOUNDARY_MARKS_V1. Não exponha
aberturas futuras ao dimensionamento no fechamento nem extremos como trajetória agregada.
Mantenha STOP_FIRST, proteção a partir do próximo candle e reentrada vedada por binding.

Prepare a fronteira em estado isolado. Duplicação idêntica é inócua, conflito ou falha
não compromete parte dela. DATA_GAP é resultado controlado que conserva fechamentos e
sinais válidos antes do OPEN faltante. A política GLOBAL_GAP_INTERRUPT_V1 interrompe toda
a carteira antes de consumir um lote OPEN incompleto. Respeite catálogo, janela e idade
de marcas de ativos detidos, com coberturas/motivos. Finalização normal libera reservas
sem liquidar lotes. Interrupção conserva compromissos. Ativo indisponível permanece
atribuído e marcado no último preço, com proteção indisponível explícita.

Implemente os seis candidatos exatos da seção 5, com risco de entrada sobre P_i,
risco aberto global e exposições de carteira/instrumento/estratégia incluindo pendências.
Use o menor caixa disponível físico/atribuído. Piso por step e mínimos não aumentam lote.
Reserve uma única despesa potencial. Revalide quantidade/orçamento/S/T congelados,
substituindo apenas o próprio compromisso, respeitando demais reservas e custos prévios.
Use motivos e precedência documentados, bloqueios diário/drawdown globais e próprios,
sem impedir saídas elegíveis. Não redimensione na abertura nem liquide excessos à força.

Crie as fixtures de oito candles e três configurações das seções 7 e 8. No canônico,
SMA/EMA compram BTC a 120000 e vendem a 80000. Quantidades 0.000166 e 0.000084, devido
à prioridade e teto BTC de 3.001%. Desembolsos 19.93992 e 10.09008 USDT, recebimentos
13.26672 e 6.71328, PnL -6.67320 e -3.37680. Caixa final 989.95, taxas 0.05, BTC zero,
retorno global -1.005% e código 0. Reconcilie atribuições finais 493.32680 e 496.62320.
No multipar, SMA/BTC e EMA/ETH competem pelo teto global de 3.001%, com 0.000166 BTC e
0.00420 ETH, mesmos valores financeiros e 120 segundos de exposição conjunta. No limite
BTC 3%, a segunda BUY é rejeitada por EXPOSURE_INSTRUMENT após a taxa do primeiro fill;
libere a reserva, confira caixa 993.32680, taxas 0.03320 e código 2. Confira as demais variantes da seção 8.3.

Gere os 15 artefatos da seção 9 com identidade por conteúdo, proveniência original,
prioridades, políticas, catálogo, unidades e cobertura. Preserve diretório exclusivo e
INCOMPLETE até o manifesto final. Exponha custos, lotes, atribuições/contribuições,
reservas, risco, excessos e exposição conjunta. Implemente HOLD_USDT e BUY_HOLD_BASKET
isolados com mesmo capital/horizonte e filtros, conforme seção 9. Não some retornos
próprios como retorno global nem agregue curvas de comparar numa carteira compartilhada.

Atualize README, planejamento e documentação pertinente. Crie docs/sprint12-glossario.md
e docs/sprint12-validacao.md. Verifique os doze critérios da seção 11, propriedade,
concorrência lógica, limites, cancelamentos, proteções, lacunas, causalidade, permutações,
rollback, idempotência, falha de escrita e reconciliação em prefixos. Execute e registre
cada comando da seção 10 e os códigos esperados, compare repetições e formatos, confira
as regressões e exemplos expandidos anteriores. Inspecione HTML offline, desktop, tela
estreita, impressão e alternativa sem JavaScript.

Corrija falhas no escopo e conclua a entrega. Não antecipe dados reais, banco, parciais,
margem, novas estratégias/frequências, otimização, paralelismo ou negociação conectada.
No registro final informe arquivos alterados, decisões de modelos, ambiente, comandos
efetivamente executados, esperado/observado, limitações e pendências. Verificações não
executadas permanecem identificadas como pendentes.
```
