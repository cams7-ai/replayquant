# Estratégia SMA_CROSS

Especificação: [Sprint 07](../sprint07.md). Implementação: `SMACross` em
`replayquant/strategies.py`, integrada por `SMASession` em `engine.py`.

As seções iniciais descrevem o caminho legado schema 2 da Sprint 07. A extensão modular schema 5 e o risco são detalhados ao final.

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

## Integração modular na Sprint 10

A estratégia compara médias simples de fechamentos contíguos de BTCUSDT. Os parâmetros `short_window` e `long_window` são inteiros, com `1 <= short_window < long_window`. A versão 1 usa a política `ROLLING_WINDOW` e aritmética racional exata.

`SMA_N = soma dos últimos N fechamentos / N`. Cada média fica disponível após N observações. A comparação com o estado anterior permite sinal a partir de `long_window + 1` fechamentos.

BUY exige curta anterior <= longa anterior e curta atual > longa atual. SELL exige curta anterior >= longa anterior e curta atual < longa atual. Igualdade atual e permanência no mesmo lado produzem `NO_CROSS`. As razões exatas decidem o cruzamento. Valores decimais de apresentação usam 12 casas e HALF_EVEN.

Com os fechamentos 100000, 90000, 80000, 100000, 120000, 100000 e 80000 e janelas 2/3, as médias no quarto ponto são ambas 90000. O quinto ponto tem curta 110000 e longa 100000, gerando BUY. O sétimo tem curta 90000 e longa 100000, gerando SELL.

Cada avaliação registra indicador pronto, sinal pronto, valores anteriores/atuais, motivo, candle, identidade e parâmetros. O sinal entra no mesmo coordenador de risco das demais estratégias. A ordem preenche apenas na próxima abertura elegível, após revalidação. Lacunas interrompem a sessão. Custos, reservas e saídas protetivas seguem a Sprint 09.

A janela finita elimina a influência de preços mais antigos quando há histórico comum suficiente para as médias atual e anterior. O experimento de aquecimento confirmou igualdade no sufixo comparável. Os exemplos são fictícios e descrevem a regra do indicador.

Configuração executável em `experiments/sprint10-sma.json`. Fórmulas e tabela de conferência em [Sprint 10](../sprint10.md). Resultados observados em [Validação](../sprint10-validacao.md).
