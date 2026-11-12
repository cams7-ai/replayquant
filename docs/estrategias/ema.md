# EMA_CROSS versão 1

Os parâmetros `short_window` e `long_window` são inteiros, com `1 <= short_window < long_window`. A versão 1 usa `SMA_SEED`. Cada janela N começa pela média simples dos seus primeiros N fechamentos. A EMA curta começa em sua própria janela e continua sendo atualizada enquanto a longa ainda aquece.

```text
alpha = 2 / (N + 1)
EMA_inicial = soma dos primeiros N fechamentos / N
EMA_t = alpha × close_t + (1 − alpha) × EMA_anterior
```

A EMA longa fica disponível após `long_window` fechamentos. Cruzamentos exigem `long_window + 1`. BUY exige curta anterior <= longa anterior e curta atual > longa atual. SELL exige curta anterior >= longa anterior e curta atual < longa atual. Igualdade atual e permanência no mesmo lado produzem `NO_CROSS`.

As recorrências e comparações usam `Fraction` construída dos preços decimais exatos. Cada valor exporta numerador, denominador, unidade USDT/BTC e apresentação com 12 casas HALF_EVEN. A apresentação não decide o sinal.

Com janelas 2/3 e a fixture comum, a quarta observação tem curta=longa=95000. Na quinta, curta=335000/3 e longa=107500, gerando BUY. Na sétima, curta=2375000/27 e longa=91875, gerando SELL. A janela 1 acompanha cada fechamento.

Uma semente diferente pode continuar influenciando valores depois da prontidão mínima. No experimento com janelas 9/21 e 0, 10 ou 50 candles anteriores ao mesmo sufixo, todos os 28 pontos comparáveis das duas comparações apresentaram alguma diferença exata nas médias. Os sinais desse trecho coincidiram. A implementação mantém razões exatas, cujo custo de memória e tamanho cresce com o histórico.

Configuração executável em `experiments/sprint10-ema.json`. O coordenador de risco, ledger, custos, reservas e proteções é compartilhado como implementação com as demais estratégias, em sessões independentes. Resultados e receita do experimento em [Validação](../sprint10-validacao.md).
