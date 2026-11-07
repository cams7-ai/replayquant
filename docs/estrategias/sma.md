# Estratégia SMA_CROSS

Especificação: [Sprint 07](../sprint07.md). Implementação: `SMACross` em
`replayquant/strategies.py`, integrada por `SMASession` em `engine.py`.

## Parâmetros e histórico

`short_window=s` e `long_window=l` são inteiros estritos com `1 <= s < l`.
O indicador guarda no máximo os últimos `l` fechamentos em uma fila. Os valores
são `Fraction(Decimal)` exatos, sem arredondamento intermediário. A avaliação
anterior guarda a relação entre as médias; a primeira comparação exige `l+1`
candles fechados contíguos. Nenhum sinal aparece só porque a primeira média
calculável está acima ou abaixo da outra.

```text
SMA_s(k) = soma(C[k-s+1:k+1]) / s
SMA_l(k) = soma(C[k-l+1:k+1]) / l
BUY:  SMA_s(k-1) <= SMA_l(k-1) e SMA_s(k) > SMA_l(k)
SELL: SMA_s(k-1) >= SMA_l(k-1) e SMA_s(k) < SMA_l(k)
```

Igualdade atual não sinaliza. Igualdade anterior permite cruzamento em qualquer
sentido. Permanência não gera sinal. Avaliações mostram razões exatas e relação
-1/0/1; ausências são `null` com motivo de aquecimento. O indicador não recebe
fila futura, arquivo completo, ordens ou OHLCV ainda indisponível.

## Decisão, intenção e execução

O sinal matemático independe da posição. A decisão verifica pendência, posição
e caixa estimado, nessa ordem. Bloqueios usam `ORDER_PENDING`, `POSITION_OPEN`,
`INSUFFICIENT_ASSET` ou `INSUFFICIENT_CASH`, sem criar ordem. Aprovação cria
intenção e ordem `NEW` identificadas. Uma rejeição no preenchimento libera a
pendência, preserva a carteira e exige novo cruzamento para outra tentativa.

Execução ocorre na próxima abertura contígua após a submissão, inclusive no
mesmo timestamp nominal com sequência posterior. Com slippage `a` e taxa `f`:
compra usa `open*(1+a)`; venda usa `open*(1-a)`; bruto é preço vezes quantidade,
e taxa é bruto vezes `f`, em USDT. A compra debita bruto+taxa, a venda credita
bruto-taxa. Não deduzir slippage novamente. Não usar high/low/close/volume final
para preencher nem limitar preço efetivo aos extremos do candle.

## Dados, término e limites

Lacuna interrompe antes do candle posterior, sem alterar posição ou pendência.
Arquivo corrigido gera nova execução, nunca preenchimento retroativo na sessão
interrompida. Ausência de abertura futura no término normal deixa a ordem
`UNEXECUTED/NO_FUTURE_OPEN`; posição aberta não é liquidada ou marcada a mercado.

O modelo é Spot comprado, um instrumento fictício, quantidade fixa, preenchimento
total, liquidez ilimitada, latência zero e deduplicação local em memória. Não há
modelo de spread, risco, reservas, otimização, benchmark ou recuperação operacional.

Na fixture 2/3, o BUY no fechamento 12:04 preenche na abertura 12:04 a 100100;
o SELL no fechamento 12:07 preenche na abertura 12:07 a 99900. Para 0.001 BTC,
capital 1000, taxa/slippage 0.001: taxas 0.2, caixa final 999.6 e resultado -0.4
USDT. Isso demonstra correção temporal e financeira, sem evidenciar rentabilidade.
