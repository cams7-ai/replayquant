# Sprint 09 — Glossário

| Termo | Significado no ReplayQuant |
| --- | --- |
| Orçamento de risco R | Patrimônio bruto marcado × fração de risco. É limite da perda **planejada** para aprovar a entrada, não teto garantido de perda realizada. |
| Perda unitária L | E×(1+f) − S×(1−f), em USDT/BTC. Inclui taxas de compra/venda; o slippage de saída é cenário adicional. |
| Candidatos de quantidade | Limites independentes por risco, exposição e saldo. O menor determina a candidata antes do piso. Empates são preservados. |
| Step | Incremento fictício de quantidade. Floor(q/step)×step difere de arredondar casas; 0.000003 é um passo válido. |
| Mínimo nocional | Menor bruto permitido para nova compra. Não autoriza aumentar a quantidade para superar o orçamento. |
| Exposição nominal | BTC × preço de referência, sem taxas. Patrimônio também inclui caixa total. |
| Caixa disponível | Parte do total ainda utilizável por outra ordem; não inclui recursos já reservados. |
| Reserva | Recursos comprometidos com ordem/grupo. Reservar transfere disponível para reservado, sem despesa ou perda patrimonial. |
| Titularidade | Identificação de quem pode consumir uma reserva. Transferir titularidade não move dinheiro total nem cria posição. |
| Liberação | Devolução dos recursos retidos ao disponível, sem taxa fictícia. Ocorre uma única vez por transição terminal. |
| Revalidação | Conferência na abertura real disponível, antes de preencher. R/S/T/q aprovados ficam congelados; violação rejeita e libera. |
| Complemento de caixa | Diferença entre desembolso efetivo e reserva. Só pode usar saldo livre real, após revalidar, sem consumir recursos de outra ordem. |
| Snapshot | Registro do estado disponível num evento: patrimônio, saldo livre, exposição, preço/idade, posição e bloqueios. |
| Preço antigo | Preço cuja idade excede o limite configurado. Ainda pode identificar a última marca aceita, sem se tornar preço negociável atual após lacuna. |
| Base diária parcial | Primeira observação positiva do dia após 00:00 UTC. A perda diária se refere a essa base, não a patrimônio inventado na meia-noite. |
| Bloqueio persistente | Estado que não é limpo pela recuperação de preço/patrimônio. Diário dura até a virada UTC; drawdown até o fim da sessão. |
| Grupo protetivo | Stop e alvo vinculados a um lote e a uma única reserva de BTC, sem duplicar a quantidade reservada por perna. |
| Stop | Saída a mercado simulada condicionada a preço adverso. Gap e slippage podem produzir execução abaixo do nível. |
| Alvo | Saída a mercado condicionada a toque favorável; não é uma limitada ou garantia de execução real. |
| Gap | Abertura além do gatilho. O modelo usa o preço de abertura conhecido como referência de venda. |
| STOP_FIRST | Convenção conservadora para um candle que toca stop e alvo. Não identifica qual ocorreu primeiro no mercado. |
| Ambiguidade OHLC | Máxima/mínima demonstram que níveis foram tocados, mas não sua sequência. O relatório registra essa incerteza. |
| Elegibilidade da proteção | A proteção começa na abertura seguinte ao candle de entrada. A janela anterior não recebe proteção neste modelo. |
| BAR_RANGE | Entrega do OHLC completo ao resolvedor de execução, antes de CLOSE alimentar o indicador. |
| BAR_CLOSE_RESOLUTION | Horário de saída modelado no fechamento do intervalo. O instante intraperíodo é desconhecido; duração/exposição são aproximações. |
| PROTECTION_TRIGGER | Evento que registra nível selecionado e marca causal antes do fill protetivo. Não expõe o caminho futuro à estratégia. |
| Reentrada no mesmo candle | Nova BUY decidida no fechamento do candle em que ocorreu saída. É bloqueada; requer sinal/solicitação posterior. |
| CANCELED | Pendência encerrada sem fill, por CANCEL manual ou prioridade protetiva. Não desfaz execuções anteriores. |
| Risco residual | Diferença entre proteção planejada e resultado possível: janela sem proteção, gaps, slippage e incerteza OHLC. |
| KEEP_OPEN | Mantém BTC no fim, sem venda forçada. O grupo termina e libera a reserva, sem alegar atuação após encerrar o experimento. |
| ACCEPTED_PREFIX | Escopo da análise antes de uma interrupção. Reservas e pendências continuam retidas no snapshot; não se preenche através da lacuna. |

## Exemplo conferível

P=1000 USDT, r=0.01, E=100 USDT/BTC, S=90, f=0.001. R=10 e
L=10.19 USDT/BTC; q_risco=1000/1019 BTC. Piso no step 0.001 resulta em
q=0.981 BTC. O desembolso reservado é 98.1981 USDT e a perda planejada é
9.99639 USDT.

Uma saída a 90 recebe 88.20171 USDT e realiza −9.99639 USDT. Um gap que executa
a 80 recebe 78.40152 e realiza −19.79658 USDT. A diferença não é erro contábil:
o preço não foi garantido pelo orçamento. As taxas já estão nesses fluxos e
não são debitadas novamente.

## API e precisão

Valores monetários são Decimal de strings. Razões e floor por incremento são
exatos; os 12 dígitos decimais exibidos não decidem operações. O contexto financeiro
local de precisão 40 rejeita inexatidão antes de comprometer a transição. Snapshots
de consulta não autorizam editar o estado privado da sessão. Reservas e ledger
podem ser reconstruídos desde a inicialização, sem acesso a dados externos.
