# Sprint 07 — Registro de validação

Validação em **07/11/2026**, na raiz do ReplayQuant, com **Python 3.12.14** e
ambiente `.venv`. Biblioteca padrão e `unittest`; nenhum pacote foi instalado.

## 1. Estado da entrega

Implementados configuração SMA versão 2, indicador incremental com razões exatas,
aquecimento, cruzamentos, decisões, intenções, slippage adverso, replay causal,
interrupção por lacuna e relatórios texto/JSON/HTML. O modo manual versão 1 foi
preservado. Especificação: [sprint07.md](sprint07.md); uso: [README](../README.md);
regras: [estrategias/sma.md](estrategias/sma.md); conceitos: [glossário](sprint07-glossario.md).

A suíte anterior passou antes das alterações: **31 testes**. A verificação final
passou com **60 testes**, incluindo esses 31 e 29 testes novos. Não há pendências
conhecidas nos requisitos obrigatórios da Sprint 07.

## 2. Comandos finais efetivamente executados

Foi executado `source .venv/bin/activate` antes dos comandos abaixo. Um executor
Python usou `subprocess.run` para registrar individualmente argumentos, stdout,
stderr e código de saída. O HTML foi salvo em `/tmp/replayquant-sprint07.html`.
Não foi necessário recriar o ambiente virtual existente.

| Comando | Código observado | Resultado observado |
| --- | --- | --- |
| `python --version` | 0 | Python 3.12.14 |
| `python -m replayquant --help` | 0 | Ajuda disponível |
| `python -m replayquant demonstrar --formato json` | 0 | Exemplo manual conferido; resultado 0.799 USDT |
| `python -m replayquant demonstrar --estrategia sma --formato texto` | 0 | Exemplo SMA conferido; formato solicitado produzido |
| `python -m replayquant demonstrar --estrategia sma --formato json` | 0 | Exemplo SMA conferido; formato solicitado produzido |
| `python -m replayquant demonstrar --estrategia sma --formato html` | 0 | Exemplo SMA conferido; formato solicitado produzido |
| `python -m unittest discover -s tests -v` | 0 | 60 testes aprovados (OK) |
| `python -m replayquant executar --dados data/fixtures/sprint07-candles.json --config experiments/sprint07-sma.json --saida $validacao_sma_dir/execucao-a --formato json` | 0 | Três artefatos schema 2 gerados; JSON stdout válido |
| `python -m replayquant executar --dados data/fixtures/sprint07-candles.json --config experiments/sprint07-sma.json --saida $validacao_sma_dir/execucao-b --formato json` | 0 | Três artefatos schema 2 gerados; JSON stdout válido |
| `cmp $validacao_sma_dir/execucao-a/manifest.json $validacao_sma_dir/execucao-b/manifest.json` | 0 | Arquivos idênticos byte a byte |
| `cmp $validacao_sma_dir/execucao-a/events.jsonl $validacao_sma_dir/execucao-b/events.jsonl` | 0 | Arquivos idênticos byte a byte |
| `cmp $validacao_sma_dir/execucao-a/report.json $validacao_sma_dir/execucao-b/report.json` | 0 | Arquivos idênticos byte a byte |
| `git diff --check` | 0 | Sem erros de whitespace nos arquivos rastreados alterados |

O diretório de validação foi `/tmp/replayquant-sprint07-4e1svk4i`; a variável
`$validacao_sma_dir` na tabela abrevia esse caminho. `commands.json` nesse diretório
preserva o registro completo dos comandos finais. Arquivos em `/tmp` são
auxiliares e podem ser removidos pelo sistema; as conclusões estão registradas aqui.
Os comandos para reproduzir a comparação constam na seção 7 da especificação.

## 3. Exemplo obrigatório: esperado e observado

| Grandeza | Esperado | Observado |
| --- | --- | --- |
| Avaliações | 8 | 8 |
| Sinais | 2 | 2 |
| Decisões aprovadas | 2 | 2 |
| Ordens preenchidas / execuções | 2 / 2 | 2 / 2 |
| Preço BUY (USDT/BTC) | 100100 | 100100.000 |
| Bruto BUY (USDT) | 100.1 | 100.100000 |
| Taxa BUY (USDT) | 0.1001 | 0.100100000 |
| Desembolso BUY (USDT) | 100.2001 | 100.200100000 |
| Preço SELL (USDT/BTC) | 99900 | 99900.000 |
| Bruto SELL (USDT) | 99.9 | 99.900000 |
| Taxa SELL (USDT) | 0.0999 | 0.099900000 |
| Recebimento SELL (USDT) | 99.8001 | 99.800100000 |
| Taxas totais (USDT) | 0.2 | 0.200000000 |
| Caixa final (USDT) | 999.6 | 999.600000000 |
| BTC final | 0 | 0.000 |
| Resultado líquido (USDT) | -0.4 | -0.400000000 |

Zeros finais preservam a representação, sem alterar a igualdade numérica. Os
asserts financeiros usam `Decimal` exato. O BUY foi sinalizado no fechamento
12:04 e preenchido na abertura seguinte de mesmo timestamp, a partir do open
100000. O SELL seguiu a mesma convenção em 12:07. As sequências de preenchimento
são estritamente posteriores às submissões; igualdade das médias em k=6 não gerou
sinal. Slippage já está no preço efetivo e não foi deduzido novamente.

Identidade da execução final:

```text
run_id = e45769672c1012d75ee5ab2d0e27823723d4b52d0a3079ad45de3de3ecbefda4
```

O ID depende dos bytes dos dados/configuração/código e da versão Python; não é
constante da aplicação. Documentação e diretório de saída não entram nesse hash.
Os três artefatos coincidiram byte a byte em duas saídas independentes.

## 4. Comportamentos efetivamente conferidos

| Grupo | Resultado observado pela suíte |
| --- | --- |
| Aquecimento e igualdade | Janelas 1/2 e 2/3, primeira comparação em longa+1, preços constantes, igualdade anterior/atual e permanência sem repetição |
| Precisão | Série 1, 0.000000000001, 0.000000000002 cruzou BUY em 1/2; razão longa final 3/2000000000000 sem perda por arredondamento |
| Causalidade | Alterar sufixo preservou prefixo; mudar OHLCV final com open preservado não alterou preenchimento na abertura; abertura não contém OHLCV futuro |
| Sequência | CLOSE, avaliação/sinal/decisão/intenção/ordem e OPEN/fill respeitaram seq mesmo com timestamp igual |
| Custos | Compra/venda com slippage adverso, taxa no preço efetivo, preços fora dos extremos permitidos e slippage zero resultando em caixa 999.8 |
| Revalidação | Alta na abertura rejeitou compra aprovada pela estimativa, sem débito, taxa ou posição parcial; nenhuma tentativa por permanência |
| Novo cruzamento | Após rejeição houve nova ordem somente no novo cruzamento; sinal SELL sem ativo foi bloqueado |
| Política e pendência | ORDER_PENDING preservou intenção anterior; POSITION_OPEN, INSUFFICIENT_ASSET e INSUFFICIENT_CASH não criaram ordens ou mudaram saldos |
| Término | Prefixo de 4 candles deixou UNEXECUTED/NO_FUTURE_OPEN com código 2; prefixo de 5 manteve BTC 0.001 e caixa 899.7999, sem lucro realizado inventado |
| Lacuna com pendência | Sem candle 5, interrompeu antes do candle 6 com caixa 1000, BTC/taxa zero, ordem NEW preservada e nenhum evento de mercado posterior |
| Lacuna com posição | Sem candle 6, manteve caixa 899.7999 e BTC 0.001; status INTERRUPTED e continuação recusada |
| Identidade e duplicatas | Candles, aberturas, avaliações, sinais/intenções, ordens e fills idênticos não repetiram efeitos; conflitos não alteraram histórico aceito; diagnóstico de duplicata futura não deslocou avaliações anteriores |
| Entrada e API | Janelas inválidas, bool/float, versões/campos/rates inválidos, candles abertos, OHLC inconsistente, datas sem fuso, conflitos e ordem incorreta recusados; UTC equivalente normalizado |
| Contexto decimal | Precisão externa 2, ROUND_UP, traps/flags adversos não alteraram os resultados ou o contexto do chamador |
| Atomicidade | Falha inexata real ao subtrair desembolso com muitas casas preservou caixa/posição/taxa/ordem; falhas injetadas no indicador e na carteira preservaram o estado aceito |
| CLI | Códigos 0/1/2, três formatos, stdout/stderr separados, artefatos schema 2 e recusa de sobrescrita; estrutura inválida não criou saída |
| Saída parcial | Lacuna pela CLI retornou 1 com relatório parcial, pendência NEW e hashes do arquivo completo; não foi convertida em término normal |
| Compatibilidade | Todos os 31 testes anteriores passaram, incluindo formato HTML, hashes independentes, recusa de sobrescrita, falhas de escrita e demonstração manual |

Casos negativos foram executados pela suíte com entradas temporárias. Código 1
foi observado em lacuna, entrada inválida e saída existente; código 2 em decisão
bloqueada e ordem sem abertura futura, além da sintaxe inválida de `argparse`.
São resultados esperados dos cenários, não falhas ocultadas da suíte.

## 5. Relatório HTML

O documento independente foi gerado pelo comando registrado na tabela. Foram
inspecionadas capturas do Chrome headless em **1440×1100** e **390×1000**, salvas em
`/tmp/replayquant-sprint07-desktop.png` e `/tmp/replayquant-sprint07-mobile.png`.
Os primeiros viewports mostram identidade, status e resumo financeiro legíveis,
com reorganização dos cartões/navegação em tela estreita. As tabelas usam rolagem
horizontal em tela estreita; o CSS de impressão foi preservado. A suíte conferiu
seções SMA, decimais, escape de conteúdo dinâmico, documento independente e
identificação de relatório parcial.

Comandos de captura que concluíram com código 0:

```bash
google-chrome --headless --no-sandbox --disable-gpu --disable-background-networking --no-first-run --user-data-dir=/tmp/replayquant-sprint07-chrome-desktop --screenshot=/tmp/replayquant-sprint07-desktop.png --window-size=1440,1100 file:///tmp/replayquant-sprint07.html
google-chrome --headless --no-sandbox --disable-gpu --disable-background-networking --no-first-run --user-data-dir=/tmp/replayquant-sprint07-chrome-mobile --screenshot=/tmp/replayquant-sprint07-mobile.png --window-size=390,1000 file:///tmp/replayquant-sprint07.html
```

As tentativas iniciais dentro da sandbox falharam: código 1 sem diretório de
perfil explícito e 133 por restrição de socket. A captura funcionou com perfil em
`/tmp` e execução autorizada fora da sandbox. Isso não alterou o código ou os
resultados financeiros. Não foi feita inspeção visual de todas as páginas de
impressão ou exportação PDF.

## 6. Decisões e limitações

- Configuração manual segue versão 1; SMA usa versão 2 sem roteiro. `replay`
  despacha pelo tipo `Config`/`SMAConfig`; `load_inputs` pelo schema JSON.
- `SMACross` usa `Fraction` e fila limitada à janela longa. A sessão mantém log
  e registros de idempotência em memória; o replay não tem limite artificial de
  candles, mas não é um motor de processamento em lotes de memória constante.
- `SMASession` reutiliza contabilidade e validações de execução de `Session`.
  Preços efetivos derivados podem exceder os limites de representação da entrada,
  desde que finitos, positivos e calculados exatamente no contexto financeiro.
- Estrutura/domínio/ordem do arquivo são pré-validados. Continuidade SMA é
  incremental; manual preserva recusa prévia de lacunas. Interrupção por lacuna
  não executa a finalização normal; correção exige nova execução.
- `handle_signal` é fronteira incremental de integração de sinais identificados.
  O replay usa apenas sinais calculados pelo indicador. Não há comando para
  sinais externos, cancelamento operacional ou mistura com roteiro manual.

Validado apenas Python 3.12.14 neste ambiente; não foi executada matriz de versões
ou sistemas operacionais. Não foram avaliados grandes volumes, dados reais,
liquidez, latência positiva, recuperação após reinício ou desempenho de investimento.
Não há risco, reservas, ledger completo, curva patrimonial ou benchmarks. A
fixture é deliberadamente pequena e pode produzir prejuízo sem reprovar o aceite.

Nenhum commit, publicação, conexão a exchange ou envio de ordem foi realizado.
