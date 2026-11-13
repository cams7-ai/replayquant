# Validação da Sprint 13 — Dados históricos reais

## 1. Ambiente e entrada

Implementação em **13/11/2026**, a partir do HEAD **71c25ac**, com árvore inicialmente limpa. Esse commit contém a especificação da Sprint 13; a referência de implementação anterior era 0b2ba4f. Não foram encontradas instruções AGENTS.md aplicáveis. Foram consultados planejamento, especificação, contratos de dados/catálogo/risco/indicadores/carteira e validações anteriores.

Python **3.12.14**, ambiente `.venv`, biblioteca padrão e unittest. A suíte de entrada passou com **203 testes** em `/tmp/sprint13-baseline.log`. Não houve instalação de dependências, mudança de assets/licenças, publicação, commit ou negociação. Os dados externos foram obtidos apenas pelo comando explícito `obter-dados`; importação, validação e replay foram também exercitados com acesso de rede bloqueado.

## 2. Entrega e decisões

Implementados `BINANCE_SPOT_KLINES_CSV_V1`, aquisição pública limitada, API tipada de importação, normalização integral, persistência SQLite, dois IDs, revisões explícitas, snapshot portátil e comandos obter-dados/importar-dados/validar-dados. A origem BINANCE_SPOT é autorizada em contexto de catálogo e proveniência; os caminhos fictícios sem catálogo conservam sua restrição anterior. O motor financeiro continua sendo o das sprints anteriores.

Os módulos novos são `archive.py`, `historical_models.py`, `historical_adapter.py`, `historical_store.py`, `historical.py` e `provenance.py`. Integrações afetam CLI, modelos/catálogo, configuração/leitura individual, matriz, carteira e relatórios. Foram acrescentados quatro conjuntos de receitas (aquisição, importação real, fixture e retirada), seis arquivos de catálogo/universo, fixtures CSV/ZIP/checksums determinísticos e os quatro arquivos brutos reais/checksums com recibo e atribuição.

A [decisão de ingestão e persistência](decisoes/sprint13-ingestao.md) documenta as tabelas, precisão, normalização, IDs, transação e limites. Pontos relevantes:

- Decimais SQLite são TEXT canônico; timestamps, linhas e contagens são INTEGER. Não há SQL financeiro por REAL/CAST/soma ou ordenação textual de preços.
- O bruto inteiro é validado antes do recorte. Volume do Candle permanece base; metadados preservam volume cotação, trades e taker. O fechamento inclusivo da fonte é convertido por aritmética inteira ao fim exclusivo do minuto.
- `dataset_version` identifica conteúdo selecionado, catálogo/universo e contratos de normalização. Revisões incluem pai/justificativa, inclusive na restauração explícita de valores antigos. `ingestion_id` identifica bytes/evidências e código de transformação, sem caminho/relógio de obtenção.
- Deduplicação equivalente não duplica candles. Conflitos dentro do lote são recusados integralmente. Correção de uma versão aceita exige supersedes/revision_reason; pais e snapshots antigos continuam executáveis.
- Todos os arquivos são preparados antes de BEGIN IMMEDIATE/commit SQLite. Falha SQL não aceita prefixo do lote. Blobs órfãos não são versões aceitas. Não se promete atomicidade distribuída de SQLite e arquivos: exportação posterior pode falhar com EXPORT_FAILED, conservando versão aceita e INCOMPLETE, sem manifesto final.
- O snapshot contém dez arquivos, com manifesto por último. A execução verifica IDs, hashes, associação de dados/catálogo, contagens/finalização e origem, sem depender de SQLite. API incremental real valida os eventos contra o snapshot fixado.
- BOUNDARY_MARKS_V1, GLOBAL_GAP_INTERRUPT_V1, reservas, risco, STOP_FIRST e KEEP_OPEN foram preservados. Nenhuma mudança de regra foi feita para obter lucro ou forçar operações.

## 3. Aquisição oficial e hashes observados

Comando realmente executado:

```bash
.venv/bin/python -m replayquant obter-dados --config experiments/sprint13-aquisicao-real.json --destino data/historicos/entrada --formato json
```

A primeira tentativa no sandbox retornou **1**, por resolução DNS indisponível. A execução com a permissão de ferramenta necessária retornou **0**, obtendo quatro ZIPs e quatro checksums oficiais. Não houve troca de fonte ou geração de dados substitutos. `data/historicos/entrada/acquisition.json` registra URLs, hashes, tamanhos e horários UTC; stdout também foi capturado em `/tmp/sprint13-aquisicao.json`.

| ZIP oficial | Bytes | SHA-256 conferido com o checksum da fonte |
| --- | --- | --- |
| BTCUSDT-1m-2024-12-31.zip | 71638 | 756551b6eb4f0a0173af3333762e6c95d08c7503bb3b7b79807e10a02575a4af |
| BTCUSDT-1m-2025-01-01.zip | 69062 | 10a12909f1b0e3fcc6b7f502e5ea9be5d1ba3455dd8ab16cc61c8650640ba7c0 |
| ETHUSDT-1m-2024-12-31.zip | 67432 | 70ae988d84bb7ad0692dccbb126dec26b8a388fbc8cdd11bda06cbfe40837cf6 |
| ETHUSDT-1m-2025-01-01.zip | 66406 | 26cc71cf7a2bd0232cf0e8aaaf529fc6674ba20059028023eb346232ee4dbf91 |

Conferidos SHA-256, associação do nome, membro ZIP e CRC. O corpus bruto local ocupa cerca de 300 KiB. Cada CSV contém **1440 linhas**: 5760 no total, 2880 por par. Os arquivos de 2024 foram interpretados em ms e os de 2025 em us, explicitamente declarados. Essa convenção foi reconferida na [documentação oficial](https://github.com/binance/binance-public-data) durante a implementação. A atribuição e a referência aos termos específicos da fonte estão em [data/historicos/NOTICE.md](../data/historicos/NOTICE.md); não se confunde licença de scripts com condições dos datasets.

## 4. Normalização e qualidade: esperado e observado

Janela de replay `[2024-12-31T23:56:00Z, 2025-01-01T00:04:00Z)`, as_of fixo `2025-01-03T00:00:00Z`. A seleção não aquece com o restante do dia. Não houve duplicatas, incompletos ou lacunas nos arquivos reais fixados.

| Caso | Brutas BTC/ETH | Selecionadas BTC/ETH | Resultado esperado/observado |
| --- | --- | --- | --- |
| Fixture sintética ms/us | 8 / 8 | 8 / 8 | PASSED, código 0 |
| Amostra real oficial | 2880 / 2880 | 8 / 8 | PASSED, código 0 |
| Retirada sintética ETH | 8 / 8 | 8 / 4 | PASSED, código 0, quatro exclusões ETH por disponibilidade |

Na amostra real, cada instrumento tem 1436 candles anteriores à janela e 1436 posteriores, além dos oito selecionados. As estatísticas por instrumento e por arquivo estão em quality.json. As identidades observadas são:

- Real: dataset_version `1c8be4f41335fc36ac440539b3a927cac5af81a56b873c6becc531f718c5c549`; ingestion_id `9b1ada27dce887a8234ce62018c8c7582caaf1bab33dbdfb80a4ce1d788004e9`.
- Fixture: dataset_version `2a076a556d04a2c05a7321ce33b96181d9604baf15033885e58f6d473106fdbd`.
- Retirada: dataset_version `637eaa74b421187b65a1016b5589bff183f659cb33634846c7ad5357212dd4d0`.

O ID de ingestão depende do código de transformação e pode mudar em implementação posterior, mesmo com a mesma versão lógica. Os hashes brutos acima e o snapshot fixado permitem verificar qual entrada produziu cada execução.

Foi conferida a fronteira exata: `1735689540000` ms abre em 31/12/2024 23:59 UTC e `1735689599999 + 1` ms fecha em 01/01/2025 00:00 UTC. O candle seguinte abre em `1735689600000000` us e fecha após `1735689659999999 + 1` us. Não existe salto artificial de 1000× ou minuto duplicado.

## 5. Resultados financeiros separados

### Fixture sintética de formato

Esperado e observado: oito candles por par, quatro fills, dois lotes encerrados, compras às 00:01 e vendas às 00:03 UTC, **0.000166 BTC / 0.00420 ETH**, caixa/patrimônio **989.95 USDT**, taxas **0.05 USDT**, retorno **−1.005%**, exposição conjunta **120 segundos**, código **0**. Esse resultado é o oráculo sintético das sprints anteriores, com nova janela temporal. Seus checksums foram gerados localmente, não são checksums oficiais de mercado.

### Amostra real

Não havia expectativa numérica de lucro ou de trades. Foram observados:

| Medida — carteira global | Valor |
| --- | --- |
| Capital inicial | 1000 USDT |
| Fills / lotes encerrados | 2 / 0 |
| Compra SMA/BTC | 0.000212 BTC a 93652 USDT/BTC |
| Compra EMA/ETH | 0.00304 ETH a 3338.86 USDT/ETH |
| Caixa final | 969.9656372416 USDT |
| Taxas pagas | 0.0300043584 USDT |
| BTC final / marca | 0.000212 BTC / 93677.98 USDT/BTC |
| ETH final / marca | 0.00304 ETH / 3339.98 USDT/ETH |
| Patrimônio bruto marcado | 999.9789082016 USDT |
| PnL realizado / não realizado | 0 / −0.0210917984 USDT |
| Retorno global marcado | −0.002109179840% |
| Liquidação hipotética | 999.94889493064 USDT |
| Exposição conjunta | 120 segundos |
| Estado / código | COMPLETED / 0 |

As posições permanecem KEEP_OPEN, sem taxa hipotética cobrada. O individual SMA/BTC tem caixa **960.158097900 USDT** e **0.000425 BTC**, código 0. Na matriz independente, SMA/EMA em BTC têm esses mesmos saldos; SMA/EMA em ETH têm caixa **960.0941456116 USDT** e **0.01194 ETH**, também código 0. Cada filho usa seu próprio capital de 1000 USDT; os patrimônios não foram agregados numa carteira.

Os filtros são SYNTHETIC_ASSUMPTION; taxa 0.001, slippage zero e liquidez ilimitada são hipóteses do cenário. O universo real está restrito a OBSERVED_COVERAGE_ONLY / SURVIVORSHIP_RESTRICTION; as bordas do catálogo não provam listagem ou retirada histórica. FINAL_ARCHIVE_ASSUMED_AVAILABLE_AT_CLOSE não reconstrói revisões disponíveis em tempo real. Oito minutos não constituem avaliação de rentabilidade, correlação ou hedge.

## 6. Testes adversos e integridade

A suíte final passou com **230 testes**, sendo **27 novos** da Sprint 13. Foram conferidos:

- Oráculo financeiro, normalização ms/us, contagens selecionadas, dez arquivos exportados e tipos SQLite text/integer.
- Reimportação/reabertura sem duplicar linhas, permutação de arquivos e caminhos equivalentes; duplicata com escala distinta mantém dataset_version e pode registrar outra ingestão.
- Conflito de valores com OHLC válido sem aceitação parcial; revisão explícita, pai preservado, snapshot antigo executável e restauração como terceira linhagem distinta.
- Falha SQL injetada antes do commit, sem candles/versão aceitos; objetos preparados podem ficar órfãos. Arquivo final inválido não abre banco nem aceita o anterior.
- Falha de escrita depois do commit informa EXPORT_FAILED, conserva versão, INCOMPLETE e ausência de manifesto final. Reexportar em outro diretório não duplica candles.
- Saída existente falha antes da ingestão; versão SQLite desconhecida não é recriada.
- Unidade/fechamento inclusivo errados, ordem invertida, colunas incompletas, decimal não finito/não representável, taker inválido, checksum/CRC e ZIP traversal/absoluto/membro inválido.
- Recorte por as_of remove o último candle incompleto, gera QUALITY_WARNINGS e não alimenta o indicador. Snapshots reais sem observações mantêm capital, código 2 e desempenho nulo no individual/carteira.
- Minuto BTC ausente em 00:01 causa qualidade com lacuna; a carteira conserva sinais/reservas do fechamento, não consome OPEN ETH isolado e retorna 1.
- Retirada sintética aceita quatro candles ETH, sem lacuna fora da disponibilidade; entrada controlada conserva o lote, marca/idade, propriedade e proteção indisponível com reserva base liberada.
- Contexto Decimal externo de precisão 3 com Inexact habilitado é preservado; texto decimal canônico não é confundido com ordenação numérica SQL.
- API/JSON estritos, tipos e referências, manifesto/hash/versão divergentes, evento real alterado sem mutação da fronteira e tentativa sem manifesto.
- Importação/validação/individual/matriz/carteira reais com OpenerDirector.open bloqueado, reimportação offline em banco novo e execução com banco fora do caminho.
- Aquisição simulada sem rede, publicação imutável, recusa de sobrescrita divergente e aquisição falha mantendo recibo INCOMPLETE.
- Quatro formatos de validação e outra cwd. As regressões anteriores preservam indicadores, causalidade, prefixos, reservas, proteção, risco e reconciliação financeira.

## 7. Comandos realmente executados e reprodução

A rodada consolidada está em **`/tmp/replayquant-sprint13-entrega`**. `commands.json` registra **62 comandos**, argumentos, cwd e códigos esperados/observados; stdout/stderr ficam em arquivos individuais. O runner auxiliar é `/tmp/sprint13-validate.py`. A aquisição oficial acima é uma etapa adicional registrada no próprio recibo. Esses caminhos são auxiliares locais; README e receitas versionadas permitem reprodução.

| Grupo | Quantidade | Esperado/observado |
| --- | --- | --- |
| Versão Python e sete ajudas | 8 | 0 |
| Quatro demonstrações manual/SMA/análise/risco | 4 | 0 |
| Importar, validar e carteira sintéticos, quatro formatos cada | 12 | 0 |
| Importar, validar e carteira reais, quatro formatos cada | 12 | 0 |
| Importar/validar retirada sintética | 2 | 0 |
| Individual, matriz e repetição HTML, fixture e real | 6 | 0 |
| Outra cwd com snapshot real | 1 | 0 |
| Saída existente e origem real sem manifesto | 2 | 1 |
| Carteiras Sprint 12 canônico/multipar/limite | 3 | 0 / 0 / 2 |
| Matriz legada Sprint 11 | 1 | 2 |
| Individual ETH/RSI legado | 1 | 0 |
| Cinco exemplos expandidos Sprints 07/09/10 | 5 | 0 |
| unittest discover -s tests -v | 1 | 0, 230 testes |
| node --check chart.js/equity.js/indicators.js | 3 | 0 |
| git diff --check | 1 | 0 |

Os exemplos expandidos preservaram caixas anteriores: Sprint 07 e Sprint 09 equivalente **1000.90155066834**; Sprint 10 SMA **1000.42208230**, EMA **1000.71085163730**, RSI **1001.93754109984 USDT**. As três carteiras Sprint 12 preservaram seus resultados; os códigos 2 do limite e da matriz legada são esperados pelos casos já documentados.

`reproduction.json` confere por bytes os **dez arquivos** de snapshots repetidos e os **quinze arquivos** das carteiras nos quatro formatos, repetição com --analise e outra cwd. HTML repetido é idêntico. Reimportação real offline em repositório novo produziu os mesmos dez arquivos e dataset_version; `offline.json` registra execução com rede bloqueada. Não se exige igualdade binária do SQLite: são conferidos contagens, chaves, versões, origem, tipos e relações lógicas.

O snapshot exportado executa sem banco acessível. Nenhum download ocorre implicitamente por manifesto ausente ou divergente. Saída existente e falta de manifesto retornam 1, sem publicar novo replay aceito.

## 8. Inspeção visual e offline

HTMLs de qualidade sintética/real, carteiras sintética/real, individual real e matriz real foram abertos no Chrome headless local. Conferidos desktop **1400×1000**, tela estreita **390×900**, mídia print e JavaScript desativado. Não houve requisição HTTP externa ou exceção JavaScript. Tabelas mantêm rolagem interna; os SVGs da carteira continuam disponíveis sem JS. O individual conserva tabelas/metadados sem JS e gera gráficos/imagens de impressão quando habilitado.

A primeira inspeção detectou um identificador longo de política causando largura 425 em viewport 390 na carteira real. Foi corrigida a quebra de texto no relatório, e a rodada final conferiu largura igual ao viewport. Foram observadas capturas desktop/mobile/print e tabelas de identidade, cobertura/unidades, hashes, posições e universo. PDFs auxiliares representam mídia print do navegador; não houve impressão física.

Evidências: `visual.json`, `*-desktop.png`, `*-mobile.png`, `*-print.png`, `*-table.png` e `*-print.pdf` no diretório consolidado. Usados Node **24.22.1**, Playwright e Chrome já instalados; execução local autorizada porque o sandbox bloqueia sockets internos do Chrome. Os checks de sintaxe dos assets usaram o Node do sistema. Nenhum pacote ou navegador foi instalado.

## 9. Limites e pendências

Concluídas implementação, demonstração real/offline e verificações obrigatórias desta etapa. A implementação foi testada em Python 3.12.14 neste ambiente, sem matriz adicional de plataformas/versões. Não foram medidos grandes históricos. A importação mantém registros em memória e o coordenador de carteira prepara snapshots completos; o replay externo usa deliberadamente oito minutos. Parquet/DuckDB, paralelismo, snapshots abertos, recuperação operacional e pesquisa temporal permanecem fora do escopo.

Checksums e relações de manifesto verificam integridade/proveniência dos bytes fixados, não assinatura da fonte nem correção econômica universal. Arquivos oficiais podem sofrer revisões; novas importações divergentes exigem linhagem explícita. O snapshot final não recupera a informação disponível em cada revisão histórica. Não há evidência de universo completo, regras de negociação históricas exatas ou rentabilidade.

Os registros auxiliares em /tmp podem ser removidos pelo sistema; os brutos necessários, receitas, atribuição, documentação e testes estão no workspace. Não houve commit ou publicação.
