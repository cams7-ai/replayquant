# RSI_REVERSION versão 1

Os parâmetros são `period` inteiro >= 1 e limiares decimais `0 < oversold < overbought < 100`. A versão 1 usa `WILDER_SMA_SEED_FLAT_50`.

Para cada diferença entre fechamentos, ganho=max(delta,0) e perda=max(-delta,0). As primeiras N variações inicializam médias simples de ganho e perda, exigindo N+1 fechamentos. Depois, aplicar suavização de Wilder.

```text
ganho_médio_t = ((N − 1) × ganho_médio_anterior + ganho_t) / N
perda_média_t = ((N − 1) × perda_média_anterior + perda_t) / N
RSI = 100 × ganho_médio / (ganho_médio + perda_média)
```

Com perda média zero e ganho positivo, RSI=100. Com ganho médio zero e perda positiva, RSI=0. Com ambos zero, RSI=50 e diagnóstico `FLAT_SEED_OR_STATE`. O RSI é adimensional e sua apresentação usa pontos de 0 a 100.

BUY ocorre ao sair da sobrevenda, com RSI anterior <= oversold e RSI atual > oversold. SELL ocorre ao sair da sobrecompra, com RSI anterior >= overbought e RSI atual < overbought. Igualdade atual não sinaliza. O primeiro sinal possível exige N+2 fechamentos. Os predicados direcionais geram no máximo um sinal por fechamento.

Recorrências, limiares e comparações são razões exatas. Os campos `rsi` e `previous_rsi` usam pontos RSI. `avg_gain` e `avg_loss` usam USDT/BTC. `comparison` e `previous_comparison` comparam cada RSI aos limiares, com −1, 0 e 1. A apresentação decimal tem 12 casas HALF_EVEN. Prontidão, médias, valores anteriores/atuais, motivos e identidade ficam registrados.

Com período 2 e limiares 30/70, a fixture comum produz RSI 0, 200/3, 600/7, 40 e 600/31 a partir do terceiro fechamento. Há BUY no quarto e SELL no sexto. O gap da fixture comum faz a compra exceder o orçamento na abertura seguinte. Na fixture `sprint10-candles-rsi.json`, as duas ordens preenchem a 100000 e encerram uma operação com lucro zero.

A suavização conserva influência da inicialização. O experimento com período 14 encontrou diferenças exatas em todos os 40 pontos comparáveis usando históricos de 0 ou 10 candles contra a referência de 50. Os sinais desse trecho coincidiram. O indicador alimenta o coordenador de risco existente, que pode rejeitar seus sinais.

Configuração em `experiments/sprint10-rsi.json`. Resultados e limites em [Validação](../sprint10-validacao.md).
