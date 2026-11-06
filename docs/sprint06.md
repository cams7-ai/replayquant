# Sprint 06 — Motor mínimo e operação manual

**Projeto:** ReplayQuant  
**Nível:** básico  
**Referência:** [Planejamento](planejamento.md), especialmente seções 4, 6, 21 e 23  
**Estado:** especificação preservada como referência; implementação e testes registrados em [sprint06-validacao.md](sprint06-validacao.md).

## 1. Objetivo e ponto de partida

Construir a primeira versão executável do ReplayQuant para compreender como eventos de mercado, ordens e preenchimentos alteram uma carteira Spot. O resultado será um replay local de candles fictícios, com ordens previamente roteirizadas e cálculos conferíveis manualmente.

Trabalhar na raiz `/home/cams7/Dev/Cripto_Tests/replayquant`, sem criar outro diretório `replayquant` ao redor do projeto. Esta sprint inaugura a implementação; não exige pacote, comandos ou entregas de código anteriores. Antes de implementar, inspecionar o estado real do repositório e preservar arquivos e alterações existentes. Os laboratórios SpotLab, PySpot, CandleVault, CrossSignal e RiskGate são referências conceituais, sem imports, cópia obrigatória de módulos ou dependências de execução.

Ao final, o estudante deverá conseguir explicar por que criar uma ordem não altera saldo, qual informação determina seu preenchimento, por que uma compra exige caixa para a taxa e como reproduzir cada alteração financeira.

## 2. Escopo e limites

Implementar pacote Python, configuração e entradas JSON versionadas, CLI, relógio simulado, leitura e validação de candles, roteiro manual, carteira em memória, ordens a mercado com preenchimento total, eventos estruturados, relatório mínimo e identificação reproduzível da execução.

Usar somente biblioteca padrão e `unittest`. Declarar Python >= 3.11 em `pyproject.toml`; fixar **3.12.14** em `.python-version` como versão de referência para reprodução. Registrar a versão realmente usada nas validações. Criar `requirements.lock` com comentário explícito de que não há dependências externas de execução/teste nesta sprint; execução local não exige instalação, gerenciador de pacotes ou acesso à rede.

O único instrumento é `FICTICIA/BTCUSDT/1m`: BTC base, USDT cotação, preços em USDT/BTC, quantidades e volumes em BTC, saldos e taxas em USDT. Saldo inicial em BTC é zero. USDT não é tratado como identidade do dólar.

Ficam fora: SMA e outros sinais automáticos, avaliação de estratégias, dimensionamento por risco, reservas, stops, alvos, limitadas, parciais, cancelamento operacional, livro de ofertas, liquidez real, slippage diferente de zero, múltiplos pares, carteira compartilhada, métricas de desempenho, benchmarks, ledger completo, SQLite, dados reais, API, credenciais, AWS, interface web e negociação real. O log inicial registra transições; o ledger e a curva patrimonial serão ampliados na Sprint 08.

## 3. Contratos de entrada

### 3.1. Regras comuns

- JSON UTF-8 estrito. Rejeitar chaves duplicadas em qualquer nível, campos ausentes/extras, constantes `NaN`/`Infinity` e tipos incorretos. `schema_version` deve ser inteiro 1, sem aceitar `true`, `1.0` ou `"1"`.
- Valores financeiros são strings com gramática `-?[0-9]+(\.[0-9]+)?`, ponto decimal, sem espaços, expoentes ou separadores de milhares. Converter diretamente para `Decimal`, sem `float` intermediário. Limitar a 18 dígitos no coeficiente e expoente decimal absoluto até 12 após conversão; zeros finais contam para esses limites de representação.
- Validar tipos e domínio também na API Python. Recusar floats, booleanos no lugar de números, valores não finitos e magnitudes fora do contrato. Preço/quantidade > 0; capital inicial > 0; volume >= 0; taxa fracionária em `[0, 1)`.
- Usar contexto decimal local novo, precisão 40 e `ROUND_HALF_EVEN`, preservando configuração, traps e flags do chamador. Aritmética financeira que não possa ser representada exatamente nesse contexto deve falhar antes da mutação, com diagnóstico; não aceitar arredondamento silencioso de saldos. Divisões para apresentação podem arredondar em contexto local separado.
- Horários ISO 8601 com fuso obrigatório, normalizados para UTC. Serializar datas canônicas com microssegundos e offset `+00:00`. O relógio de parede não determina eventos, IDs ou decisões.
- Validar arquivos inteiros antes de iniciar o replay. Erro estrutural não produz simulação parcial. Duplicatas de domínio equivalentes podem ser ignoradas conforme as regras abaixo, mantendo diagnóstico.

### 3.2. Candles

Arquivo `data/fixtures/sprint06-candles.json`, envelope com exatamente `schema_version` e `candles`. Cada candle contém exatamente:

| Campo | Contrato |
| --- | --- |
| `source`, `symbol`, `interval` | Respectivamente `FICTICIA`, `BTCUSDT`, `1m` |
| `open_time`, `close_time` | Datas com fuso; abertura alinhada ao minuto; duração exata de um minuto |
| `open`, `high`, `low`, `close` | Strings decimais positivas, com `low <= open/close <= high` |
| `volume` | String decimal não negativa, em BTC |
| `is_closed` | Booleano JSON; nesta sprint, deve ser `true` |

O intervalo é `[open_time, close_time)`. A disponibilidade do candle completo é assumida no fechamento; isso é convenção fictícia, sem alegação de latência observada. Candles abertos são recusados nesta entrada de replay, sem alimentar o motor.

Identidade: `(source, symbol, interval, open_time)`. Repetição numericamente equivalente da mesma chave é ignorada, sem novos eventos de mercado; conteúdo divergente é erro. Após deduplicação, exigir ordem crescente e continuidade minuto a minuto. Não ordenar nem preencher lacunas silenciosamente. Como o arquivo inteiro é validado antes do replay, uma lacuna nesta sprint impede o início; a detecção incremental será necessária ao ampliar o replay. A lista deve conter pelo menos um candle.

### 3.3. Configuração e roteiro

Arquivo `experiments/sprint06-manual.json`, com exatamente os campos abaixo:

```json
{
  "schema_version": 1,
  "source": "FICTICIA",
  "symbol": "BTCUSDT",
  "interval": "1m",
  "initial_cash": "1000",
  "quantity": "0.001",
  "fee_rate": "0.001",
  "slippage_rate": "0",
  "orders": [
    {"id": "compra-01", "at_close": "2026-01-01T12:01:00+00:00", "side": "BUY"},
    {"id": "venda-01", "at_close": "2026-01-01T12:02:00+00:00", "side": "SELL"}
  ]
}
```

`quantity` é fixa para todas as ordens; `fee_rate` é a alíquota fracionária nas duas pontas; `slippage_rate` precisa ser exatamente zero. Origem/par/intervalo precisam corresponder aos candles. Não oferecer parâmetros de estratégias nesta etapa.

Cada item de `orders` tem exatamente `id`, `at_close` e `side`. IDs não vazios, sem espaços nas extremidades; lado `BUY` ou `SELL`; instante referente a um fechamento existente. A lista pode ser vazia e deve estar em ordem temporal não decrescente. Ordens no mesmo fechamento seguem a ordem explícita do roteiro. Não alterar essa ordem para melhorar o resultado. Repetir ID com o mesmo conteúdo normalizado é inócuo, inclusive após estado terminal; reutilizar ID com conteúdo diferente invalida a configuração.

## 4. Eventos, relógio e execução

### 4.1. Ordem temporal

Para cada minuto de fronteira, processar nesta ordem:

1. Fechamento do candle anterior, se existir: liberar o OHLCV completo.
2. Submissões manuais vinculadas a esse fechamento, na ordem do roteiro.
3. Abertura do candle seguinte, se existir: liberar somente identidade, horário e preço de abertura; tentar preencher a ordem pendente.

Na primeira abertura não há fechamento anterior nem ordem pendente. No último fechamento ainda é possível criar ordem; sem outra abertura, ela termina não executada. Registrar sequência inteira monotônica `seq` além do timestamp: submissão e preenchimento podem ter o mesmo horário nominal, mas o preenchimento precisa ter sequência estritamente posterior. Essa convenção representa latência zero entre eventos distintos, sem preencher na própria fase de submissão.

A fila pode ser preparada a partir do arquivo completo, mas o evento de abertura não pode expor high, low, close ou volume final. Alterar esses campos de um candle, mantendo a abertura e a validade dos dados, não muda um preenchimento já ocorrido na abertura. Alterar candles posteriores não muda o prefixo de eventos financeiros anteriores; hashes globais do experimento podem mudar.

### 4.2. Estados e validação financeira

Estados mínimos: `NEW`, `FILLED`, `REJECTED`, `UNEXECUTED`. Fluxos permitidos: solicitação válida aceita em `NEW`; solicitação recusada em `REJECTED`; `NEW -> FILLED` na próxima abertura; `NEW -> REJECTED` se a revalidação falhar; `NEW -> UNEXECUTED` ao encerrar sem abertura futura. Terminais não sofrem novas transições.

Permitir no máximo uma ordem pendente no experimento e uma posição de quantidade fixa: `BUY` exige BTC zero; `SELL` exige BTC suficiente para a quantidade fixa. Não acumular compras sobre posição aberta. Solicitação concorrente é rejeitada, preservando a ordem já pendente. Não reservar nem debitar ao aceitar uma ordem.

Na submissão, validar pendência, posição e, para compra, estimativa de caixa com taxa usando o último fechamento disponível. Validar nessa ordem para produzir motivos determinísticos. Essa estimativa não garante o preço da próxima abertura. No preenchimento, revalidar caixa com taxa e quantidade disponível usando o preço efetivo; rejeitar integralmente se faltar saldo, sem reduzir a quantidade e sem caixa negativo. Não consultar a próxima abertura antecipadamente para aceitar a ordem.

Motivos estáveis mínimos: `ORDER_PENDING`, `POSITION_OPEN`, `INSUFFICIENT_CASH`, `INSUFFICIENT_ASSET`, `NO_FUTURE_OPEN`. Erros de estrutura/domínio de entrada são distintos dessas rejeições. Aceitar/rejeitar/encerrar ordem não altera saldos; somente um preenchimento válido altera caixa e BTC atomicamente.

O preço executado é o `open` da próxima abertura contígua após a submissão. O preenchimento é total, uma única vez. Quantidade não é limitada pelo volume OHLCV: trata-se de hipótese explícita de liquidez ilimitada deste modelo fictício, sem comprovar negociabilidade. Não atribuir spread zero observado: não há modelo de spread; slippage zero é configurado.

### 4.3. Fórmulas e idempotência

Com preço `p`, quantidade `q` e alíquota `f`:

```text
bruto = p * q                        [USDT]
taxa = bruto * f                     [USDT]
compra: caixa -= bruto + taxa; BTC += q
venda:  caixa += bruto - taxa; BTC -= q
```

Taxa cobrada somente no preenchimento, em USDT. Não descontar spread/slippage novamente. Calcular e validar todos os novos valores antes de efetivar a transição. IDs de execução podem ser derivados como `<order_id>:fill:1`, únicos dentro do experimento. Aplicar novamente uma execução idêntica é inócuo; mesmo ID com conteúdo financeiro ou referência de ordem divergente é erro sem mutação, inclusive após preenchimento terminal. O registro de deduplicação é em memória, sem recuperação após reinício.

## 5. Fixture obrigatória e resultados manuais

Criar o arquivo completo abaixo, sem rede ou números aleatórios:

```json
{
  "schema_version": 1,
  "candles": [
    {
      "source": "FICTICIA", "symbol": "BTCUSDT", "interval": "1m",
      "open_time": "2026-01-01T12:00:00+00:00", "close_time": "2026-01-01T12:01:00+00:00",
      "open": "100000", "high": "100000", "low": "100000", "close": "100000",
      "volume": "1", "is_closed": true
    },
    {
      "source": "FICTICIA", "symbol": "BTCUSDT", "interval": "1m",
      "open_time": "2026-01-01T12:01:00+00:00", "close_time": "2026-01-01T12:02:00+00:00",
      "open": "100000", "high": "101000", "low": "100000", "close": "101000",
      "volume": "1", "is_closed": true
    },
    {
      "source": "FICTICIA", "symbol": "BTCUSDT", "interval": "1m",
      "open_time": "2026-01-01T12:02:00+00:00", "close_time": "2026-01-01T12:03:00+00:00",
      "open": "101000", "high": "101000", "low": "101000", "close": "101000",
      "volume": "1", "is_closed": true
    }
  ]
}
```

Usar a configuração da seção 3.3. Começar com 1.000 USDT e 0 BTC, solicitar compra após o fechamento de 12:01 e venda após o de 12:02. Os preços vêm dos eventos de abertura; não são preços de execução fornecidos pelo roteiro.

| Etapa | Bruto USDT | Taxa USDT | Fluxo de caixa USDT | Caixa após etapa USDT | BTC após etapa |
| --- | --- | --- | --- | --- | --- |
| Inicial | — | — | — | 1000 | 0 |
| Compra de 0,001 BTC a 100000 | 100 | 0.1 | -100.1 | 899.9 | 0.001 |
| Venda de 0,001 BTC a 101000 | 101 | 0.101 | +100.899 | 1000.799 | 0 |

Bruto da operação: `101 - 100 = 1 USDT`; taxas totais: `0.201 USDT`; resultado líquido realizado da ida e volta: `100.899 - 100.1 = 0.799 USDT`. O relatório desta sprint precisa mostrar esses cálculos, sem exigir métricas percentuais ou curva patrimonial.

Se o roteiro ficar vazio, caixa final = 1000, BTC = 0 e taxas = 0; resultado de ida e volta fica `null` com motivo `NO_CLOSED_ROUND_TRIP`. Se houver somente compra, manter a posição aberta; não criar venda fictícia, marcação a mercado ou lucro realizado inventado. Para manter o relatório mínimo, o campo de resultado agregado de ida e volta só é aplicável quando houve exatamente uma compra seguida de uma venda integral e a posição final é zero; em outros casos usar `null` com `ROUND_TRIP_NOT_APPLICABLE`. Sempre informar saldos, taxas e execuções reais da simulação.

## 6. Artefatos e CLI

Organização sugerida, ajustável sem alterar os contratos públicos:

```text
.python-version
pyproject.toml
requirements.lock
.gitignore
README.md
replayquant/__init__.py
replayquant/__main__.py
replayquant/validation.py
replayquant/models.py
replayquant/data.py
replayquant/engine.py
replayquant/execution.py
replayquant/portfolio.py
replayquant/reporting.py
data/fixtures/sprint06-candles.json
experiments/sprint06-manual.json
tests/test_sprint06.py
docs/sprint06.md
docs/sprint06-validacao.md
docs/sprint06-glossario.md
```

Não criar módulos vazios das sprints futuras. Ignorar `.venv/`, `__pycache__/` e `runs/`. `demonstrar` usa os dois arquivos versionados acima; documentar que os comandos são executados da raiz.

CLI a implementar:

```bash
python -m replayquant --help
python -m replayquant demonstrar --formato texto
python -m replayquant demonstrar --formato json
python -m replayquant executar --dados data/fixtures/sprint06-candles.json --config experiments/sprint06-manual.json --saida runs/sprint06-manual --formato texto
```

`--formato` aceita `texto` (padrão) e `json` em ambos os subcomandos. `executar` exige `--dados`, `--config` e `--saida`. `demonstrar` não grava arquivos. `executar` cria um diretório de saída novo, incluindo pais necessários; recusa diretório/arquivo já existente, sem sobrescrever ou apagar conteúdo. Validar entradas antes de criar a saída. Uma falha de escrita deve ser relatada como técnica; arquivos incompletos nunca representam uma execução bem-sucedida.

Artefatos de `executar`: `manifest.json`, `events.jsonl`, `report.json`. Todos incluem `schema_version: 1`; números financeiros em strings sem perda de precisão, ausências em `null` com motivo. O formato texto explica fórmulas, unidades e limitações; a saída JSON em stdout é somente o relatório, sem mensagens de progresso. Diagnósticos da CLI ficam em stderr.

O log deve conter abertura/fechamento, submissão, aceitação/rejeição, preenchimento e encerramento, com `seq`, horário simulado, tipo, `run_id`, referências de ordem/execução quando aplicáveis, motivo e saldos antes/depois nas transições financeiras. Aberturas não contêm OHLCV futuro. Registrar diagnóstico de duplicatas ignoradas sem duplicar eventos de mercado ou taxas.

O manifesto registra SHA-256 dos bytes de dados/configuração, hash do código, versão do pacote, Python real, política decimal, modelo de execução, taxa/slippage e ausência de aleatoriedade (`seed: null`, com motivo). Para o hash do código, usar caminhos relativos ordenados e hashes dos bytes de todos os `.py` sob `replayquant/`, mais `pyproject.toml`, `requirements.lock` e `.python-version`; armazenar essa lista no manifesto e hashear sua serialização JSON canônica UTF-8 (`sort_keys=True`, separadores `(',', ':')`). Não depender de commit Git limpo ou disponível. Derivar `run_id` por SHA-256 de JSON canônico com hashes de dados/configuração/código e versão Python real; diretório de saída e hora real não entram na identidade. Duas saídas em diretórios diferentes com entradas, código e Python iguais devem ser idênticas byte a byte nos três arquivos.

| Código | Significado |
| --- | --- |
| 0 | Replay concluído sem ordens rejeitadas ou não executadas; inclui roteiro vazio |
| 1 | Arquivo/configuração/dados inválidos, falha aritmética ou técnica, incluindo saída existente |
| 2 | Replay concluído com ordem rejeitada ou não executada; relatório e diagnóstico preservados |

`argparse` também retorna 2 para erro de sintaxe, sem iniciar o replay. Uma falha inesperada deve encerrar com erro e diagnóstico, sem ser convertida em rejeição de ordem. O caso principal de `demonstrar` retorna 0 somente se os resultados conferirem com os valores obrigatórios.

## 7. Verificação e critérios de aceite

Implementar testes de comportamento com `unittest`, cobrindo pelo menos:

1. Exemplo principal: duas execuções, taxas 0.201, resultado 0.799, caixa 1000.799 e BTC zero, comparados com `Decimal` exato.
2. Submissão não altera saldo; execução só ocorre em evento posterior; fechamento e abertura no mesmo timestamp respeitam `seq`.
3. Compra com capital 100 USDT e taxa 0.001 é rejeitada, pois custa 100.1; não há débito nem posição.
4. Revalidação: manter fechamento inicial 100000 e elevar somente a abertura seguinte para 101000 com OHLC consistente; capital 100.1 aceita a estimativa, mas rejeita o preenchimento de 101.101 USDT, preservando saldo.
5. Venda sem BTC, compra com posição aberta e segunda ordem no mesmo fechamento são rejeitadas com motivo estável; pendência anterior é preservada.
6. Submissão no último fechamento termina `UNEXECUTED/NO_FUTURE_OPEN`, sem taxa. Roteiro vazio e posição final aberta respeitam a seção 5.
7. Repetições idênticas de ordem, candle e execução não repetem efeitos; conflitos preservam o estado e falham na camada apropriada.
8. JSON malformado, chaves duplicadas, schema booleano, campos extras/ausentes, floats, não finitos, taxa inválida, slippage não zero, datas sem fuso, OHLC inconsistente, aberto, ordem temporal inválida e lacuna são recusados. Datas com offsets equivalentes normalizam para o mesmo instante.
9. Mudanças válidas em high/low/close/volume futuros não alteram preenchimento anterior; mudança de sufixo preserva o prefixo financeiro, desconsiderando identificação global do experimento.
10. Precisão/traps/flags externos não alteram os resultados nem são modificados. Falhas aritméticas não produzem mutação parcial.
11. CLI: ajuda, texto/JSON, códigos 0/1/2, três artefatos válidos, recusa de sobrescrita e duas execuções iguais em diretórios distintos. Nada depende de rede, data real, caminho absoluto do repositório ou projetos vizinhos.

Preparação e comandos previstos para o implementador, na raiz do projeto:

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python --version
python -m replayquant --help
python -m replayquant demonstrar --formato texto
python -m replayquant demonstrar --formato json
python -m unittest discover -s tests -v
```

Para verificar arquivos e reprodução sem reutilizar uma saída existente, executar na mesma sessão Bash:

```bash
validacao_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint06-candles.json --config experiments/sprint06-manual.json --saida "$validacao_dir/execucao-a" --formato json
python -m replayquant executar --dados data/fixtures/sprint06-candles.json --config experiments/sprint06-manual.json --saida "$validacao_dir/execucao-b" --formato json
cmp "$validacao_dir/execucao-a/manifest.json" "$validacao_dir/execucao-b/manifest.json"
cmp "$validacao_dir/execucao-a/events.jsonl" "$validacao_dir/execucao-b/events.jsonl"
cmp "$validacao_dir/execucao-a/report.json" "$validacao_dir/execucao-b/report.json"
git diff --check
```

Todos esses comandos devem retornar 0 no exemplo principal. Os casos negativos e os códigos 1/2 são verificados pela suíte, sem deixar o procedimento manual ambíguo. Registrar cada código realmente observado; não inferir sucesso do último comando para os anteriores.

Aceite exige testes relevantes aprovados, reprodução demonstrada, saldos não negativos, nenhuma venda descoberta, documentação em português e explicação dos limites do modelo. O glossário deve explicar evento, replay, relógio simulado, candle, ordem, preenchimento, pendência, taxa, idempotência, hash e distinção entre caixa e resultado. O roteiro de validação separa resultados esperados, observados, comandos não executados e pendências. Criar este documento de especificação, isoladamente, não conclui a implementação da Sprint 06.

## 8. Prompt autossuficiente de execução

Copie o bloco inteiro para um agente com acesso ao repositório. Os contratos detalhados estão neste documento versionado, cuja leitura é obrigatória; não dependem da conversa original.

````text
Implemente a Sprint 06 — Motor mínimo e operação manual do ReplayQuant.

DIRETÓRIO E ENTRADA
Trabalhe em /home/cams7/Dev/Cripto_Tests/replayquant, que já é a raiz do projeto.
Antes de editar, inspecione git status, arquivos existentes e instruções AGENTS.md
aplicáveis. Leia integralmente docs/sprint06.md e docs/planejamento.md,
principalmente as regras transversais e o escopo da Sprint 06. Este documento
(docs/sprint06.md, seções 1 a 7) fixa entradas, schemas, fases temporais, estados,
exemplos, CLI, artefatos e aceite; implemente esses contratos sem adivinhá-los.
Se ele estiver ausente ou houver contradição essencial, registre a lacuna antes
de executar trabalho dependente. Não exija código de sprints anteriores: esta
é a implementação inicial. Preserve trabalho existente e projetos vizinhos.

OBJETIVO
Entregar um motor local de replay Spot fictício BTCUSDT/1m, com ordens manuais
roteirizadas, carteira em memória e alterações financeiras auditáveis. Implemente,
teste e documente; não entregue apenas uma proposta. A fixture comprova correção
contábil e temporal, sem evidenciar rentabilidade de estratégia.

ESCOPO E TECNOLOGIA
Use biblioteca padrão e unittest, Python >= 3.11, versão de referência 3.12.14
em .python-version, metadados em pyproject.toml e requirements.lock declarando
ausência de dependências externas. Execute em .venv, sem instalação de pacotes
ou rede. Não importe SpotLab, PySpot, CandleVault, CrossSignal ou RiskGate.
Não implemente indicadores, gestão de risco, reservas, stops, limitadas,
parciais, livro, dados reais, banco, web, AWS ou ordens reais. Não antecipe
as sprints 07 a 20. Crie apenas módulos com responsabilidade presente.

CONTRATOS A IMPLEMENTAR
1. Implemente os schemas exatos das seções 3 e 5 de docs/sprint06.md.
   Use JSON estrito versionado, Decimal a partir de strings, validação também
   na API Python, limites de representação e contexto local de precisão 40
   com ROUND_HALF_EVEN. Não use float financeiro nem arredondamento silencioso
   de saldos; preserve o contexto externo e rejeite operações inexatas antes
   da mutação. Use datas com fuso normalizadas em UTC.
2. Valide arquivos integralmente antes do replay: candles fechados consistentes,
   identidade por origem/par/intervalo/abertura, duplicatas equivalentes inócuas,
   conflito como erro, ordem cronológica e continuidade. Não ordene ou complete
   lacunas silenciosamente. Configuração fixa slippage zero, quantidade única,
   taxas em USDT e ordens BUY/SELL vinculadas a fechamentos existentes.
3. Processe fechamento, submissões desse fechamento e abertura seguinte nessa
   ordem. A abertura expõe apenas identidade, horário e open. Uma ordem só
   preenche em evento de sequência posterior, mesmo se o timestamp coincidir.
   Não consulte high/low/close/volume final para preencher na abertura.
4. Implemente NEW, FILLED, REJECTED e UNEXECUTED; uma pendência e uma posição
   de quantidade fixa. Submissão não altera saldos; valide posição/caixa com
   taxa ao aceitar e revalide no preço da abertura. Sem BTC não há venda;
   sem caixa suficiente não há compra. Não reduza quantidade ou permita caixa
   negativo. Ao terminar sem abertura futura, registre NO_FUTURE_OPEN.
5. Cada preenchimento total cobra p*q*fee_rate em USDT. Compra debita
   p*q*(1+fee_rate) e soma q BTC; venda credita p*q*(1-fee_rate) e subtrai q BTC.
   Efetive a atualização atomicamente. Liquidez ilimitada é hipótese fictícia,
   não informação inferida do volume. Não desconte custos duas vezes.
6. Garanta IDs determinísticos e idempotência de ordens/execuções. Duplicata
   idêntica não repete efeitos; ID conflitante é erro sem mutação. Registre
   eventos estruturados, motivos estáveis e saldos antes/depois.
7. Implemente demonstrar e executar com as opções, arquivos, códigos de saída
   e política de não sobrescrita da seção 6. Gere manifesto, events.jsonl e
   report.json com schemas versionados, strings decimais e hashes de entradas
   e código. Implemente exatamente a definição de hash/run_id da seção 6.
   Não use hora real ou diretório de saída na identidade ou nos artefatos.

EXEMPLO OBRIGATÓRIO
Crie data/fixtures/sprint06-candles.json com os três candles completos da seção 5
e experiments/sprint06-manual.json com o JSON da seção 3.3. Capital 1000 USDT,
BTC zero, quantidade 0.001, taxa 0.001 e slippage 0. Compra submetida no fechamento
12:01 UTC de 2026-01-01 preenche na abertura seguinte a 100000; venda submetida
no fechamento 12:02 preenche na abertura seguinte a 101000.
Compra: bruto 100, taxa 0.1, desembolso 100.1; caixa 899.9 e BTC 0.001.
Venda: bruto 101, taxa 0.101, recebimento 100.899; caixa 1000.799 e BTC zero.
Taxas 0.201, resultado líquido da ida e volta 0.799 USDT, com Decimal exato.
Explique fórmulas e unidades. Sem ida e volta aplicável, use null com motivo,
conforme seção 5, sem fabricar resultado ou liquidar posição aberta.

TESTES E ACEITE
Implemente todos os casos da seção 7: exemplo exato, precedência temporal,
rejeições sem mutação, saldo com taxa, gap de preço que invalida saldo, pendência
concorrente, posição aberta, última ordem sem evento futuro, roteiro vazio,
idempotência/conflitos, JSON e dados inválidos, UTC, causalidade por prefixo,
contexto decimal isolado, artefatos e códigos da CLI. Compare duas execuções
em diretórios distintos byte a byte, incluindo manifesto, eventos e relatório.
Corrija falhas até a suíte relevante passar; nunca altere os valores esperados
para acomodar um defeito. Não alegue testes não executados como aprovados.

COMANDOS E DOCUMENTAÇÃO
Execute na raiz:
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python --version
python -m replayquant --help
python -m replayquant demonstrar --formato texto
python -m replayquant demonstrar --formato json
python -m unittest discover -s tests -v

Na mesma sessão Bash, execute:
validacao_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint06-candles.json --config experiments/sprint06-manual.json --saida "$validacao_dir/execucao-a" --formato json
python -m replayquant executar --dados data/fixtures/sprint06-candles.json --config experiments/sprint06-manual.json --saida "$validacao_dir/execucao-b" --formato json
cmp "$validacao_dir/execucao-a/manifest.json" "$validacao_dir/execucao-b/manifest.json"
cmp "$validacao_dir/execucao-a/events.jsonl" "$validacao_dir/execucao-b/events.jsonl"
cmp "$validacao_dir/execucao-a/report.json" "$validacao_dir/execucao-b/report.json"
git diff --check

Registre o código de saída de cada comando: no caso principal espera-se 0.
Verifique os códigos 1 e 2 dos casos negativos pela suíte. Se Python de referência
não estiver disponível, registre a versão usada e a limitação, sem instalar ou
alterar o sistema silenciosamente. Falta de pré-requisito não autoriza inventar
resultados. Não faça commit, publicação ou alterações externas.

Entregue o código, fixtures, configuração, metadados e README em português,
docs/sprint06-validacao.md e docs/sprint06-glossario.md. Preserve a especificação
como referência e registre decisões necessárias sem ampliar o escopo. A validação
deve distinguir esperado, observado e não executado, com limitações e pendências.
Na resposta final, informe arquivos alterados, comandos realmente executados,
resultados observados e limitações. Não declare concluída a sprint se faltar
requisito obrigatório de implementação ou validação.
````
