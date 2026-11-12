# Validação da Sprint 11 — Múltiplos pares e catálogo

## 1. Ambiente e entrada

Implementação verificada em 12/11/2026, partindo de HEAD **7cdd89a**, com a árvore inicialmente limpa. Foram lidos o planejamento, a especificação da Sprint 11 e os contratos anteriores pertinentes. A suíte de entrada passou com **151 testes**, registrada em `/tmp/replayquant-sprint11-base.log`.

Python efetivamente usado **3.12.14**, executado por `.venv/bin/python`. A implementação usa biblioteca padrão e `unittest`. Nenhuma dependência ou asset de terceiros foi instalado ou atualizado. A inspeção visual usou Playwright e Node já disponíveis no ambiente, com Chrome headless local. As verificações `node --check` usaram o Node do sistema.

## 2. Implementação e decisões

O catálogo é um snapshot imutável `Catalog`, com registros `Instrument`, filtros tipados, disponibilidade, data/origem das regras e classificação da hipótese. O conteúdo completo e seu hash participam da identidade. O exemplo usa `SYNTHETIC_ASSUMPTION`. `CURRENT_RULES_ASSUMED_FOR_PERIOD` continua explicitamente classificado como hipótese.

`CatalogConfig` estende o contrato de risco, resolve os filtros pelo catálogo e acrescenta `Window`. O schema 6 usa `mode: STRATEGY`, análise obrigatória e catálogo explícito. O parser legado de candles continua restrito a BTC quando chamado sem catálogo. O caminho novo resolve o instrumento no catálogo e valida o arquivo inteiro contra a configuração antes do recorte. Os registros Candle/Opening validam estrutura genérica, enquanto sessão e catálogo validam a autorização do instrumento.

`AssetBalance` contém `cash` e `asset_quantity`. O saldo legado `Balance` conserva o campo `btc` e oferece a quantidade genérica para o cálculo compartilhado. `after_fill`, ledger, risco e reservas continuam sendo o mesmo núcleo financeiro. O ledger recebe contexto da moeda base, e reservas de moeda divergente são recusadas. Não foi criado um motor ETH separado.

O schema 6 exporta quantidades e volume em base, preços em USDT/base, caixa/taxas em USDT e RSI em pontos. Médias de ganhos/perdas RSI também recebem a unidade USDT/base. Benchmarks novos usam BUY_HOLD_ASSET, enquanto os caminhos anteriores conservam BUY_HOLD_BTC. CSVs novos incluem origem, símbolo, base/cotação e intervalo. O ledger interno mantém a política financeira anterior e a projeção nova usa schema 6.

A identidade individual schema 6 usa configuração resolvida canônica, catálogo completo, dados, estratégia, políticas, Python e código/assets. Isso permite ao filho de matriz e ao individual equivalente terem o mesmo run_id, manifesto e eventos. Os caminhos legados preservam o hash de configuração por bytes. Na matriz, a identidade lógica usa a composição canônica dos filhos. `recipe_hash` registra separadamente os bytes da receita original. Listas reordenadas conservam o resultado lógico e mudam essa proveniência.

A rotina `compare` executa sequencialmente sessões independentes. O ranking usa razões exatas e grupos com condições comparáveis. Sua elegibilidade exige FULL, COMPLETED e código 0. A saída conserva linhas excluídas, com ranking nulo e motivo. Não há agregação patrimonial das sessões nem seleção automática de parâmetros.

A cobertura registra janela solicitada, disponibilidade, interseção elegível, candles esperados/aceitos/excluídos, duplicatas, lacunas e motivos de borda. Um resultado sem observações tem UNAVAILABLE, código 2 e métricas de desempenho nulas. O caixa é conservado, sem benchmark comprado. Finalizar uma sessão após abertura ainda não fechada é recusado, preservando o estado aceito.

## 3. Comandos realmente executados

A rodada final está em **`/tmp/replayquant-sprint11-final-9tyc0obx`**. Seu `commands.json` contém argumentos completos, códigos esperados/observados e stderr de **37 comandos**, capturados individualmente. Saídas dos cenários foram preservadas em arquivos por formato. As receitas reproduzíveis estão na seção 9 da [especificação](sprint11.md) e no README.

| Grupo executado | Quantidade | Esperado e observado |
| --- | --- | --- |
| Versão Python e ajudas principal, executar e comparar | 4 | 0 |
| Demonstrações manual/SMA, com e sem risco, JSON | 4 | 0 |
| Individual ETH/RSI nos quatro formatos e repetição com `--analise` | 5 | 0 |
| Matriz canônica nos quatro formatos e repetição HTML | 5 | 2 |
| Matriz parcial HTML/JSON | 2 | 2 |
| Matriz com listas reordenadas e caminhos absolutos equivalentes | 1 | 2 |
| Instrumento sem candles elegíveis nos quatro formatos | 4 | 2 |
| Schema 6 sem catálogo e diretório de saída já existente | 2 | 1 |
| Exemplos expandidos Sprint 07, Sprint 09 equivalente e SMA/EMA/RSI Sprint 10, HTML | 5 | 0 |
| Sintaxe de chart.js, equity.js e indicators.js | 3 | 0 |
| `python -m unittest discover -s tests -v` | 1 | 0, 170 testes |
| `git diff --check` | 1 | 0 |

O código 2 das matrizes era esperado porque há filhos com ordens não executadas/rejeitadas. Os erros de catálogo ausente e saída existente retornaram 1 sem publicar nova execução. O primeiro erro não criou diretório. Uma falha de escrita foi injetada nos testes, preservando INCOMPLETE e impedindo manifesto final de sucesso.

## 4. Matriz canônica e memória financeira

Foram executadas seis combinações, todas com capital próprio de 1000 USDT, sete candles de 01/01/2026 12:00–12:07 UTC, taxa de 0.001 e slippage zero. As séries usam o último fechamento como abertura seguinte. ETH é a transformação didática BTC/50. Os resultados esperados na especificação coincidiram com os observados.

| Combinação | Fills / trades encerrados | Caixa USDT | Posição final | Patrimônio bruto USDT | Retorno % | Drawdown máximo % | Código / ranking |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SMA 2/3 / BTC | 1 / 0 | 980.06008 | 0.000166 BTC | 993.34008 | −0.665992 | 0.665992 | 2 / nulo |
| EMA 2/3 / BTC | 1 / 0 | 980.06008 | 0.000166 BTC | 993.34008 | −0.665992 | 0.665992 | 2 / nulo |
| RSI 2, 30/70 / BTC | 2 / 1 | 999.9602 | 0 BTC | 999.9602 | −0.00398 | 0.398412247658 | 0 / 1 |
| SMA 2/3 / ETH | 1 / 0 | 980.06008 | 0.00830 ETH | 993.34008 | −0.665992 | 0.665992 | 2 / nulo |
| EMA 2/3 / ETH | 1 / 0 | 980.06008 | 0.00830 ETH | 993.34008 | −0.665992 | 0.665992 | 2 / nulo |
| RSI 2, 30/70 / ETH | 2 / 1 | 999.96012 | 0 ETH | 999.96012 | −0.003988 | 0.399209911120 | 0 / 2 |

SMA/EMA sinalizam BUY às 12:05 e SELL às 12:07. A compra BTC ocorre a 120000, com stop 60000 e orçamento 10 USDT. Perda unitária `120000×1.001 − 60000×0.999 = 60180 USDT/BTC`, piso q=0.000166 BTC, bruto 19.92 e taxa 0.01992 USDT. O caixa fica 980.06008. A marca final de 80000 dá posição de 13.28 USDT e patrimônio 993.34008. ETH usa preço 2400, stop 1200, perda unitária 1203.6 e piso 0.00830 ETH, com os mesmos valores financeiros. A saída final fica UNEXECUTED/NO_FUTURE_OPEN, com posição conservada e reserva liberada.

RSI compra às 12:04 e vende às 12:06. BTC negocia a 100000 nas duas pontas, com perda unitária planejada 50150 e piso de 10/50150 para 0.000199 BTC. Cada ponta tem bruto 19.9 e taxa 0.0199, totalizando −0.0398 USDT. ETH negocia a 2000 nas duas pontas, com perda unitária 1003 e piso de 10/1003 para 0.00997 ETH. Cada bruto é 19.94 e cada taxa 0.01994, totalizando −0.03988 USDT. Filtros diferentes explicam a diferença residual entre os pares.

As seis reconciliações financeiras e de reservas passaram. Os benchmarks têm capital próprio, filtros do instrumento e o mesmo horizonte aceito. Somente as duas linhas RSI entraram no ranking. Um teste adicional confirmou posições 1, 1 e 3 para empate exato, com ordenação estável dos empatados.

## 5. Disponibilidade, isolamento e casos adversos

O catálogo parcial restringe ETH a `[12:02,12:06)` UTC, aceitando quatro candles. O histórico anterior foi excluído do aquecimento. Todos os resultados ETH têm cobertura PARTIAL da janela solicitada e ranking nulo.

| Estratégia ETH parcial | Avaliações | Sinais / fills | Caixa USDT | Código / motivo |
| --- | --- | --- | --- | --- |
| SMA 2/3 | 4 | 0 / 0 | 1000 | 0, sem cruzamento |
| EMA 2/3 | 4 | 0 / 0 | 1000 | 0, sem cruzamento |
| RSI 2, 30/70 | 4 | 1 SELL / 0 | 1000 | 2, INSUFFICIENT_ASSET |

O RSI parcial fica calculável às 12:05 com 100 e às 12:06 cai para 50, emitindo SELL sem posição. Os resultados financeiros BTC coincidiram com a matriz canônica, embora o hash de catálogo alterado modifique identidades. O comparativo parcial retornou 2.

Os 19 testes novos cobrem ainda os casos abaixo, além das regressões anteriores.

- JSON/API inválidos, catálogo duplicado, cotação incompatível, intervalos e datas inválidos, campos inesperados e filtros divergentes da configuração resolvida.
- Alteração de entrada não usada do catálogo afetando identidade, hipóteses de regras atuais e terceiro símbolo SOLUSDT incluído somente por catálogo e dados.
- Arquivo BTC trocado por ETH, candle estrangeiro no fim do arquivo, evento estrangeiro incremental e abertura fora da disponibilidade, sem mutação aceita.
- Posição aberta ao fim de disponibilidade, liberação de reserva, pendência com INSTRUMENT_UNAVAILABLE e proteção BAR_CLOSE_RESOLUTION no fechamento do último intervalo válido.
- Lacuna interna com posição/reserva retida, análise do prefixo, exclusão de borda, contagem de duplicatas e sinais sem repetição.
- Preço com idade exatamente 60 segundos aceito, 61 segundos rejeitado e preço futuro inválido. Contexto Decimal externo hostil foi preservado.
- Sessões BTC/ETH intercaladas, replay incremental igual ao arquivo, prefixo invariante a extremos futuros e falha injetada sem aceitar estado parcial.
- Cancelamento idempotente com liberação, unidades em HTML/Markdown/CSV, escape de metadados, saída existente e falha de escrita.

Uma variante com disponibilidade ETH somente em fevereiro foi executada contra a janela de janeiro. O resultado foi UNAVAILABLE, código 2, saldo inicial conservado, nenhuma ordem/fill e métricas de desempenho nulas com motivo. Foram gerados os onze arquivos, inclusive CSVs vazios de trades e ledger sem eventos inventados. Nenhum benchmark comprou.

## 6. Reprodução, identidade e formatos

O individual ETH/RSI produziu o mesmo manifesto, run_id, eventos e relatório do filho correspondente da matriz. A repetição individual com `--analise` gerou onze arquivos idênticos por bytes. Os quatro formatos de stdout foram executados com os mesmos valores financeiros.

A matriz completa produziu **70 arquivos**, quatro resumos e onze arquivos em cada um dos seis diretórios de filhos. Os formatos HTML/JSON/Markdown/texto e a repetição HTML tiveram artefatos iguais por bytes. A saída HTML repetida também foi idêntica. A matriz parcial e a variante UNAVAILABLE foram repetidas em JSON com a mesma igualdade aplicável aos seus artefatos.

A receita com datasets/estratégias invertidos e caminhos equivalentes absolutos preservou matrix_id, comparison.json, ranking e todos os artefatos dos filhos. O recipe_hash original ficou diferente. O teste de CLI em outra cwd passou usando PYTHONPATH para localizar o pacote e a receita por caminho absoluto. Os caminhos internos foram resolvidos em relação à receita.

As exportações CSV schema 6 incluem os metadados do instrumento. A ordem de gravação conserva INCOMPLETE até terminar todos os filhos e o manifesto. A precedência agregada dos códigos é 1, depois 2, depois 0.

## 7. Regressões dos exemplos expandidos

Os cinco comandos HTML retornaram 0. Posições finais ficaram zeradas e os valores abaixo coincidiram com os exemplos já documentados, respeitando seus parâmetros próprios.

| Configuração expandida | Caixa final USDT | Lucro líquido USDT |
| --- | --- | --- |
| Sprint 07 SMA | 1000.90155066834 | 0.90155066834 |
| Sprint 09 SMA equivalente | 1000.90155066834 | 0.90155066834 |
| Sprint 10 SMA | 1000.42208230 | 0.42208230 |
| Sprint 10 EMA | 1000.71085163730 | 0.71085163730 |
| Sprint 10 RSI | 1001.93754109984 | 1.93754109984 |

Os caminhos legados conservaram os payloads BTC e filtros/custos existentes. Hashes de código e IDs refletem a implementação atual.

## 8. Inspeção visual e offline

Os HTMLs individual ETH, matriz canônica, matriz parcial e indisponibilidade foram abertos no Chrome headless. Houve **zero exceções JavaScript e zero requisições HTTP externas**. Desktop de 1400×1000 e tela de 390×900 foram conferidos. `scrollWidth` coincidiu com a largura da página nos dois tamanhos. Tabelas largas têm rolagem interna.

Foram inspecionados rótulos ETH/USDT, tabela de metadados/cobertura, gráfico RSI e tabelas de comparação, inclusive estados parciais/UNAVAILABLE. A largura da coluna de metadados foi ajustada após a primeira inspeção para preservar leitura dos rótulos. A matriz tem âncoras internas e resumo autossuficiente. A comparação conserva os motivos de exclusão do ranking e os parâmetros detalhados por filho.

A conferência de mídia de impressão usou evento beforeprint seguido de mídia print. No individual, as cinco imagens de gráficos tiveram dimensões válidas, incluindo BUY_HOLD_ASSET e indicadores. Na variante sem dados, a apresentação conserva os motivos e a tabela sem simular trajetórias. Com JavaScript desativado, o individual ETH conservou 18 tabelas e a identificação do instrumento.

Registros em `visual.json`, capturas `*-desktop.png`, `*-mobile.png`, `*-print.png` e `eth-indicator.png` no diretório final. O Chrome foi inicialmente bloqueado no sandbox por um socket interno, `setsockopt`. A execução local com a permissão de ferramenta necessária concluiu a inspeção. Não houve instalação de navegador, biblioteca ou dependência. A validação é de navegador/mídia CSS, sem impressão física.

## 9. Entregas e limites

Foram entregues catálogo e configuração tipados, cobertura, matriz/CLI, generalização financeira e de apresentação, dois catálogos, duas fixtures, três receitas/configurações, 19 testes novos, README, glossário e documentação atualizada. As sprints anteriores passaram na suíte completa de **170 testes**. A especificação e o planejamento apontam para este registro.

Permanece um instrumento por sessão, com capital independente e catálogo fixo durante o replay. O processamento é sequencial, com snapshots completos. Não foi medida capacidade para grandes matrizes ou históricos. Foi executado Python 3.12.14 neste ambiente, sem matriz adicional de versões/sistemas.

As regras de catálogo são hipóteses declaradas, os dados são fictícios e o resultado negativo da matriz canônica foi aceito como conferência de correção. A implementação conserva as convenções de execução, liquidez ilimitada e OHLC das sprints anteriores. Capital compartilhado e ingestão de mercado real permanecem nas etapas seguintes.

As verificações obrigatórias descritas acima estão concluídas. Não houve commit ou publicação. Artefatos auxiliares de `/tmp` podem ser removidos pelo sistema; este registro preserva os resultados observados, e o README contém as receitas de reprodução.
