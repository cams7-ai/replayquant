# Glossário da Sprint 10

| Termo | Significado no ReplayQuant |
| --- | --- |
| Contrato de estratégia | Interface incremental que transforma candles fechados em avaliações e sinais |
| Registro | Mapeamento explícito de nome e versão para fábrica de novas instâncias |
| StrategySpec | Identidade imutável com nome, versão e parâmetros tipados |
| SMA | Média simples dos últimos N fechamentos, em USDT/BTC |
| EMA | Média móvel exponencial com alpha=2/(N+1) e semente SMA |
| Semente | Estado inicial do indicador, calculado do histórico disponível |
| Wilder | Suavização com peso 1/N para a nova observação |
| RSI | Razão entre ganhos médios e soma de ganhos/perdas médios, em pontos de 0 a 100 |
| Sobrevenda | Região RSI <= oversold. BUY exige sair dessa região para cima |
| Sobrecompra | Região RSI >= overbought. SELL exige sair dessa região para baixo |
| Aquecimento | Observações necessárias para calcular indicador e sua comparação anterior |
| Indicador pronto | Há valores atuais calculáveis |
| Sinal pronto | Há valores atuais e anteriores suficientes para testar cruzamento |
| Razão exata | Numerador/denominador usados no cálculo e na decisão |
| HALF_EVEN | Arredondamento de apresentação para o par mais próximo no empate |
| Sufixo comum | Mesmo trecho temporal comparado após históricos anteriores de tamanhos diferentes |
| Carteira independente | Sessão com capital, ordens, reservas e indicadores próprios |
| Revalidação | Verificação da entrada na abertura, preservando quantidade, stop, alvo e orçamento aprovados |
| WARMUP | Histórico insuficiente para testar o cruzamento |
| NO_CROSS | Indicadores disponíveis, sem cruzamento estrito atual |
| CROSS_UP / CROSS_DOWN | Cruzamento de médias para cima / para baixo |
| EXIT_OVERSOLD / EXIT_OVERBOUGHT | Saída direcional da região de sobrevenda / sobrecompra |
| FLAT_SEED_OR_STATE | Ganho e perda médios zero, com RSI convencional igual a 50 |

Consulte [Sprint 10](sprint10.md), [SMA](estrategias/sma.md), [EMA](estrategias/ema.md), [RSI](estrategias/rsi.md) e [Validação](sprint10-validacao.md).
