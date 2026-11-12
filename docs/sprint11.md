# Sprint 11 — Múltiplos pares e catálogo

**Projeto** ReplayQuant  
**Nível** intermediário  
**Referência** [Planejamento](planejamento.md), especialmente seções 4, 11, 21 e 23  
**Pré-requisitos** Sprints 06 a 10 implementadas, com seus registros de validação  
**Estado** especificação para implementação futura. Comandos novos e resultados esperados abaixo deverão ser verificados durante a implementação.

## 1. Objetivo e ponto de partida

Distinguir o efeito da estratégia do efeito do instrumento, executando SMA, EMA e RSI em BTCUSDT e ETHUSDT fictícios. Um catálogo identifica moedas, filtros e disponibilidade temporal. Cada combinação estratégia × par possui capital, histórico, indicadores, ordens, reservas e resultados próprios.

Trabalhar em `/home/cams7/Dev/Cripto_Tests/replayquant`, evoluindo o projeto atual. A referência consultada é o commit `c8df5ae`. Inspecionar HEAD, `git status` e instruções `AGENTS.md` aplicáveis. Preservar alterações existentes e posteriores. Ler os contratos anteriores e seus registros, especialmente [Sprint 09](sprint09.md), [Sprint 10](sprint10.md) e [validação do Sprint 10](sprint10-validacao.md). Conferir os pré-requisitos pela suíte e pelas demonstrações existentes antes de editar.

A Sprint 10 entrega o registro SMA_CROSS/1, EMA_CROSS/1 e RSI_REVERSION/1, schema 5 com risco obrigatório, recorrências exatas, API incremental e relatórios offline. Entretanto, `models.instrument` restringe FICTICIA/BTCUSDT/1m, `Balance` e consumidores usam `btc`, reservas aceitam BTC/USDT, benchmarks usam BUY_HOLD_BTC e HTML/JavaScript contêm unidades BTC. Generalizar somente o parser deixaria saldos e relatórios incorretos para ETH. A etapa deve alcançar toda essa cadeia e reutilizar os cálculos financeiros existentes.

## 2. Escopo e limites

Implementar catálogo local versionado, seleção de instrumento, validação cruzada entre catálogo/configuração/dados, disponibilidade temporal, unidades genéricas e execução de uma matriz pequena de experimentos independentes. Entregar comparação descritiva com custos, risco, amostra, cobertura, rejeições e ranking com elegibilidade explícita.

Começar por FICTICIA, BTCUSDT e ETHUSDT, cotação USDT e candles de um minuto. A inclusão posterior de outro par fictício com cotação USDT deve ocorrer por dados e entrada de catálogo válidos. Cada sessão continua negociando um único instrumento e uma posição comprada, com preenchimentos totais e uma intenção comum pendente.

Reutilizar risco, reservas, revalidação, prioridade de saídas, STOP_FIRST, marcação e KEEP_OPEN das sprints anteriores. Indicadores continuam causais e independentes. Python >= 3.11, biblioteca padrão, `unittest`, UTC e execução offline permanecem a base. Registrar a versão efetiva do ambiente, dependências e assets já utilizados.

Capital compartilhado, arbitragem de sinais simultâneos e lotes concorrentes pertencem à Sprint 12. Ingestão externa, dados históricos reais e persistência pertencem à Sprint 13. Conversão de moedas de cotação, otimização automática, eleição de parâmetros pelo lucro, paralelismo, novas estratégias, novas frequências e modelos de execução ficam fora desta etapa.

## 3. Catálogo de instrumentos

### 3.1. Arquivo e identidade

Criar futuramente `data/catalogo/sprint11-instrumentos.json`, com JSON estrito e envelope próprio `schema_version: 1`. O conteúdo canônico abaixo define o exemplo principal.

```json
{
  "schema_version": 1,
  "catalog_id": "SPRINT11_FICTICIA_V1",
  "instruments": [
    {
      "source": "FICTICIA",
      "symbol": "BTCUSDT",
      "base_asset": "BTC",
      "quote_asset": "USDT",
      "intervals": ["1m"],
      "available_from": "2026-01-01T12:00:00+00:00",
      "available_until": null,
      "instrument_filters": {"step": "0.000001", "min_quantity": "0.000001", "min_notional": "0"},
      "rules_basis": "SYNTHETIC_ASSUMPTION",
      "rules_as_of": "2026-01-01T00:00:00+00:00",
      "rules_source": "Hipótese didática da fixture Sprint 11"
    },
    {
      "source": "FICTICIA",
      "symbol": "ETHUSDT",
      "base_asset": "ETH",
      "quote_asset": "USDT",
      "intervals": ["1m"],
      "available_from": "2026-01-01T12:00:00+00:00",
      "available_until": null,
      "instrument_filters": {"step": "0.00001", "min_quantity": "0.00001", "min_notional": "0"},
      "rules_basis": "SYNTHETIC_ASSUMPTION",
      "rules_as_of": "2026-01-01T00:00:00+00:00",
      "rules_source": "Hipótese didática da fixture Sprint 11"
    }
  ]
}
```

A chave de instrumento é `(source, symbol)`, com intervalos permitidos declarados. Exigir uma entrada por chave, rejeitando duplicatas mesmo equivalentes. `catalog_id` identifica a revisão, mas o hash dos bytes do catálogo também integra a identidade. Mesmo ID textual com outro conteúdo produz identidade diferente. Carregar um snapshot imutável, sem reler o arquivo no meio da sessão.

Origem, símbolo, moedas, intervalos e referências devem ser strings não vazias validadas. Nesta versão, moedas e símbolos usam letras maiúsculas/dígitos, com `symbol = base_asset + quote_asset`, base diferente da cotação e cotação USDT. Validar a estrutura dos modelos de mercado também pela API. A autorização para negociar um símbolo vem do catálogo resolvido no caminho novo. Configurações legadas continuam restritas ao instrumento que já suportavam.

### 3.2. Datas e regras

A disponibilidade é `[available_from, available_until)`, com fim opcional `null`. Datas têm fuso, normalização UTC e alinhamento ao minuto. Quando há fim, exigir `available_from < available_until`. Um candle negociável deve estar integralmente contido na disponibilidade, com `open_time >= available_from` e `close_time <= available_until` quando finito.

O registro tem um único conjunto de filtros fixos para sua disponibilidade nesta etapa. Exigir `step > 0`, `min_quantity > 0` e `min_notional >= 0`, em strings decimais, com os limites atuais de entrada. Step e quantidade mínima são unidades do ativo base. Nocional mínimo é USDT. O piso por step, revalidação e rejeição sem aumento para cumprir mínimo seguem a Sprint 09.

`rules_basis` é obrigatório e admite `SYNTHETIC_ASSUMPTION` ou `CURRENT_RULES_ASSUMED_FOR_PERIOD`. `rules_as_of` registra a data de referência declarada das regras e `rules_source` sua origem textual. A segunda classificação deve aparecer explicitamente como hipótese de aplicar regras atuais ao período. A data de referência não demonstra disponibilidade histórica da informação. O exemplo canônico usa somente regras sintéticas. Não rotular nenhuma dessas classificações como histórico verificado de uma exchange.

Revisar filtros exige outro snapshot/hash de catálogo. Mudanças de regras dentro da execução e histórico completo de revisões permanecem para etapas posteriores. Metadados de disponibilidade e proveniência não entram como indicadores ou condições para antecipar compra/venda pela estratégia.

## 4. Configuração e compatibilidade

### 4.1. Execução individual schema 6

Introduzir configuração **schema 6**, `mode: STRATEGY`, com seleção de origem/par/intervalo, janela explícita, capital, custos, risco e StrategySpec da Sprint 10. O catálogo é obrigatório nesse caminho e fornece moedas e filtros. Recusar `instrument_filters` na configuração schema 6 para evitar duas fontes de regras. Recusar roteiro manual e campos extras.

Exemplo completo previsto para `experiments/sprint11-eth-rsi.json`.

```json
{
  "schema_version": 6,
  "mode": "STRATEGY",
  "source": "FICTICIA",
  "symbol": "ETHUSDT",
  "interval": "1m",
  "window": {"start": "2026-01-01T12:00:00+00:00", "end": "2026-01-01T12:07:00+00:00"},
  "initial_cash": "1000",
  "fee_rate": "0.001",
  "slippage_rate": "0",
  "risk": {
    "risk_fraction": "0.01",
    "exposure_fraction": "1",
    "stop_fraction": "0.5",
    "target_fraction": "0.9",
    "daily_loss_fraction": "0.9",
    "drawdown_fraction": "0.9",
    "max_price_age_seconds": "60"
  },
  "strategy": {
    "name": "RSI_REVERSION",
    "version": 1,
    "parameters": {"period": 2, "oversold": "30", "overbought": "70"}
  }
}
```

A janela é `[start, end)`, com datas UTC alinhadas, início anterior ao fim e candles integralmente contidos. O último fechamento pode coincidir com `end`. Aquecimento usa somente candles elegíveis dentro da janela nesta versão, iniciando estratégia e carteira vazias. Candles excluídos não aquecem o indicador.

`executar` receberá `--catalogo CAMINHO` para schema 6. Na API, receber um catálogo resolvido e validado explicitamente, sem fallback global. Não exigir esse argumento das configurações 1, 2, 4 e 5. Nelas, manter filtros, instrumento, políticas, campos e comportamento anteriores. Recusar uso de catálogo para substituir silenciosamente filtros legados.

Schema 6 implica análise obrigatória, com `--analise` redundante e sem alteração de identidade. A API rejeita desativar a análise. Validar tipos/faixas, JSON duplicado, não finitos, booleanos numéricos, desconhecimento de instrumento/estratégia/versão e ausência de catálogo antes de iniciar o replay.

### 4.2. Modelos e unidades

Generalizar campos, projeções e validações necessários à moeda base. O caminho schema 6 apresenta `final_balance.cash` em USDT e `final_balance.asset_quantity` no ativo base, com `base_asset`, `quote_asset`, `symbol`, `source` e `interval` explícitos. As métricas genéricas existentes, como `final_asset_quantity`, preservam seu significado e recebem a unidade correta.

Reutilizar a aritmética de carteira, ledger e reservas. Adaptar os modelos internos ou suas fronteiras de compatibilidade para que posições ETH não dependam de campos públicos rotulados `btc`. Preservar `balance.btc`, payloads e unidades dos caminhos legados BTC. A representação interna escolhida deve ser documentada e testada sem manter dois motores financeiros.

Reservas usam a moeda base efetiva e USDT. Uma saída ETH consome somente ETH daquela sessão. Médias, preços de referência, stop/alvo e ganho/perda médios do RSI usam USDT/base. RSI permanece em pontos 0–100. Quantidades e volume são base, patrimônio e taxas são USDT. Contexto decimal local, razões exatas, limites e rollback continuam vigentes.

## 5. Dados, disponibilidade e fronteiras

Cada arquivo de candles corresponde a uma origem/par/intervalo. Reutilizar o envelope de candles schema 1 e seus campos, tornando a validação do instrumento contextual ao catálogo no caminho novo. Antes de recortar, validar o arquivo inteiro, incluindo OHLC, tipos, ordem e identidade. Misturar BTC e ETH num arquivo individual ou fornecer arquivo incompatível com a configuração é erro, mesmo se os candles divergentes ficariam fora da janela. Duplicatas equivalentes seguem a política existente, conflitos falham.

Aplicar a interseção entre janela solicitada e disponibilidade, registrando separadamente candles excluídos antes/depois da janela e antes/depois da disponibilidade. Os candles aceitos devem ser contíguos. Uma lacuna interna interrompe no mesmo prefixo causal da Sprint 10, sem preencher, aquecer ou executar através dela. Exclusões apenas nas bordas não constituem lacuna interna.

O relatório declara início/fim solicitados, limites de disponibilidade, primeiro/último candle elegível, último evento efetivamente processado, candles esperados/aceitos/excluídos, duplicatas, lacunas e motivos. Mostrar cobertura frente à janela solicitada e também frente à interseção elegível, sem tratar listagem tardia como perda de arquivo. Distinguir `FULL`, `PARTIAL` e `NONE` para cobertura da janela solicitada. Dados ausentes numa borda exigem diagnóstico de cobertura parcial.

Se a interseção não tiver candle, não criar posição, ordem, taxa ou benchmark comprado. Emitir resultado de combinação `UNAVAILABLE`, motivo `NO_ELIGIBLE_CANDLES`, contagens zero e métricas de desempenho `null` com motivo. É uma combinação reportável, com código de política 2. Símbolo ausente do catálogo, arquivo inexistente ou conteúdo inválido são erros de entrada, código 1.

Uma abertura fora da disponibilidade jamais preenche ordem, inclusive na API incremental. Para OPEN_EVENT, o horário do fill deve pertencer ao intervalo de disponibilidade. Para BAR_CLOSE_RESOLUTION, o horário modelado pode coincidir com available_until quando o candle inteiro pertence à disponibilidade e a proteção já era elegível naquele candle. Nesse caso, o timestamp representa a resolução do último intervalo válido conforme a Sprint 09. Recusá-la com diagnóstico estável `INSTRUMENT_UNAVAILABLE`, preservando o último estado aceito. O executor de arquivo encerra o horizonte elegível sem consumir esse evento. Pendência cujo próximo evento foi eliminado pelo fim de disponibilidade termina `UNEXECUTED/INSTRUMENT_UNAVAILABLE`; quando só falta abertura futura nos dados/janela, usar `NO_FUTURE_OPEN`. Não antecipar uma ordem ao último fechamento para liquidá-la.

Posição ainda aberta no fim permanece KEEP_OPEN, marcada somente no último preço elegível, com motivo e horário desse preço. Finalização normal libera reservas conforme a Sprint 09. Interrupção por lacuna preserva as reservas do prefixo. O catálogo não obriga liquidação fictícia em deslistagem. O BUY_HOLD também começa na primeira abertura elegível, respeita filtros e termina no mesmo prefixo da estratégia.

A idade de preço usa o relógio simulado e o horário de sua disponibilidade, com limite inclusivo de `max_price_age_seconds`. Preservar os testes de preço ausente, antigo e futuro. Uma marca conservada após o fim do instrumento serve à apresentação do prefixo e não autoriza nova negociação.

## 6. Matriz de experimentos independentes

### 6.1. Entrada e resolução

Introduzir o comando futuro `comparar --config --saida --formato`, com formatos texto, JSON, Markdown e HTML. Criar `experiments/sprint11-matriz.json`, envelope próprio schema 1, com exatamente os campos abaixo.

| Campo | Conteúdo obrigatório |
| --- | --- |
| `schema_version` | Inteiro 1 |
| `mode` | `INDEPENDENT_MATRIX` |
| `catalog` | `../data/catalogo/sprint11-instrumentos.json` |
| `source`, `interval`, `quote_asset` | FICTICIA, 1m e USDT |
| `window` | Mesma janela do exemplo individual |
| `initial_cash`, `fee_rate`, `slippage_rate`, `risk` | Exatamente os valores do exemplo individual |
| `datasets` | Lista dos dois objetos `{symbol, path}` definidos abaixo |
| `strategies` | Lista dos três objetos `{id, strategy}` definidos abaixo |

Datasets canônicos são `{"symbol":"BTCUSDT","path":"../data/fixtures/sprint11-btc-candles.json"}` e o equivalente ETH com `sprint11-eth-candles.json`. As estratégias são `sma-2-3` com SMA_CROSS/1 e janelas 2/3, `ema-2-3` com EMA_CROSS/1 e janelas 2/3, e `rsi-2-30-70` com RSI_REVERSION/1, período 2 e limiares 30/70. O objeto `strategy` tem o mesmo formato do schema 6.

Resolver caminhos relativos ao arquivo de configuração da matriz, também quando a CLI é chamada de outro diretório. IDs são únicos, não vazios e seguros para nomes de diretórios, restritos a letras/dígitos/hífen/underscore. Rejeitar IDs duplicados, datasets repetidos, listas vazias e cotação incompatível. Validar todos os arquivos e combinações antes de iniciar gravação. Datas/recortes sem observações elegíveis permanecem resultados de política.

Criar seis configurações resolvidas schema 6 e sessões novas com 1000 USDT cada. Reusar a mesma rotina de replay e relatório individual. Executar sequencialmente em ordem canônica `(source, symbol, strategy_id)`. Inverter a ordem de datasets/estratégias na entrada preserva a ordem lógica, os resultados e os IDs derivados da matriz canônica. Registrar também o hash dos bytes originais da receita como proveniência, separado da identidade lógica normalizada. Caminhos resolvidos servem à localização/proveniência; a identidade lógica usa os conteúdos e suas associações aos instrumentos, permitindo reprodução em outra raiz.

### 6.2. Resultados e ranking

Cada linha contém identidade de matriz/execução, estratégia/versão/parâmetros, par/moedas, capital inicial, risco e filtros, taxa/slippage, custos pagos, patrimônio bruto, liquidação hipotética, retorno, drawdown, duração, exposição, trades encerrados, posição final, rejeições e motivos. Incluir cobertura, aquecimento, estado do replay, código de saída e status de disponibilidade.

O ranking é descritivo, por retorno patrimonial bruto marcado, já afetado pelos custos pagos, em ordem decrescente. Empates financeiros exatos recebem a mesma posição, com salto posterior de posição e ordenação estável por par/ID de estratégia. Decidir elegibilidade/empates por valores ou razões exatas, sem usar percentuais arredondados.

Entram no mesmo grupo de ranking somente combinações com janela solicitada igual, cobertura FULL, replay concluído com código 0, capital/cotação/custos/risco comparáveis e horizonte efetivamente igual. Filtros por instrumento podem diferir e ficam explícitos. Posição aberta e número de trades aparecem ao lado do retorno. Linhas parciais, indisponíveis, interrompidas ou com código 2 permanecem na comparação, com ranking `null` e motivo. Resultados de períodos diferentes não disputam a mesma posição.

Nenhuma soma de lucros, retornos ou capitais das seis sessões será apresentada como desempenho de uma carteira. Não combinar suas curvas num patrimônio único. Exibir a condição `INDEPENDENT_CAPITAL_PER_RUN` e comparar benchmarks passivos separadamente por execução. Não selecionar automaticamente uma configuração para operar ou iniciar pesquisa de parâmetros.

## 7. Fixtures e expectativas conferíveis

### 7.1. Matriz canônica

Criar duas fixtures locais com sete candles, de 01/01/2026 12:00 a 12:07 UTC. Preços em strings decimais, volume base `"1"`, candles fechados e metadados FICTICIA/par/1m. Para cada série, a primeira abertura é o primeiro fechamento e cada abertura seguinte é o fechamento anterior. `high=max(open,close)` e `low=min(open,close)`.

| Fechamento número | BTCUSDT | ETHUSDT |
| --- | --- | --- |
| 1 | 100000 | 2000 |
| 2 | 90000 | 1800 |
| 3 | 80000 | 1600 |
| 4 | 100000 | 2000 |
| 5 | 120000 | 2400 |
| 6 | 100000 | 2000 |
| 7 | 80000 | 1600 |

A trajetória ETH é uma transformação didática BTC/50 para conferir unidades e filtros. Volumes são por ativo e não representam liquidez comparável. O catálogo canônico permite as duas séries completas. Taxa 0.001, slippage zero e demais parâmetros são os da seção 4.1. As seis sessões começam vazias e independentes.

| Combinação | Compra / venda UTC | Quantidade base | Caixa final USDT | Ativo final | Patrimônio bruto USDT | Código esperado |
| --- | --- | --- | --- | --- | --- | --- |
| SMA ou EMA / BTC | BUY 12:05, SELL final 12:07 sem abertura | 0.000166 BTC | 980.06008 | 0.000166 BTC | 993.34008 | 2 |
| SMA ou EMA / ETH | BUY 12:05, SELL final 12:07 sem abertura | 0.00830 ETH | 980.06008 | 0.00830 ETH | 993.34008 | 2 |
| RSI / BTC | BUY 12:04, SELL 12:06 | 0.000199 BTC | 999.9602 | 0 BTC | 999.9602 | 0 |
| RSI / ETH | BUY 12:04, SELL 12:06 | 0.00997 ETH | 999.96012 | 0 ETH | 999.96012 | 0 |

SMA/EMA sinalizam no quinto e sétimo fechamentos. A entrada BTC a 120000 tem stop 60000, perda unitária `120000×1.001 − 60000×0.999 = 60180 USDT/BTC`, orçamento 10 USDT e piso q=0.000166 BTC. Compra bruta 19.92, taxa 0.01992 e desembolso 19.93992 USDT. A posição termina marcada a 80000, valendo 13.28 USDT. ETH a 2400 e stop 1200 tem perda unitária 1203.6 USDT/ETH, piso q=0.00830 ETH e os mesmos valores financeiros.

RSI sinaliza no quarto e sexto fechamentos. BTC compra e vende a 100000. Sua perda unitária é `100000×1.001 − 50000×0.999 = 50150`, candidato `10/50150 BTC` e piso 0.000199 BTC. Bruto por ponta 19.9, taxa por ponta 0.0199 e lucro −0.0398 USDT. ETH compra e vende a 2000, com perda unitária 1003 e piso de `10/1003` para 0.00997 ETH. Bruto 19.94, taxa por ponta 0.01994 e lucro −0.03988 USDT. A diferença entre os dois resultados decorre dos incrementos definidos no catálogo.

Os dois RSI são elegíveis para o ranking canônico, com BTC antes de ETH. As quatro linhas SMA/EMA continuam no comparativo com motivos de não execução final e ranking indisponível. `comparar` retorna 2, pois a matriz contém filhos com código 2. O resultado negativo é válido para o aceite técnico.

### 7.2. Variantes temporais e de domínio

Criar `data/catalogo/sprint11-instrumentos-parcial.json` derivado do catálogo canônico, alterando somente a disponibilidade ETH para `[2026-01-01T12:02:00Z, 2026-01-01T12:06:00Z)`. Executar a mesma matriz com receita `experiments/sprint11-matriz-parcial.json`. Apenas quatro candles ETH podem alimentar seus indicadores. Seus resultados têm cobertura PARTIAL da janela solicitada e ranking indisponível. BTC conserva o resultado da matriz canônica. Documentar os sinais efetivamente observados após esse aquecimento reduzido.

Cobrir ainda instrumento completamente fora da janela, ausência de candles numa borda, lacuna interna, fim de disponibilidade com ordem pendente e posição aberta. Para o teste de posição aberta, usar RSI/ETH completo até a compra e fixar `available_until=12:05 UTC`. Nenhum fill de abertura pode ocorrer a partir desse instante. O candle de entrada continua sujeito à janela sem atuação protetiva da Sprint 09. A posição permanece marcada no último fechamento elegível, com liberação final de reservas e cobertura parcial.

Testar catálogo sem o par, moeda de cotação incompatível, chave duplicada, intervalo não permitido, limites de datas inválidos e regras atuais assumidas com rótulo de hipótese. Testar troca de arquivo BTC por ETH, candle estrangeiro inserido no final do arquivo e evento estrangeiro pela API incremental. Nenhum histórico ou saldo da primeira sessão pode ser alterado por essas falhas.

Demonstrar inclusão de um terceiro símbolo fictício cotado em USDT pelo catálogo/dados, sem editar uma whitelist de pares no motor. Esse teste verifica extensibilidade do catálogo, sem ampliar a matriz canônica de seis execuções.

## 8. Artefatos, identidade e apresentação

A execução individual schema 6 gera os onze artefatos do modo de risco, com instrumento e unidades resolvidos, filtros e origem das regras, disponibilidade e cobertura. A identidade inclui catálogo/hash, instrumento, janela, dados, configuração, estratégia e versões de políticas, além de código/assets e Python. Se o catálogo inclui entradas não usadas, seu hash completo continua registrado e participa da identidade. Saída e relógio de parede ficam fora da identidade lógica.

Usar identificadores de benchmark `HOLD_USDT` e `BUY_HOLD_ASSET` no schema novo, com `base_asset` explícito. Preservar BUY_HOLD_BTC nos payloads legados. Todas as taxas/custos e filtros são aplicados no instrumento correto e cada benchmark usa capital próprio. Código e JavaScript exibem BTC/ETH/USDT conforme os metadados, incluindo gráficos, tooltips, labels, fórmulas, CSVs e alternativa sem JavaScript.

O diretório de comparação contém `manifest.json`, `comparison.json`, `comparison.csv`, `comparison.md` e `runs/<symbol>/<strategy_id>/`, com os onze arquivos de cada filho. Resultados UNAVAILABLE também têm artefatos com métricas nulas e motivos, adaptando o contrato de relatório para ausência de eventos. O HTML da matriz é emitido em stdout, fora do diretório de artefatos, com resumo autossuficiente e navegação por âncoras internas, legível sem JavaScript. Cada linha identifica o run_id do filho. O comparison.md pode vincular relatórios dos filhos por caminhos relativos ao diretório da matriz. O HTML emitido deve funcionar independentemente do local em que stdout foi salvo.

Comparações determinísticas ignoram somente proveniência explicitamente dependente da ordem textual original da receita. Na mesma entrada em bytes, exigir igualdade por bytes de todos os artefatos e da saída HTML. Em receitas semanticamente equivalentes reordenadas, exigir igualdade de identidade lógica, IDs de filhos, valores, ranking e eventos dos filhos, mantendo distintos os hashes de proveniência dos arquivos originais.

Validar os diretórios de saída novos antes de gravar. Manter o marcador INCOMPLETE até concluir os filhos e o manifesto da matriz. Erro estrutural anterior não cria diretório. Falha técnica posterior não publica um resumo de sucesso e mantém a gravação incompleta identificada. Código 1 tem precedência sobre 2; código 2 tem precedência sobre 0. Descrever separadamente estado da combinação, código financeiro e cobertura.

## 9. Entregáveis e comandos de validação futura

Entregar catálogo/modelos e resolução tipada, generalização das unidades, schema 6, suporte individual e comando comparar, fixtures/configurações especificadas, testes de comportamento e relatórios. Atualizar README, planejamento e documentação das estratégias onde necessário. Criar `docs/sprint11-glossario.md` e `docs/sprint11-validacao.md`, registrando ambiente, comandos, resultados esperados/observados, comparação, hipóteses do catálogo, inspeção visual, limitações e pendências.

Na raiz do repositório, ativar a `.venv` existente. Se ela não existir, criá-la com `python3 -m venv .venv`. Conferir a versão concreta e as dependências do projeto. Os comandos abaixo são receitas futuras da implementação, não resultados executados nesta especificação.

```bash
source .venv/bin/activate
python --version
python -m unittest discover -s tests -v
python -m replayquant --help
python -m replayquant executar --help
python -m replayquant demonstrar --formato json
python -m replayquant demonstrar --risco --estrategia sma --formato json
```

Depois de implementar, `comparar --help` e o individual RSI/ETH canônico retornam 0. As matrizes canônica e parcial retornam 2 pelos motivos registrados na seção 7. Registrar cada código individualmente.

```bash
python -m replayquant comparar --help
sprint11_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint11-eth-candles.json --config experiments/sprint11-eth-rsi.json --catalogo data/catalogo/sprint11-instrumentos.json --saida "$sprint11_dir/eth-rsi" --formato html > "$sprint11_dir/eth-rsi.html"
python -m replayquant comparar --config experiments/sprint11-matriz.json --saida "$sprint11_dir/matriz" --formato html > "$sprint11_dir/matriz.html"
python -m replayquant comparar --config experiments/sprint11-matriz-parcial.json --saida "$sprint11_dir/parcial" --formato html > "$sprint11_dir/parcial.html"
python -m replayquant comparar --config experiments/sprint11-matriz.json --saida "$sprint11_dir/repeticao" --formato json > "$sprint11_dir/repeticao.json"
python -m unittest discover -s tests -v
node --check replayquant/assets/chart.js
node --check replayquant/assets/equity.js
node --check replayquant/assets/indicators.js
git diff --check
```

Comparar arquivos de matriz e filhos repetidos por bytes, incluindo eventos, ledger e reservas. Testar os quatro formatos, `--analise` redundante no individual, saída existente, falha de escrita e execução de outra cwd com caminhos resolvidos pela receita. Inverter listas da matriz e verificar a paridade lógica da seção 8. Conferir também as demonstrações e exemplos expandidos das Sprints 07, 09 e 10, com seus parâmetros reais de risco/custos.

## 10. Critérios de aceite

1. Catálogo e schema 6 validam nomes, moedas, regras, filtros, datas e identidades por JSON/API. Hipóteses de regras são explícitas nos artefatos.
2. Os seis exemplos canônicos conferem com a seção 7, incluindo unidades, quantidades, taxas e saldo. Dados de ETH não aparecem rotulados BTC.
3. Troca de instrumento usa o mesmo núcleo financeiro e estratégias versionadas. Configurações anteriores conservam seus contratos e resultados financeiros.
4. Intercalar sessões, inverter a matriz e repetir execuções preserva isolamento, identidade lógica e resultados conforme a política declarada. Não compartilhar estado de indicador, caixa ou reserva.
5. Arquivo/evento de instrumento divergente, catálogo inválido e falha técnica não deixam mutação parcial ou resumo falso de sucesso. Duplicação idêntica continua inócua e conflito falha.
6. Listagem tardia, fim exclusivo, interseção vazia e dados fora da janela respeitam elegibilidade. Candles excluídos não aquecem e nenhuma ordem preenche fora da disponibilidade.
7. Lacuna interrompe antes do evento posterior. Prefixos anteriores são invariantes a mudanças futuras, também com ETH e catálogo. Preço antigo/futuro segue o contrato causal.
8. Finalização distingue disponibilidade de falta de abertura e conserva posição KEEP_OPEN. Reservas e benchmarks param no mesmo horizonte e reconciliam com suas moedas.
9. Ranking exibe custos, drawdown, trades, posição e cobertura, tem empates exatos e exclusões justificadas. Métricas indisponíveis são nulas, sem somar sessões numa carteira.
10. Identidade inclui catálogo e regras resolvidas. Mesmo snapshot/entrada reproduz artefatos. Reordenar receita conserva identidade lógica com proveniência original distinta.
11. HTML/Markdown/CSV/JSON/texto exibem instrumento e unidades corretos. Verificar HTML offline em desktop, tela estreita, impressão e sem JavaScript, com erros e requisições externas registrados.
12. Entregáveis, glossário e validação em português registram os comandos realmente executados. Resultados negativos e ausência de trades não impedem aceite de correção.

## 11. Prompt autossuficiente de execução

Copiar o bloco inteiro para implementar a etapa. Os contratos completos estão nas seções 1 a 10 deste documento versionado e devem ser lidos antes das alterações.

```text
Implemente a Sprint 11 — Múltiplos pares e catálogo do ReplayQuant em
/home/cams7/Dev/Cripto_Tests/replayquant, evoluindo o projeto até concluir código,
exemplos, testes e documentação.

Inspecione git status, HEAD, AGENTS.md aplicáveis e alterações existentes. A referência
consultada nesta especificação é c8df5ae. Preserve trabalho existente e posterior.
Leia integralmente docs/sprint11.md, seções 1 a 10, docs/planejamento.md e os contratos
anteriores com seus registros, especialmente Sprint 09 e Sprint 10. Confira a suíte
e as demonstrações de entrada da seção 9. Registre lacunas essenciais antes do trabalho
dependente. Use ambiente isolado, Python >=3.11, biblioteca padrão e unittest, com versão
concreta registrada. Reutilize assets/licenças e o núcleo financeiro existente.

Implemente o catálogo JSON schema 1 da seção 3 e seu snapshot imutável, validando também
pela API. Inclua origem, símbolo, base/cotação, intervalos, disponibilidade [início,fim),
filtros, rules_basis, rules_as_of e rules_source. Crie o catálogo canônico BTCUSDT/ETHUSDT
com regras sintéticas e o catálogo parcial da seção 7.2. Trate regras atuais aplicadas
ao período como hipótese explícita. Inclua hashes e regras resolvidas nos manifestos.

Implemente schema 6 mode STRATEGY, janela explícita e catálogo obrigatório no argumento
--catalogo de executar e na API. Use exatamente a configuração ETH/RSI da seção 4.1.
Os filtros vêm somente do catálogo. Preserve configurações 1/2/4/5 e relatórios legados,
incluindo balance.btc e BUY_HOLD_BTC nos caminhos antigos. Schema 6 implica análise
obrigatória e --analise redundante. Valide JSON estrito, campos, tipos, faixas, finitude,
UTC, intervalos e identidades em arquivos e modelos Python.

Generalize a validação hoje fixa em BTC e toda a cadeia de carteira, ledger, reservas,
risco, análise, benchmarks, exportações e gráficos para moeda base resolvida. No payload
novo use final_balance.asset_quantity, base_asset, quote_asset, símbolo/origem/intervalo
e BUY_HOLD_ASSET. Quantidades/volumes são base, preços são USDT/base, caixa/taxas são
USDT e RSI é adimensional. Não duplique o motor. Preserve Decimal/contexto local,
razões exatas, atomicidade, idempotência e políticas da Sprint 09/10.

Cada arquivo contém um único instrumento. Valide todo o arquivo antes do recorte e
recuse qualquer mistura ou divergência com catálogo/configuração. Candles só são
negociáveis quando contidos na janela e na disponibilidade. Excluídos não aquecem.
Reporte cobertura frente à janela e à interseção elegível, exclusões e motivos. Lacuna
interna interrompe no prefixo aceito. Par sem candle elegível gera combinação UNAVAILABLE,
código 2, métricas nulas e motivo, sem negociação. Erro estrutural gera código 1.

Bloqueie abertura fora da disponibilidade também pela API, sem mutação. Preserve a
resolução BAR_CLOSE_RESOLUTION no fim do último intervalo válido, conforme seção 5.
Pendência encerrada
pela disponibilidade usa INSTRUMENT_UNAVAILABLE; falta de abertura nos dados/janela usa
NO_FUTURE_OPEN. Preserve KEEP_OPEN e marca no último preço elegível. Finalização normal
libera reservas, lacuna as preserva. Benchmarks independentes usam filtros e mesmo
horizonte. Não liquidar ficticiamente no fim de disponibilidade nem antecipar sinais.

Implemente comparar --config --saida --formato e a receita de matriz da seção 6.1,
schema próprio 1. Resolva caminhos relativos à receita. Gere produto cartesiano das
três estratégias e dois datasets, sessões isoladas de 1000 USDT, ordem canônica e IDs
independentes da ordem das listas. Registre hash original de proveniência separado da
identidade lógica normalizada. A execução individual e o filho correspondente precisam
concordar em eventos/finanças, considerando os vínculos de identidade declarados.

Crie as fixtures de sete candles da seção 7.1, BTC e ETH=BTC/50, com abertura igual ao
fechamento anterior, volume 1 e OHLC consistente. Custos são taxa 0.001/slippage zero.
SMA/EMA 2/3 encerram com caixa 980.06008 USDT, posições 0.000166 BTC ou 0.00830 ETH,
patrimônio 993.34008 e código 2 pela saída final não executada. RSI 2, 30/70 encerra
uma operação por par, lucro -0.0398 USDT no par BTCUSDT e -0.03988 USDT no par ETHUSDT,
caixas 999.9602 e 999.96012, ativos zero e código 0. Confira as fórmulas e unidades
da seção 7, distinguindo os pares dos valores monetários. A matriz canônica retorna 2.

Implemente a comparação/ranking da seção 6.2, com capital/custos/risco, filtros, amostra,
drawdown, exposição, posição, cobertura e motivos por linha. Somente combinações FULL,
concluídas com código 0 e horizontes/condições comparáveis disputam ranking por retorno
patrimonial exato, com empates e ordenação estável. Não some resultados independentes
nem selecione automaticamente parâmetros ou uma estratégia para operar.

Entregue os onze artefatos schema 6 por filho, quatro resumos da matriz e diretórios
runs/<symbol>/<strategy_id> definidos na seção 8. Preserve INCOMPLETE em falhas parciais,
saída exclusiva e precedência de códigos 1 sobre 2 sobre 0. Verifique texto, JSON,
Markdown, HTML, CSV, unidades, catálogo, cobertura e navegação offline. Inspecione
desktop, tela estreita, impressão e alternativa sem JavaScript. Atualize README,
planejamento e documentação pertinente. Crie docs/sprint11-glossario.md e
docs/sprint11-validacao.md.

Teste os doze critérios da seção 10. Inclua listagem tardia/fim/interseção vazia, borda
sem dados, gap interno, preço antigo/futuro, evento estrangeiro, campos inválidos,
catálogo ausente/duplicado, isolamento intercalado, ordem invertida da matriz, cancelamento,
proteções, reconciliação e falha de escrita. Teste terceiro par fictício por catálogo,
sem mudar whitelist no motor. Execute e registre os comandos da seção 9, comparações
por bytes/lógicas, regressões das Sprints 06 a 10 e os exemplos expandidos existentes.

Corrija as falhas encontradas no escopo e conclua a implementação e documentação.
Não antecipe carteira compartilhada, ingestão real, banco, otimização, paralelismo ou
negociação conectada. No registro final informe arquivos alterados, decisões de modelos,
ambiente, comandos efetivamente executados, esperado/observado, limitações e pendências.
Marque como pendentes as verificações que não foram executadas.
```
