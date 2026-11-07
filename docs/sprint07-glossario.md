# Sprint 07 — Glossário

| Conceito | Significado no ReplayQuant |
| --- | --- |
| SMA | Média móvel simples dos últimos fechamentos de uma janela; cada preço tem o mesmo peso |
| Janela | Número inteiro de candles fechados usados no cálculo; curta é menor que longa |
| Aquecimento | Histórico necessário para calcular e comparar médias; a primeira comparação exige longa + 1 candles contíguos |
| Razão exata | Numerador/denominador inteiro sem arredondamento; decide o cruzamento mesmo abaixo da precisão exibida |
| Igualdade | Médias com o mesmo valor exato; igualdade atual não sinaliza, anterior pode iniciar cruzamento |
| Cruzamento | Mudança de relação entre médias anterior/atual com desigualdades explícitas; não se repete por permanência |
| Causalidade | Decisão usa somente dados liberados até seu evento; arquivo carregado não equivale a informação disponível |
| Avaliação | Registro do indicador em cada fechamento aceito, inclusive aquecimento e ausência de cruzamento |
| Sinal | Cruzamento matemático BUY/SELL, independente da carteira e da aprovação |
| Decisão | Verificação de pendência, posição e caixa; pode bloquear um sinal sem criar ordem |
| Intenção | Vínculo identificado entre decisão aprovada e ordem; não é execução nem muda saldo |
| Pendência | Ordem NEW aguardando abertura elegível; impede outra intenção e não reserva caixa nesta etapa |
| Slippage | Fração adversa incorporada ao preço: multiplica open por 1+a na compra e 1-a na venda |
| Taxa | Custo em USDT calculado sobre preço efetivo vezes quantidade; cobrado apenas no preenchimento |
| Sequência lógica | seq distingue eventos ordenados que podem compartilhar timestamp nominal |
| Latência zero | Convenção que permite executar na abertura seguinte ao sinal, com sequência posterior mesmo no mesmo horário |
| Lacuna | Ausência do próximo intervalo esperado; interrompe antes de processar o candle posterior |
| Prefixo causal | Eventos aceitos anteriores a uma fronteira; alterações futuras preservam seu conteúdo, exceto hashes/IDs globais do experimento |
| Relatório parcial | Estado INTERRUPTED com diagnóstico e carteira/pendência preservadas; não representa replay concluído |
| NO_FUTURE_OPEN | Término normal sem abertura para uma ordem pendente, distinto de interrupção por DATA_GAP |

Veja a [estratégia](estrategias/sma.md), a [especificação](sprint07.md) e o
[glossário da Sprint 06](sprint06-glossario.md) para os contratos herdados.
