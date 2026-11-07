# Sprint 07 — Estratégia SMA e causalidade

**Projeto:** ReplayQuant  
**Nível:** básico  
**Referência:** [Planejamento](planejamento.md), especialmente seções 4, 7, 21 e 23  
**Pré-requisito:** [Sprint 06](sprint06.md), com [validação registrada](sprint06-validacao.md)  
**Estado:** especificação preservada como referência; implementação e verificações registradas em [sprint07-validacao.md](sprint07-validacao.md).

## 1. Objetivo e ponto de partida

Evoluir o motor existente para produzir sinais de cruzamento de médias móveis simples (SMA) usando apenas candles fechados já disponíveis. Separar avaliação, sinal, decisão, ordem e preenchimento, demonstrando por que o preço da próxima abertura não pode participar da decisão no fechamento anterior.

Trabalhar na raiz `/home/cams7/Dev/Cripto_Tests/replayquant`. Antes de editar código, inspecionar instruções `AGENTS.md` aplicáveis, `git status`, implementação, testes e documentos da Sprint 06. Confirmar os pré-requisitos pela suíte existente; registros anteriores não substituem a verificação do estado atual. Preservar trabalho alheio e registrar lacunas essenciais antes do trabalho dependente.

Esta etapa evolui o mesmo projeto; não recriar o pacote nem importar SpotLab, PySpot, CandleVault, CrossSignal ou RiskGate. O modo manual continua disponível para regressão e aprendizado. O modo SMA substitui o roteiro como origem das ordens em seus próprios experimentos, sem combinar as duas fontes.

## 2. Escopo e limites

Implementar SMA curta/longa configuráveis, aquecimento, cruzamentos exatos, estratégia incremental, intenção pendente, rastreabilidade e slippage percentual fixo adverso. Manter um instrumento `FICTICIA/BTCUSDT/1m`, posição comprada de quantidade fixa, BTC inicial zero, taxa em USDT, preenchimento total e no máximo uma ordem pendente.

Usar biblioteca padrão e `unittest`, Python >= 3.11 e versão de referência 3.12.14, conforme os metadados existentes. Não instalar dependências nem acessar rede. Preservar CLI manual, formatos texto/JSON/HTML, não sobrescrita e identificação reproduzível dos experimentos.

Ficam fora: EMA/RSI, otimização de parâmetros, risco por patrimônio, reservas, stops, alvos, vendas descobertas, parciais, limitadas, liquidez real, latência positiva, cancelamento operacional pela CLI, múltiplos pares, métricas/benchmarks da Sprint 08, dados históricos reais, persistência operacional, web, AWS e negociação real. A fixture valida lógica e contabilidade; não mede desempenho de investimento.

## 3. Entradas, versões e precisão

### 3.1. Contratos preservados

Reutilizar o schema de candles versão 1 da seção 3.2 da Sprint 06: envelope `schema_version`/`candles`, identidade por origem/par/intervalo/abertura, candles fechados de um minuto em UTC, OHLC consistente e volume base não negativo. Não expor candle aberto à estratégia.

Preservar JSON estrito, rejeição de campos inesperados/ausentes, chaves duplicadas, não finitos, booleanos como números e datas sem fuso. Valores financeiros são strings na gramática `-?[0-9]+(\.[0-9]+)?`, com até 18 dígitos no coeficiente e expoente decimal absoluto até 12, inclusive zeros finais. Validar também construções diretas pela API Python.

Contabilidade usa `Decimal`, contexto local novo com precisão 40 e `ROUND_HALF_EVEN`, sem alterar contexto, traps ou flags externos. Aritmética financeira inexata falha antes da mutação. Indicadores para apresentação podem arredondar em contexto separado; a apresentação não decide cruzamentos. Não converter valores financeiros em `float`.

### 3.2. Configuração SMA

Criar `experiments/sprint07-sma.json` com exatamente:

```json
{
  "schema_version": 2,
  "source": "FICTICIA",
  "symbol": "BTCUSDT",
  "interval": "1m",
  "initial_cash": "1000",
  "quantity": "0.001",
  "fee_rate": "0.001",
  "slippage_rate": "0.001",
  "strategy": {
    "name": "SMA_CROSS",
    "short_window": 2,
    "long_window": 3
  }
}
```

`short_window` e `long_window` são inteiros estritos, sem booleanos, satisfazendo `1 <= short_window < long_window`. Validar antes de iniciar o replay. `fee_rate` e `slippage_rate` são frações em `[0, 1)`; `0.001` significa 0,10%. Capital e quantidade são positivos. Não aceitar `orders` nesta configuração nem parâmetros desconhecidos de estratégia.

A versão 1 manual conserva seus campos e a exigência de slippage zero. A versão 2 desta sprint identifica exclusivamente o modo SMA acima. Não reinterpretar configurações antigas silenciosamente. Artefatos SMA usam `schema_version: 2`; preservar os schemas e contratos públicos do modo manual versão 1. Documentar o despacho de versões na API e na CLI.

### 3.3. Validação estrutural e continuidade

Validar integralmente estrutura, tipos, domínio de cada candle, identidades conflitantes e ordem cronológica antes de iniciar. Erro estrutural, conflito ou evento fora de ordem impede o replay; não ordenar silenciosamente. Duplicata equivalente é inócua e diagnosticada, sem alimentar a SMA duas vezes.

No modo SMA, separar essa validação da verificação de continuidade, que ocorre incrementalmente na fronteira de cada nova abertura. Assim uma lacuna pode interromper uma execução após um prefixo válido. Essa evolução é necessária: a Sprint 06 rejeita lacunas antes de iniciar e esse comportamento permanece no modo manual. A API incremental SMA também verifica duplicatas, conflitos e ordem antes de mutar estado; conflito em fluxo interrompe com erro sem incorporar o evento divergente.

## 4. SMA, cruzamento e decisões

### 4.1. Histórico e comparação exata

Numerar os fechamentos contíguos aceitos por `k`, começando em 1. Com preço de fechamento `C`, janela curta `s` e longa `l`:

```text
S_s(k) = soma dos últimos s fechamentos até k
S_l(k) = soma dos últimos l fechamentos até k
SMA_s(k) = S_s(k) / s
SMA_l(k) = S_l(k) / l
D(k) = sinal de [l * S_s(k) - s * S_l(k)]
```

Comparar por somas/razões exatas. Uma implementação possível converte os `Decimal` para inteiros numa escala decimal comum e usa somas e produtos de inteiros Python; outra pode usar razões exatas da biblioteca padrão. Não decidir com médias arredondadas nem com somas que tenham perdido precisão. Usar somente o histórico necessário, sem impor limite artificial ao número de candles do arquivo.

Com `k < l`, médias completas não estão disponíveis. Com `k = l`, há médias atuais, mas não há par anterior completo. A primeira comparação exige `l + 1` candles fechados contíguos. Registrar uma avaliação por fechamento aceito, incluindo aquecimento com motivo `WARMUP`, quantidade observada e valores disponíveis; ausências são `null` com motivo.

### 4.2. Desigualdades e posição

| Condição | Sinal |
| --- | --- |
| `D(k-1) <= 0` e `D(k) > 0` | `BUY` |
| `D(k-1) >= 0` e `D(k) < 0` | `SELL` |
| Demais casos, incluindo `D(k) = 0` | Nenhum, motivo `NO_CROSS` |

Igualdade anterior pode iniciar cruzamento; igualdade atual não sinaliza. Permanecer acima ou abaixo não repete sinal. Não comprar simplesmente porque a primeira média disponível está acima. Atualizar o histórico comparável mesmo quando uma decisão for bloqueada.

O sinal descreve o cruzamento matemático independentemente da carteira. Uma decisão separada verifica, nesta ordem, pendência, posição e caixa estimado. Sinal BUY com posição aberta é bloqueado com `POSITION_OPEN`; sinal SELL sem quantidade disponível, com `INSUFFICIENT_ASSET`; pendência, com `ORDER_PENDING`; compra sem caixa estimado com taxa/slippage, com `INSUFFICIENT_CASH`. Bloqueio não cria ordem nem altera saldo; vincular o diagnóstico ao sinal.

Uma decisão aprovada cria uma intenção identificada e uma ordem de mercado `NEW`, vinculadas ao sinal. Sinal não altera caixa, posição ou reservas. Não há reserva nesta etapa. A ordem preenche integralmente na próxima abertura elegível ou termina rejeitada/não executada. Não acumular compras nem reduzir quantidade para caber no saldo.

Uma intenção pendente bloqueia outra para a mesma posição, inclusive na API incremental. Rejeição de preenchimento libera a pendência e conserva a posição. Não reenviar a intenção recusada em fechamentos posteriores apenas porque a SMA continua do mesmo lado; nova tentativa exige novo cruzamento. Uma eventual integração que cancele uma intenção deve obedecer à mesma regra, sem exigir criar um subsistema de cancelamento nesta sprint. Falha técnica é interrupção, não rejeição por política nem convite para nova tentativa automática.

## 5. Relógio, execução e lacunas

### 5.1. Ordem causal dos eventos

Em uma fronteira contígua, processar:

1. `CLOSE`: disponibilizar candle encerrado.
2. `EVALUATION`: atualizar SMA com esse fechamento e avaliar cruzamento.
3. `SIGNAL`, se houver; `DECISION` com aprovação/bloqueio; submissão e aceitação da ordem quando aprovada.
4. `OPEN` do candle seguinte: disponibilizar somente identidade, horário e preço de abertura.
5. Preenchimento ou rejeição da ordem pendente, com sequência posterior à submissão.

Eventos podem compartilhar timestamp nominal, mas `seq` inteiro estritamente crescente define sua precedência. É uma convenção de latência zero entre eventos distintos. Não exigir timestamp estritamente maior, não preencher na fase de sinal e não consultar abertura futura para aprovar uma decisão. A estratégia recebe somente fechamentos liberados e informações da carteira já consolidadas; não recebe o arquivo completo, a fila futura ou o OHLCV completo na abertura.

IDs determinísticos devem distinguir avaliação, sinal, decisão, intenção, ordem e execução dentro do experimento. Os eventos devem permitir seguir essas referências, mantendo a convenção de deduplicação local. Repetição idêntica é inócua; mesmo ID com conteúdo divergente é erro sem mutação do histórico aceito. Não prometer recuperação após reinício.

### 5.2. Slippage e taxas

Com abertura `o`, slippage fracionário `a`, quantidade `q` e taxa `f`:

```text
p_compra = o * (1 + a)               [USDT/BTC]
p_venda  = o * (1 - a)               [USDT/BTC]
bruto = p * q                       [USDT]
taxa = bruto * f                    [USDT]
compra: caixa -= bruto + taxa; BTC += q
venda:  caixa += bruto - taxa; BTC -= q
```

Na decisão de compra, estimar desembolso substituindo `o` pelo último fechamento disponível, já com slippage e taxa. Na abertura, recalcular com seu preço e revalidar caixa/posição antes de qualquer mutação. Uma alta na abertura pode invalidar a estimativa: rejeitar integralmente sem taxa. Cálculos e transição financeira são atômicos.

Registrar preço de referência, preço efetivo, alíquotas, bruto e taxa. Slippage já está no preço; não debitá-lo novamente. Não limitar o preço efetivo ao high/low do candle nem usar esses extremos para validar liquidez: não estão disponíveis na abertura. Volume não limita preenchimentos; liquidez ilimitada é hipótese fictícia. Não há modelo separado de spread.

### 5.3. Último candle e interrupção por lacuna

No encerramento normal, ordem criada no último fechamento termina `UNEXECUTED/NO_FUTURE_OPEN`, sem taxa. Reportar sinal, decisão e ordem; não criar abertura ou venda fictícia. Posição aberta permanece aberta, sem marcação patrimonial ou liquidação forçada nesta sprint.

Se a próxima abertura for posterior ao fechamento anterior esperado, interromper **antes de liberar essa abertura**, alimentar indicadores ou preencher pendências. Registrar `DATA_GAP` com horário esperado, encontrado e último evento aceito. Preservar caixa, posição, taxas, histórico e a ordem `NEW` pendente; não chamar a finalização normal que a converteria em `NO_FUTURE_OPEN`.

Produzir status `INTERRUPTED`, diagnóstico, relatório parcial claramente identificado e artefatos do prefixo aceito, com código 1. O relatório mantém a pendência e explica que o replay não terminou. Metadados e hashes identificam o arquivo original inteiro, inclusive seu sufixo não processado. Uma lacuna é erro de dados, não perda financeira ou resultado normal de estratégia. Recuperação exige corrigir/versionar os dados e iniciar outra execução, sem retomar ou reconstruir operações retroativamente nesta sessão.

Erros estruturais anteriores ao replay não criam saída. Falhas técnicas não devem ser mascaradas como rejeições ou produzir artefatos com aparência de conclusão bem-sucedida. A interrupção por lacuna é o caso diagnosticado com saída parcial definida nesta seção.

## 6. Fixture obrigatória e conferência manual

Criar `data/fixtures/sprint07-candles.json` no envelope versão 1. A tabela especifica todos os candles; todos têm `source: FICTICIA`, `symbol: BTCUSDT`, `interval: 1m`, `volume: "1"` e `is_closed: true`. A data é **2026-01-01**, horários UTC com offset `+00:00`, e valores OHLC são strings JSON. Não gerar preços aleatórios nem buscar dados externos.

| k | Abertura | Fim | open | high | low | close |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 12:00 | 12:01 | 100000 | 100000 | 100000 | 100000 |
| 2 | 12:01 | 12:02 | 100000 | 100000 | 99000 | 99000 |
| 3 | 12:02 | 12:03 | 100000 | 100000 | 98000 | 98000 |
| 4 | 12:03 | 12:04 | 100000 | 102000 | 100000 | 102000 |
| 5 | 12:04 | 12:05 | 100000 | 104000 | 100000 | 104000 |
| 6 | 12:05 | 12:06 | 100000 | 100000 | 100000 | 100000 |
| 7 | 12:06 | 12:07 | 100000 | 100000 | 98000 | 98000 |
| 8 | 12:07 | 12:08 | 100000 | 100000 | 99000 | 99000 |

Usar a configuração da seção 3.2. As médias da tabela seguinte são explicativas: frações indicam valores exatos e não strings obrigatórias de apresentação.

| k | SMA curta 2 | SMA longa 3 | Avaliação |
| --- | --- | --- | --- |
| 1–2 | Conforme disponibilidade | Indisponível | Aquecimento |
| 3 | 98500 | 99000 | Aquecimento: falta comparação anterior |
| 4 | 100000 | 299000/3 | Cruzamento BUY |
| 5 | 103000 | 304000/3 | Sem cruzamento |
| 6 | 102000 | 102000 | Igualdade atual, sem sinal |
| 7 | 99000 | 302000/3 | Cruzamento SELL a partir da igualdade |
| 8 | 98500 | 99000 | Sem cruzamento |

O BUY surge no fechamento 12:04 e preenche na abertura 12:04 do candle 5; o SELL surge no fechamento 12:07 e preenche na abertura 12:07 do candle 8, sempre com `seq` posterior. As diferenças entre fechamento e próxima abertura são intencionais.

| Etapa | Preço efetivo USDT/BTC | Bruto USDT | Taxa USDT | Fluxo USDT | Caixa USDT | BTC |
| --- | --- | --- | --- | --- | --- | --- |
| Inicial | — | — | — | — | 1000 | 0 |
| BUY | 100100 | 100.1 | 0.1001 | -100.2001 | 899.7999 | 0.001 |
| SELL | 99900 | 99.9 | 0.0999 | +99.8001 | 999.6 | 0 |

Resultado líquido da única ida e volta: `99.8001 - 100.2001 = -0.4 USDT`; taxas totais `0.2 USDT`. Efeito adverso do slippage no bruto: `0.1 + 0.1 = 0.2 USDT`, já incorporado nos preços. Exigir 8 avaliações, 2 sinais, 2 decisões aprovadas, 2 ordens preenchidas e 2 execuções; nenhuma ordem no aquecimento, igualdade ou permanência.

Variantes obrigatórias, derivadas sem alterar a fixture principal:

- Slippage zero: preços 100000 em ambas as pontas, taxas totais 0.2 e caixa final 999.8 USDT.
- Somente candles 1 a 4: sinal BUY final, ordem não executada, caixa 1000, BTC zero, taxa zero e código 2.
- Somente candles 1 a 5: compra preenchida, posição 0.001 BTC mantida, caixa 899.7999 e nenhum lucro realizado inventado.
- Remover candle 5: interromper antes da abertura 12:05 do candle 6; último fechamento aceito 12:04, ordem BUY pendente, caixa 1000, BTC zero e taxa zero.
- Remover candle 6: compra já realizada no candle 5 permanece; interromper antes do candle 7, com caixa 899.7999 e BTC 0.001.

Sem ida e volta aplicável, usar `null` e os motivos da Sprint 06. O cálculo mínimo só é aplicável a exatamente uma compra seguida de uma venda integral, posição final zero e execução concluída; em replay interrompido usar `null/REPLAY_INTERRUPTED`. Não ampliar para métricas agregadas de múltiplos trades antes da Sprint 08.

## 7. Entregáveis, CLI e artefatos

Evoluir apenas os módulos necessários; sugerem-se `replayquant/strategies.py` e testes `tests/test_sprint07.py`, além das alterações pertinentes em dados, modelos, motor, execução, relatórios e CLI. Não criar arquitetura de plugins ou módulos vazios para etapas futuras.

Entregar fixture/configuração da seção 6, README atualizado, `docs/sprint07-validacao.md`, `docs/sprint07-glossario.md` e `docs/estrategias/sma.md`. O glossário explica SMA, janela, aquecimento, igualdade, cruzamento, causalidade, intenção, slippage e sequência lógica. O documento da estratégia descreve parâmetros, equações, sinais, decisões, limites e ausência de evidência de rentabilidade.

Adicionar `--estrategia sma` somente a `demonstrar`; sem a opção, a demonstração manual mantém seu comportamento. `executar` seleciona o modo pelo schema da configuração, sem argumento redundante. Comandos previstos após implementar, na raiz:

```bash
source .venv/bin/activate
python --version
python -m replayquant --help
python -m replayquant demonstrar --formato json
python -m replayquant demonstrar --estrategia sma --formato texto
python -m replayquant demonstrar --estrategia sma --formato json
python -m replayquant demonstrar --estrategia sma --formato html > /tmp/replayquant-sprint07.html
python -m unittest discover -s tests -v
```

`demonstrar --estrategia sma` verifica os resultados obrigatórios e retorna 0 somente se conferirem. Não grava artefatos. Todos os formatos explicam avaliações, sinais, decisões, ordens, execuções e estado final; HTML permanece independente, responsivo, imprimível e com escape de texto dinâmico. JSON stdout contém somente relatório; diagnósticos vão para stderr. Valores financeiros são strings, ausência é `null` com motivo e horários são UTC canônicos.

`executar` mantém `--dados`, `--config` e `--saida` obrigatórios e `--formato texto|json|html`. Criar saída nova, sem sobrescrever/apagar. Manter `manifest.json`, `events.jsonl` e `report.json`, ampliando no schema 2 a rastreabilidade de estratégia, comparações exatas (numeradores/denominadores ou inteiros escalados), decisões, pendências e status `COMPLETED`/`INTERRUPTED`. O manifesto registra parâmetros, aquecimento, convenção temporal, política de lacunas, taxa e slippage, além dos hashes e metadados da Sprint 06. Reutilizar a definição canônica de hash de código e `run_id`; não incluir relógio real ou caminho de saída na identidade.

| Código | Contrato SMA |
| --- | --- |
| 0 | Replay concluído sem bloqueios por política, ordens rejeitadas ou não executadas; inclui nenhum cruzamento/aquecimento apenas |
| 1 | Entrada inválida, falha aritmética/técnica ou interrupção por lacuna; esta última preserva artefatos parciais identificados |
| 2 | Replay concluído com decisão bloqueada por política, ordem rejeitada ou não executada |

`WARMUP` e `NO_CROSS` não são bloqueios por política. Erro sintático de `argparse` conserva código 2 sem iniciar replay. Preservar os códigos do modo manual.

Para reprodução, executar na mesma sessão Bash, com diretório temporário novo:

```bash
validacao_sma_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint07-candles.json --config experiments/sprint07-sma.json --saida "$validacao_sma_dir/execucao-a" --formato json
python -m replayquant executar --dados data/fixtures/sprint07-candles.json --config experiments/sprint07-sma.json --saida "$validacao_sma_dir/execucao-b" --formato json
cmp "$validacao_sma_dir/execucao-a/manifest.json" "$validacao_sma_dir/execucao-b/manifest.json"
cmp "$validacao_sma_dir/execucao-a/events.jsonl" "$validacao_sma_dir/execucao-b/events.jsonl"
cmp "$validacao_sma_dir/execucao-a/report.json" "$validacao_sma_dir/execucao-b/report.json"
git diff --check
```

Espera-se 0 individualmente nos comandos principais; registrar cada código observado. Conferir os códigos negativos pela suíte, sem inferir sucesso de comandos anteriores pelo último resultado. Salvar HTML fora de `--saida`, pois redirecionamento pelo shell precede a criação do diretório.

## 8. Verificação e critérios de aceite

Implementar testes de comportamento com `unittest`, cobrindo:

1. Fixture completa e variantes da seção 6 com `Decimal` exato, contagens de eventos e referências entre entidades.
2. Janelas `1/2`, `2/3`, aquecimento de `l` e primeira comparação em `l+1`; recusar zero, negativa, iguais, invertidas, float, string e booleano na API/JSON.
3. Entrada/saída, igualdade anterior em ambos os sentidos, igualdade atual, sequência constante e permanência no mesmo lado; nenhuma repetição sem novo cruzamento.
4. Diferença exata abaixo da precisão exibida: construir séries válidas de magnitudes mistas e confirmar que médias exibidas iguais não apagam cruzamento. Por exemplo, janelas 1/2 com fechamentos `1`, `0.000000000001`, `0.000000000002`: o terceiro fecha com cruzamento BUY, mesmo que uma apresentação com oito casas exiba ambas as médias como zero.
5. Mesmo timestamp em fases distintas, ordem estrita por `seq`, preenchimento somente na abertura seguinte e nenhuma informação high/low/close/volume final no evento de abertura ou na interface da estratégia.
6. Causalidade por prefixo: alterar sufixo válido preserva avaliações, sinais, decisões e efeitos financeiros anteriores; ignorar apenas IDs/hashes globais derivados do arquivo. Um replay truncado pode ter finalização diferente, que não integra o prefixo comparado. Alterar high/low/close/volume do candle de preenchimento preserva esse preenchimento, mantendo open e validade; seu fechamento pode afetar decisões posteriores.
7. Rejeição por saldo incluindo taxa/slippage; abertura que invalida estimativa aprovada; ausência de mutação e de reenvio sem novo cruzamento. Venda sem ativo, compra com posição e intenção concorrente são bloqueadas sem mudar posição/pendência anterior; cobrir a API incremental onde o arquivo contíguo não produz concorrência naturalmente.
8. Slippage zero/positivo em ambos os lados, limites inválidos e preço fora dos extremos sem consulta ao OHLC futuro; taxa sobre preço efetivo e custo não duplicado.
9. Lacunas antes/depois de preenchimento, preservação exata do prefixo e pendência, ausência de OPEN/CLOSE posterior e distinção de `NO_FUTURE_OPEN`. Sessão interrompida recusa continuação; correção demanda nova execução.
10. Duplicatas idênticas de candle/avaliação/intenção/ordem/execução inócuas; conflitos falham sem mutação aceita. Eventos fora de ordem, candles abertos, JSON inválido e limites de domínio são recusados nas camadas apropriadas.
11. Contextos decimais externos adversos não alteram decisões/saldos nem são modificados; falha aritmética não deixa débito, taxa ou preenchimento parcial.
12. CLI, códigos 0/1/2, formatos, rejeição de sobrescrita, schemas, relatórios parciais e comparação byte a byte. Executar regressões da Sprint 06, inclusive demonstração manual e HTML.

Aceite exige suíte relevante aprovada, causalidade demonstrada, reprodução, invariantes financeiros e documentação em português. O registro de validação distingue esperado, observado, comandos não executados e pendências; informa versão Python real e limitações. Não declarar a sprint concluída apenas por criar esta especificação.

## 9. Prompt autossuficiente de execução

Copie o bloco inteiro para um agente com acesso ao repositório. As referências são arquivos versionados do projeto; não é necessário consultar a conversa original.

````text
Implemente a Sprint 07 — Estratégia SMA e causalidade do ReplayQuant.

CONTEXTO E ENTRADA
Trabalhe em /home/cams7/Dev/Cripto_Tests/replayquant, evoluindo o projeto existente.
Inspecione git status, instruções AGENTS.md aplicáveis, código e testes. Leia
integralmente docs/sprint07.md (seções 1 a 8), docs/planejamento.md e os contratos
da Sprint 06 em docs/sprint06.md e docs/sprint06-validacao.md. Confirme o estado
anterior executando a suíte existente no ambiente .venv. Preserve trabalho alheio.
Se faltar pré-requisito essencial ou houver contradição impeditiva, registre a
lacuna antes de executar trabalho dependente; não recrie o projeto silenciosamente.

OBJETIVO E LIMITES
Implemente, teste e documente sinais SMA causais com execução na próxima abertura,
latência zero entre eventos ordenados, slippage fixo adverso e rastreabilidade.
Não entregue somente proposta. Use biblioteca padrão/unittest, Python >= 3.11,
referência 3.12.14, sem pacotes novos ou rede. Preserve modo manual, formatos e
contratos versão 1. Não importe laboratórios vizinhos. Não antecipe EMA/RSI,
risco, reservas, stops, métricas/benchmarks, dados reais, múltiplos pares, parciais,
latência positiva, web, AWS, negociação real ou recuperação após reinício.

ENTRADAS E ARITMÉTICA
Implemente exatamente a configuração schema_version 2 SMA_CROSS da seção 3.2
de docs/sprint07.md, sem orders. Janelas inteiras estritas 1 <= curta < longa,
frações fee_rate/slippage_rate em [0,1), quantidade fixa, capital positivo,
instrumento FICTICIA/BTCUSDT/1m e BTC inicial zero. Preserve candles schema 1,
JSON estrito, strings decimais, limites e validações na API Python. Contabilidade
em Decimal com contexto local precisão 40 e ROUND_HALF_EVEN, erro antes de mutação
se inexata, sem alterar o contexto do chamador. Decida cruzamentos por razões ou
inteiros escalados exatos, nunca por médias arredondadas ou float.

ESTRATÉGIA E TEMPO
Uma avaliação por candle fechado contíguo; comparar médias anterior/atual exige
longa+1 fechamentos. BUY: curta anterior <= longa anterior e curta atual > longa
atual. SELL: curta anterior >= longa anterior e curta atual < longa atual.
Igualdade atual e permanência não sinalizam. Registre WARMUP/NO_CROSS quando
cabíveis. Separe avaliação, sinal, decisão, intenção, ordem e execução com IDs
determinísticos e referências. A estratégia recebe apenas fechamentos liberados.
Processe CLOSE, EVALUATION, SIGNAL/DECISION/submissão e só depois OPEN/fill do
candle seguinte. Timestamp pode coincidir; seq precisa crescer. Não consulte
open futuro na decisão nem high/low/close/volume final na abertura.

Decisão verifica pendência, posição e caixa estimado, nesta ordem. Uma pendência,
uma posição de quantidade fixa, sem compra acumulada ou venda descoberta. Sinal
bloqueado é registrado sem ordem ou mudança de saldo. Estime compra pelo último
close com slippage e taxa; revalide no open efetivo. Falha por saldo rejeita sem
taxa ou mutação, libera pendência e não reenvia sem novo cruzamento. Não implemente
cancelamento operacional; qualquer cancelamento integrado deve conservar posição
e exigir novo cruzamento. Duplicata idêntica é inócua; ID conflitante falha sem
mutação do histórico aceito, conforme seções 4 e 5.

EXECUÇÃO E LACUNAS
Preço BUY = open*(1+slippage); SELL = open*(1-slippage). Bruto = preço*quantidade,
taxa = bruto*fee_rate em USDT. Compra debita bruto+taxa e soma BTC; venda credita
bruto-taxa e subtrai BTC. Preenchimento total atômico, liquidez ilimitada fictícia,
sem limitar por volume/extremos nem descontar slippage outra vez. Registre preço
de referência e efetivo. Última ordem sem abertura futura termina
UNEXECUTED/NO_FUTURE_OPEN; posição aberta não é liquidada artificialmente.

No modo SMA, valide estrutura/domínio/conflitos/ordem antes do replay, mas confira
continuidade incrementalmente antes de cada OPEN. Lacuna interrompe antes do
candle posterior, preservando caixa, posição, histórico, taxas e pendência NEW.
Não finalize como NO_FUTURE_OPEN. Gere DATA_GAP, status INTERRUPTED, relatório
parcial e artefatos do prefixo com código 1. Hashes cobrem o arquivo original.
Não aceite continuação: correção exige dados versionados e nova execução. Mantenha
a rejeição prévia de lacunas no modo manual. Siga os detalhes da seção 5.3.

EXEMPLO OBRIGATÓRIO
Crie data/fixtures/sprint07-candles.json com os oito candles exatos da tabela da
seção 6 e experiments/sprint07-sma.json com o JSON da seção 3.2. Todos em
2026-01-01 UTC, opens 100000, closes 100000/99000/98000/102000/104000/100000/
98000/99000, OHLC e horários exatamente conforme a tabela. Janelas 2/3,
capital 1000, quantidade 0.001, taxa/slippage 0.001. BUY no fechamento 12:04,
fill no OPEN 12:04: preço 100100, bruto 100.1, taxa 0.1001, caixa 899.7999,
BTC 0.001. Igualdade em k=6 não sinaliza. SELL no fechamento 12:07, fill no OPEN
12:07: preço 99900, bruto 99.9, taxa 0.0999, caixa 999.6, BTC zero. Taxas 0.2,
resultado líquido -0.4 USDT. Exigir 8 avaliações, 2 sinais, 2 decisões aprovadas,
2 ordens e 2 fills. Implemente também as variantes de slippage zero, truncamento,
posição aberta e lacunas da seção 6. São testes de correção, não de rentabilidade.

CLI, ARTEFATOS E ENTREGAS
Preserve demonstrar manual; adicione demonstrar --estrategia sma para o exemplo
novo, com conferência dos valores obrigatórios. executar escolhe o modo pelo
schema e mantém --dados/--config/--saida e --formato texto|json|html. Siga seção 7
para códigos 0/1/2, relatórios, não sobrescrita, stdout/stderr e artefatos versão 2
SMA, mantendo versão 1 manual. Preserve definição canônica de hashes/run_id da
Sprint 06; parâmetros/modelos são registrados, sem hora real ou caminho de saída
na identidade. Duas saídas iguais devem coincidir byte a byte nos três artefatos.
Entregue código, fixtures, configuração, testes, README atualizado,
docs/sprint07-validacao.md, docs/sprint07-glossario.md e docs/estrategias/sma.md.
Não crie módulos vazios ou arquitetura para sprints futuras.

VALIDAÇÃO E REGISTRO FINAL
Implemente todos os casos da seção 8, incluindo precisão de cruzamento, prefixo
causal, igualdade, aquecimento, pendências, rejeição sem reenvio, lacunas com estado
preservado, deduplicação, contexto decimal e regressões manuais/HTML. Corrija falhas
sem mudar valores esperados para acomodar defeitos. Na raiz, ative .venv, confira
Python real e execute todos os comandos da seção 7: ajuda, demonstração manual,
três formatos SMA, unittest discover e duas execuções em diretórios novos com cmp
dos três arquivos e git diff --check. Registre o código de cada comando e resultados
observados; casos negativos 1/2 são conferidos pela suíte. Não alegue verificações
não executadas. Se o ambiente de referência faltar, registre a limitação sem
instalar ou alterar o sistema silenciosamente.
Não faça commit, publicação ou alterações externas. Na resposta final informe
arquivos alterados, verificações realmente feitas, resultados, limitações e
pendências. Não declare concluída a sprint se faltar requisito obrigatório.
````
