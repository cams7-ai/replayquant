# Sprint 06 — Glossário

| Termo | Significado neste projeto |
| --- | --- |
| Spot | Compra e venda de um ativo existente. O laboratório exige BTC disponível para vender e não usa margem ou alavancagem. |
| Base e cotação | Em BTCUSDT, BTC é o ativo base e USDT é a cotação. Preço é USDT/BTC; quantidade é BTC; caixa e taxas são USDT. |
| Candle OHLCV | Resumo de um intervalo: abertura, máximo, mínimo, fechamento e volume. Não revela a ordem dos preços dentro do minuto. |
| Intervalo `[início, fim)` | Inclui o começo, exclui o fim. Uma negociação no fim pertence ao intervalo seguinte. |
| Evento | Informação ou transição em uma sequência. `OPEN`, `CLOSE`, submissão e preenchimento são eventos distintos. |
| Replay | Reprocessamento de dados históricos ou fictícios conforme um relógio de simulação, liberando apenas a informação de cada fase. |
| Relógio simulado | Tempo derivado dos dados, sem usar a hora da máquina para decisões. |
| Timestamp e `seq` | Timestamp identifica o instante nominal; `seq` ordena eventos que podem ter o mesmo horário. |
| Disponibilidade | Instante em que a informação pode ser usada. `open` é liberado na abertura; OHLCV completo, no fechamento. |
| Causalidade | Uma decisão ou preenchimento não consulta dados que ainda não foram liberados pelo relógio. |
| Roteiro manual | Lista explícita de solicitações BUY/SELL associadas a fechamentos. Não é uma estratégia ou um indicador. |
| Ordem | Solicitação aceita ou recusada pelo simulador. Criá-la não é comprar ou vender; saldo ainda não muda. |
| Pendência | Ordem `NEW` esperando a próxima abertura. Uma segunda solicitação é recusada enquanto essa pendência existir. |
| Preenchimento | Execução fictícia confirmada, com preço, quantidade e taxa, que altera saldos uma única vez. |
| Taxa | Custo em USDT, calculado como preço × quantidade × alíquota. `0.001` é fração equivalente a 0,10%. |
| Slippage | Diferença de execução em relação a uma referência. Aqui é configurado como zero, sem modelar mercado real. |
| Spread | Diferença entre bid e ask. O laboratório não possui livro nem modelo próprio de spread. |
| Liquidez ilimitada | Hipótese didática de preenchimento total, sem usar o volume final para limitar a quantidade. Não é liquidez observada. |
| Caixa | Saldo em USDT. Comprar reduz caixa e aumenta BTC; essa redução isolada não é prejuízo realizado da ida e volta. |
| Posição | Quantidade de BTC mantida. Uma posição aberta não é liquidada artificialmente no fim dos dados. |
| Resultado líquido | Na ida e volta do exemplo, recebimento líquido da venda menos desembolso da compra: 100.899 − 100.1 = 0.799 USDT. |
| Atomicidade | Calcular e validar o novo estado por inteiro antes de efetivar débitos, créditos, taxas e registro de preenchimento. |
| Idempotência | Repetir o mesmo registro não repete seu efeito. Execução duplicada não cobra outra taxa nem move caixa novamente. |
| Conflito de ID | Mesmo identificador com conteúdo diferente. É erro, não uma nova operação autorizada. |
| Decimal | Representação decimal criada de texto, sem float financeiro intermediário. A precisão é finita e controlada localmente. |
| Hash SHA-256 | Identificador por conteúdo. Mudar bytes de dados, configuração ou código muda sua identificação. |
| Manifesto | Registro do conteúdo usado, runtime, políticas e modelo de execução, suficiente para identificar o experimento local. |
| Relatório HTML | Documento independente obtido com `--formato html`, com indicadores, tabelas e memória de cálculo. Pode ser salvo por redirecionamento de stdout e aberto no navegador para leitura, impressão ou PDF, sem conexão à internet. |
| `run_id` | Hash de hashes de entrada/código e versão Python. Não depende de hora real, diretório de saída ou commit Git. |
| `INCOMPLETE` | Marcador de gravação ainda não concluída ou que falhou. Artefatos com esse marcador não devem ser consumidos como persistência bem-sucedida. |

## Estados de ordem

- `NEW`: aceita, ainda não executada e sem débito/reserva.
- `FILLED`: executada integralmente no evento de abertura elegível.
- `REJECTED`: recusada na submissão ou revalidação, sem execução parcial.
- `UNEXECUTED`: aceita, mas sem abertura futura disponível até o fim do replay.

Os estados terminais não voltam a `NEW`. Uma repetição idêntica consulta o registro
existente. Não há cancelamento operacional, execução parcial ou recuperação de
estado após reiniciar o processo.

## Ausência não é zero

Sem preenchimentos, taxas zero são um valor conhecido. Já o resultado de uma ida
e volta inexistente não é calculado: aparece como `null` com
`NO_CLOSED_ROUND_TRIP`. Quando há preenchimentos mas o roteiro não corresponde a
exatamente uma compra e uma venda integral, usa-se `ROUND_TRIP_NOT_APPLICABLE`.
O laboratório não avalia lucro não realizado, patrimônio marcado ou desempenho de
estratégias nesta etapa.
