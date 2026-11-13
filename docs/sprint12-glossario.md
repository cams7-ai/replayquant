# Glossário da Sprint 12 — Carteira compartilhada

| Termo | Significado no ReplayQuant |
| --- | --- |
| Caixa físico | Único saldo USDT. Apenas movimentos `PHYSICAL` do ledger o alteram. |
| Atribuição | Parte auditável do caixa/patrimônio pertencente a uma estratégia; linhas `ATTRIBUTION` não criam capital adicional. |
| UNALLOCATED | Residual inicial não alocado. Permanece em caixa e não financia compras das estratégias. |
| Binding | Instância independente de indicador e intenção por titular, origem, símbolo e intervalo. |
| Lote | Quantidade integral adquirida por um binding, com proprietário, custo com taxa, referências, stop/alvo e risco congelados. |
| Detentor de reserva | Ordem ou grupo protetivo que controla temporariamente um compromisso; não substitui o proprietário do lote. |
| Reserva compartilhada de base | Uma reserva por lote, compartilhada pelas duas pernas protetivas. Transferida à SELL comum e restaurada em cancelamento. |
| ALLOCATED_BUDGETS_V1 | Orçamentos iniciais por estratégia, sem empréstimo, realocação ou redistribuição de ganhos/perdas. |
| Arbitragem | Aprovação BUY por `(priority, strategy_id, symbol, signal_id)`, crescente. Não promete equidade econômica. |
| Capacidade comprometida | Posições às marcas comuns mais estimativas das BUY pendentes. A candidatura própria é substituída, não duplicada, na revalidação. |
| Risco aberto planejado | Soma das perdas estimadas de lotes e pendências até seus stops absolutos, com taxas. Não limita perdas efetivas em gaps. |
| Fronteira | Minuto global com fechamentos e aberturas tipados. Seu digest identifica conteúdo canônico e duplicatas numéricas equivalentes. |
| BOUNDARY_MARKS_V1 | Todas as marcas CLOSE são publicadas juntas; depois, todas as OPEN. Extremos OHLC não representam trajetória global. |
| BAR_CLOSE_RESOLUTION | Timestamp modelado para resolver proteção pelo range de candle já encerrado; STOP_FIRST quando ambos os níveis são tocados. |
| GLOBAL_GAP_INTERRUPT_V1 | Falta de abertura de qualquer stream ativo interrompe a carteira antes de publicar qualquer OPEN daquele lote. Conserva o prefixo CLOSE/sinais e suas reservas. |
| Contribuição | `PnL_i / capital_global_inicial × 100`. Sua soma reconstrói o retorno global. |
| Retorno próprio | `PnL_i / atribuição_inicial_i × 100`. Denominador diferente; não somar esses retornos. |
| Exposição conjunta | Intervalo entre observações com posições físicas positivas em mais de uma base. Não demonstra hedge ou correlação estatística. |
| KEEP_OPEN | Conserva lotes no término; libera reservas no fim normal e separa liquidação hipotética de operações efetivamente executadas. |
| Proteção indisponível | Lote conservado após fim do instrumento, sem nova cotação negociável; reserva base liberada e risco histórico preservado. |
| BUY_HOLD_BASKET | Referência independente, com capital global próprio e parcela exata `1/N` para cada ativo único, filtros, custos e horizonte aceito. |

Quantidades e volume usam moeda base; preços, médias e stops usam USDT/base; caixa, custo, patrimônio e PnL usam USDT; RSI usa pontos; idades/durações usam segundos. Decimais financeiros são textos nas exportações. Razões incluem numerador/denominador e apresentação com 12 casas; o arredondamento exibido não decide operações.
