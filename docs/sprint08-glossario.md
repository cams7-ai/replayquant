# Sprint 08 — Glossário

| Conceito | Significado no ReplayQuant |
| --- | --- |
| Ledger | Registro imutável do saldo inicial e dos movimentos de cada preenchimento, separado por carteira e unidade |
| Projeção de saldos | Reconstrução de caixa e BTC somando os deltas do ledger; uma taxa já incluída no delta não é debitada novamente |
| Base de custo | Bruto pago pela posição mais a taxa da compra; permanece vinculado ao lote até sua venda integral |
| Lote | Posição de quantidade fixa aberta por uma compra e identificada por sua execução |
| Trade encerrado | Compra e venda integral do mesmo lote, ambas preenchidas; sinal ou ordem não executada não forma trade |
| Realizado | Recebimento da venda após taxa menos base de custo; soma dos resultados dos trades encerrados |
| Não realizado bruto | Valor da posição ao preço disponível menos sua base de custo; pode existir sem venda |
| Patrimônio bruto marcado | Caixa total mais BTC vezes o preço de marcação; já reflete custos pagos, mas não custos de saída ainda não incorridos |
| Liquidação hipotética | Cenário de patrimônio descontando slippage/taxa de uma saída ao preço disponível; não altera carteira nem gera fill |
| Marcação a mercado | Consulta que avalia a posição com open ou close já liberado; não usa o preço efetivo do fill como marca e não cria movimento |
| Curva patrimonial | Pontos INITIAL, OPEN, FILL e CLOSE, conservando inclusive alterações diferentes com mesmo timestamp |
| Pico | Maior patrimônio observado até um ponto; igualdade fora de drawdown atualiza a âncora para o ponto mais recente |
| Vale | Menor patrimônio do episódio de drawdown, com sequência que permite distinguir eventos no mesmo horário |
| Drawdown | Queda do patrimônio em relação ao pico anterior, em USDT ou percentual; maior percentual e maior queda absoluta podem pertencer a episódios distintos |
| Recuperação | Primeiro retorno ao pico anterior ou acima dele; episódio não recuperado só tem duração observada até o fim aceito |
| Expectativa amostral | Média aritmética dos lucros líquidos dos trades encerrados em USDT/TRADE; não é previsão de lucro |
| Taxa de acerto | Ganhos divididos por trades encerrados; sem trades é indisponível, e empates entram no denominador |
| Exposição temporal | Segundos efetivamente em posição sobre o horizonte total, incluindo aquecimento no denominador |
| Benchmark | Carteira virtual de referência, independente da estratégia, com mesmo capital inicial e período aceito |
| HOLD_USDT | Manter caixa em USDT sem juros; não pressupõe equivalência garantida ao dólar |
| BUY_HOLD_BTC | Comprar na primeira abertura com custos, quantidade com piso e resíduo de caixa; manter a posição até o fim |
| Quantum | Passo ilustrativo de 0.000000000001 BTC usado no piso da quantidade do benchmark; não é regra de exchange |
| Retorno do trade | Lucro líquido dividido pelo desembolso da compra, incluindo sua taxa |
| Retorno da carteira | Variação do patrimônio bruto em relação ao capital inicial; tem denominador diferente do trade |
| Pontos percentuais | Diferença entre dois percentuais de retorno, distinta de uma variação percentual relativa |
| Prefixo aceito | Dados/eventos processados antes da lacuna; análise parcial e benchmarks encerram nesse mesmo trecho |
| Reconciliação | Conferência independente de movimentos, saldos, bases de custo e da identidade patrimônio = capital + realizado + não realizado |
| Razão exata | Numerador/denominador preservados antes de arredondar a apresentação para 12 casas HALF_EVEN |
| Eixo por evento | Representação visual que dá posição distinta a cada ponto, sem inventar horários para alterações de mesmo timestamp |

Contratos completos em [sprint08.md](sprint08.md), com uso no [README](../README.md)
e resultados efetivamente observados no [registro de validação](sprint08-validacao.md).
