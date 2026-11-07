# Sprint 08 — Registro de validação

Validação executada em **07/11/2026**, na raiz do ReplayQuant, com **Python
3.12.14**, ambiente `.venv`, biblioteca padrão e `unittest`. Não foram instalados
pacotes, atualizadas bibliotecas, obtidos dados reais ou enviadas ordens.

## 1. Estado da entrega

Implementados ledger imutável integrado aos fills, projeção causal de patrimônio,
trades e bases de custo, métricas com razões exatas, referências HOLD_USDT e
BUY_HOLD_BTC, flag `--analise`, schemas enriquecidos 3, nove arquivos e relatórios
texto/JSON/Markdown/HTML. Os modos anteriores continuam disponíveis sem a flag.

A suíte anterior passou antes das alterações: **71 testes**. A suíte final
passou com **100 testes**, sendo os 71 anteriores e 29 novos. Não há pendências
conhecidas nos requisitos obrigatórios desta sprint. A especificação está em
[sprint08.md](sprint08.md); uso no [README](../README.md); conceitos no
[glossário](sprint08-glossario.md).

## 2. Comandos finais realmente executados

`source .venv/bin/activate` foi executado antes do roteiro final. Um executor
local Python usou `subprocess.run` para registrar cada argumento, stdout, stderr
e código individual, sem inferir sucesso de comandos anteriores pelo último.
A tabela registra a verificação final, após corrigir falhas intermediárias de
validação/serialização encontradas durante o desenvolvimento.

| Comando | Código observado | Resultado observado |
| --- | --- | --- |
| `python --version` | 0 | Python 3.12.14 |
| `python -m replayquant --help` | 0 | Ajuda inclui --analise e markdown |
| `python -m replayquant demonstrar --formato json` | 0 | Demonstração anterior conferida; schema preservado |
| `python -m replayquant demonstrar --estrategia sma --formato json` | 0 | Demonstração anterior conferida; schema preservado |
| `python -m replayquant demonstrar --analise --formato texto` | 0 | Demonstração enriquecida conferida; formato solicitado gerado |
| `python -m replayquant demonstrar --analise --formato json` | 0 | Demonstração enriquecida conferida; formato solicitado gerado |
| `python -m replayquant demonstrar --analise --formato markdown` | 0 | Demonstração enriquecida conferida; formato solicitado gerado |
| `python -m replayquant demonstrar --estrategia sma --analise --formato html` | 0 | Demonstração enriquecida conferida; formato solicitado gerado |
| `python -m replayquant demonstrar --analise --formato html` | 0 | Demonstração enriquecida conferida; formato solicitado gerado |
| `python -m unittest discover -s tests -v` | 0 | 100 testes aprovados (OK) |
| `python -m replayquant executar --dados data/fixtures/sprint08-candles.json --config experiments/sprint08-manual.json --analise --saida $validacao_sprint08_dir/execucao-a --formato json` | 0 | Nove artefatos válidos; relatório no formato solicitado |
| `python -m replayquant executar --dados data/fixtures/sprint08-candles.json --config experiments/sprint08-manual.json --analise --saida $validacao_sprint08_dir/execucao-b --formato json` | 0 | Nove artefatos válidos; relatório no formato solicitado |
| `cmp $validacao_sprint08_dir/execucao-a/manifest.json $validacao_sprint08_dir/execucao-b/manifest.json` | 0 | Arquivo idêntico byte a byte |
| `cmp $validacao_sprint08_dir/execucao-a/events.jsonl $validacao_sprint08_dir/execucao-b/events.jsonl` | 0 | Arquivo idêntico byte a byte |
| `cmp $validacao_sprint08_dir/execucao-a/report.json $validacao_sprint08_dir/execucao-b/report.json` | 0 | Arquivo idêntico byte a byte |
| `cmp $validacao_sprint08_dir/execucao-a/ledger.jsonl $validacao_sprint08_dir/execucao-b/ledger.jsonl` | 0 | Arquivo idêntico byte a byte |
| `cmp $validacao_sprint08_dir/execucao-a/equity.csv $validacao_sprint08_dir/execucao-b/equity.csv` | 0 | Arquivo idêntico byte a byte |
| `cmp $validacao_sprint08_dir/execucao-a/trades.csv $validacao_sprint08_dir/execucao-b/trades.csv` | 0 | Arquivo idêntico byte a byte |
| `cmp $validacao_sprint08_dir/execucao-a/metrics.csv $validacao_sprint08_dir/execucao-b/metrics.csv` | 0 | Arquivo idêntico byte a byte |
| `cmp $validacao_sprint08_dir/execucao-a/benchmarks.csv $validacao_sprint08_dir/execucao-b/benchmarks.csv` | 0 | Arquivo idêntico byte a byte |
| `cmp $validacao_sprint08_dir/execucao-a/report.md $validacao_sprint08_dir/execucao-b/report.md` | 0 | Arquivo idêntico byte a byte |
| `python -m replayquant executar --dados data/fixtures/sprint07-candles-expandido.json --config experiments/sprint07-sma-expandido.json --analise --saida $validacao_sprint08_dir/sma-ampliado --formato html` | 0 | Nove artefatos válidos; relatório no formato solicitado |
| `git diff --check` | 0 | Sem erro de whitespace nos arquivos rastreados alterados |

`$validacao_sprint08_dir` abrevia `/tmp/replayquant-sprint08-_8t_j_kv`.
O arquivo `commands.json` nesse diretório preserva as saídas e códigos completos.
Os HTMLs foram salvos em `/tmp/replayquant-sprint08.html`,
`/tmp/replayquant-sprint08-manual.html` e
`/tmp/replayquant-sprint08-ampliado.html`. A saída do cenário ampliado também
está em `$validacao_sprint08_dir/sma-ampliado.html`. Arquivos em `/tmp` são
auxiliares; as conclusões observadas ficam documentadas aqui.

## 3. Exemplo manual: esperado e observado

| Grandeza | Esperado | Observado |
| --- | --- | --- |
| Entradas do ledger da estratégia | 3 | 3 |
| Pontos patrimoniais da estratégia | 9 | 9 |
| Caixa final USDT | 1000.799 | 1000.799000 |
| BTC final | 0 | 0.000 |
| Taxas pagas USDT | 0.201 | 0.201000 |
| Realizado USDT | 0.799 | 0.799000 |
| Não realizado final USDT | 0 | 0 |
| Patrimônio final USDT | 1000.799 | 1000.799000 |
| Retorno da carteira % | 0.0799 | 0.079900000000 |
| Retorno do trade % | 0.798201798202 | 0.798201798202 |
| Máximo drawdown % | 0.010090918174 | 0.010090918174 |
| Maior queda absoluta USDT | 0.101 | 0.101 |
| Maior duração observada de drawdown s | 60 | 60 |
| Tempo em posição s | 60 | 60 |
| Horizonte s | 180 | 180 |
| Exposição % | 33.333333333333 | 33.333333333333 |
| Expectativa USDT/TRADE | 0.799 | 0.799000000000 |
| Reconciliação | PASSED | PASSED |

As comparações usam `Decimal` e razões exatas; zeros finais não alteram igualdade
numérica. A curva observada foi:

```text
1000 → 1000 → 1000 → 1000 → 999.9 → 1000.9 → 1000.9 → 1000.799 → 1000.799
```

A taxa da compra reduz o patrimônio antes da valorização. O pico de 1000.9 cai
0.101 pela taxa da venda; a razão percentual exata é **101/10009**. O primeiro
episódio recupera após 60 s; o último permanece sem recuperação por 60 s
observados. O retorno do trade usa desembolso 100.1 e razão **799/1001** em %;
o da carteira usa capital 1000 e razão **799/10000** em %.

HOLD_USDT terminou com 1000 USDT, sem taxa ou exposição BTC. BUY_HOLD_BTC teve:

| Grandeza | Esperado | Observado |
| --- | --- | --- |
| Quantidade BTC | 0.009990009990 | 0.009990009990 |
| Caixa residual USDT | 0.000000001 | 0.000000001000000 |
| Taxa de entrada USDT | 0.999000999 | 0.999000999000000 |
| Patrimônio bruto USDT | 1008.991008991 | 1008.991008991000000 |
| Liquidação hipotética USDT | 1007.98201798201 | 1007.982017982010000 |
| Exposição temporal % | 100 | 100.000000000000 |

A referência mantém BTC aberto; não há taxa de saída paga ou liquidação forçada.
As três carteiras têm o mesmo capital inicial e horizonte e não compartilham
saldo. A exposição de quase todo o capital do benchmark é distinta da quantidade
fixa da estratégia.

Identidade do exemplo manual enriquecido:

```text
run_id = 800c703ed8c70e2cf900381bc71fae49a1d84756e23a7f13407d7ce4a60e3b12
```

O modo de análise inclui `analysis_policy: SPRINT08_V1` na identidade canônica.
A suíte recalculou a identidade independentemente. A ausência da flag conserva
a definição anterior; código novo altera naturalmente seu hash. Caminhos e
relógio real não participam da identidade.

## 4. Variantes e comportamentos observados pela suíte

| Grupo | Evidência observada |
| --- | --- |
| Reconstrução | Deltas de caixa/BTC e taxas reproduzem saldos após cada entrada; base de custo e trades são reconciliados; todos os pontos respeitam E = C0 + R + U |
| Roteiro vazio | Patrimônio 1000, custos/exposição/drawdown zero, realizado zero e acerto/expectativa null com NO_CLOSED_TRADES; benchmarks continuam independentes |
| Posição aberta | Com dois candles e uma compra: caixa 899.9, BTC 0.001, base 100.1, realizado zero, não realizado 0.9, bruto 1000.9 e liquidação hipotética 1000.799; taxa paga 0.1 separada da hipotética 0.101 |
| SMA canônico | Realizado -0.4, taxas 0.2, impacto de slippage 0.2; patrimônio no primeiro fill 999.7999 e não realizado -0.2001, usando open de referência |
| SMA ampliado | Três trades com +0.73754871919, +0.77489849630 e -0.61089654715 USDT; realizado 0.90155066834, BTC zero e taxas 0.60339361166 |
| Exposição ampliada | 6120 s em posição sobre 14400 s, 42.5%; expectativa 0.300516889447 USDT/TRADE e acerto 66.666666666667% |
| Estatística exata | Lucros 2/-1/0 produzem expectativa 1/3 e acerto 1/3; pequenos lucros não viram empate pelo arredondamento; HALF_EVEN nas razões positivas/negativas |
| Drawdown | Sequência 1000/1100/990/1050/1100/1080 produz máximo 10%, queda 110 e maior duração 180 s, seguida de episódio aberto de 60 s |
| Episódios e empates | Picos iguais atualizam âncora, vale empatado preserva primeiro ponto, duração zero em mesmo timestamp é válida, máximo percentual/absoluto/duração podem vir de episódios diferentes |
| Benchmarks | Compra passiva na primeira abertura, piso exato no quantum, resíduo não negativo, custos iguais aos da configuração e motivo explícito quando quantidade fica abaixo do quantum |
| Idempotência/imutabilidade | Fill repetido não duplica efeitos; ID divergente falha; entradas congeladas; preparação falha sem mudar caixa/posição/ordem/ledger aceitos |
| Reconciliação adversa | Movimento adulterado é recusado; falha de ledger não é convertida em rejeição de estratégia |
| API incremental | Mesmos eventos progressivos e por arquivo geram o mesmo ledger e a mesma análise |
| Causalidade | Mudanças futuras preservam movimentos e pontos anteriores; variação de OHLCV final não altera o fill/marca da abertura; prefixo truncado preserva os pontos já disponíveis |
| Lacuna | Status INTERRUPTED, scope ACCEPTED_PREFIX e referências somente até o último evento aceito; pendência NEW preservada, sem abertura/fill posterior |
| Falha técnica | Referências preservam o motivo real da interrupção técnica, sem substituí-lo por DATA_GAP |
| Rejeição/término | Ordem rejeitada ou NO_FUTURE_OPEN não cria movimento ou taxa; código 2 conserva análise |
| Contexto/tipos | Precisão externa 2, ROUND_UP e traps/flags adversos não alteram resultados/contexto; bool em contagem/duração/flag, datas sem fuso e curvas inválidas recusados |
| CSV/Markdown | Cabeçalhos comparados com a especificação versionada, razões/motivos corretos, ausência de trades com arquivo só de cabeçalho, UTF-8/LF e reconstrução das exportações a partir do JSON |
| CLI/arquivos | Códigos 0/1/2, schemas antigos preservados, nove arquivos enriquecidos, entrada inválida sem saída e recusa de sobrescrita sem alterar arquivos |
| Falha de escrita | Erro técnico propagado, sem sucesso fictício; regressões anteriores também conferem o marcador INCOMPLETE |
| Segurança/offline | Strings são escapadas no HTML/Markdown e no payload de script; socket bloqueado não impede análise; nenhum dado real ou pacote externo é necessário |

Os cenários negativos foram invocados pela suíte com arquivos temporários: código
1 em entrada inválida/lacuna/saída existente, código 2 em rejeição e combinação
Markdown sem análise. Esses códigos são os resultados esperados de cada caso,
não falhas ocultadas da suíte. Falhas técnicas/aritméticas inesperadas permanecem
erros, sem conversão para política de ordem ou estatística da estratégia.

## 5. Exportações e reprodução

As duas saídas finais contêm exatamente nove arquivos, incluindo os nove
comparados na seção 2. O ledger JSONL principal contém seis entradas: três da
estratégia, uma de caixa e duas de comprar/manter. O CSV de patrimônio contém
24 pontos (9/7/8 por carteira), sem apagar alterações no mesmo timestamp.
O CSV de métricas tem 23 métricas escalares; detalhes de episódios permanecem
no JSON/Markdown/HTML.

Os nove arquivos coincidiram byte a byte. A suíte também reconstruiu todos os
exports adicionais a partir de `report.json` e conferiu o HTML reconstruído por
hash de conteúdo, sem reler dados de mercado. A descoberta de ordem diferente
de campos após recarregar JSON foi corrigida com serialização canônica dos
parâmetros apresentados; não foram modificados valores financeiros.

## 6. Navegador e gráficos

O bundle Lightweight Charts 5.2.0 e suas licenças permaneceram inalterados.
Foi acrescentado somente `replayquant/assets/equity.js`, registrado no hash do
código. Os pontos financeiros são calculados no Python; JavaScript converte
valores apenas para desenho e mantém o texto exato no detalhe de cada ponto.

As curvas usam **índice de evento** no eixo horizontal, com horário UTC e fase
nos detalhes. Cada carteira tem sequência própria; o espaçamento visual não
representa duração física. Nenhum horário foi inventado e nenhum ponto de taxa
foi sobrescrito. Para comparação numérica usam-se as mesmas datas e convenção
de patrimônio; a duração das métricas é calculada pelos timestamps reais.

Verificação no Chrome headless, com DNS externo bloqueado e sem recursos de
rede carregados pela página:

- Desktop **1440×1600**, largura interna 1018 px; layout móvel explicitamente
  fixado em **390 px**, largura interna 324 px, sem interferência do CSS das
  tabelas nos gráficos.
- Nove pontos da estratégia, sete de HOLD_USDT e oito de BUY_HOLD_BTC confirmados
  na API pública da biblioteca; série não perde amostras de mesmo horário.
- Antes/depois da taxa em 12:01: patrimônio 1000 e 999.9, com X diferentes
  (356/458 px em desktop, aproximadamente 86.11/111 px no móvel) e Y diferentes.
- Navegação e botão de visualização completa mantêm o eixo esquerdo fixo.
- As três capturas de impressão geraram PNG e foram inspecionadas.
- HTML completo ampliado inicializou candles e três curvas com **240 candles**,
  **seis marcadores** e **487/481/482 pontos**, respectivamente. As quatro
  capturas de Canvas foram geradas e a lista de recursos externos ficou vazia.

Comandos de navegador efetivamente executados com código **0** usaram
`google-chrome --headless --no-sandbox --disable-gpu`,
`--disable-background-networking`, `--host-resolver-rules='MAP * ~NOTFOUND'`,
`--dump-dom`, `--screenshot` e perfis em `/tmp`, autorizados fora da sandbox.
Cópias de teste com instrumentação de API/eventos ficaram em
`/tmp/sprint08-browser.html`, `/tmp/sprint08-browser-mobile.html` e
`/tmp/sprint08-full-browser.html`. A página entregue não recebe essa
instrumentação extra.

Capturas inspecionadas: `/tmp/sprint08-curvas-desktop.png`,
`/tmp/sprint08-curvas-mobile.png`, `/tmp/sprint08-relatorio-completo.png` e
`/tmp/sprint08-impressao-curva.png`. As medidas foram conferidas por asserts
sobre os DOMs em `/tmp/sprint08-browser-desktop-dom.html`,
`/tmp/sprint08-browser-mobile-dom.html` e `/tmp/sprint08-full-dom.html`.

## 7. Decisões, limites e pendências

- O ledger é integrado ao fill em todos os modos; a flag controla análise,
  schema e exportações. Entradas e estado proposto são preparados antes do
  commit financeiro. Até receber a primeira abertura válida, a entrada inicial
  aguarda o horário do relógio; relatórios exigem fechamento/encerramento válido.
- Curvas são projeções de leitura do ledger imutável e dos eventos aceitos,
  sem repetir preenchimentos ou consultar dados futuros. A API progressiva
  usa exatamente o mesmo núcleo da simulação por arquivo.
- As referências reutilizam custos e transições do ledger. Sua compra passiva
  tem origem explicitamente anterior ao replay; não flexibiliza a regra de
  submissão no fechamento para as estratégias.
- Valores exatos ficam no ledger/JSON e razões; arredondamento é exclusivo de
  apresentação. O JavaScript não calcula lucros, métricas ou dimensionamento.
- As métricas CSV e o ledger podem ser auditados sem navegador; o HTML mantém
  tabelas e alternativa sem JavaScript. Posição aberta e taxa hipotética são
  distintas de trade encerrado e taxa paga.

Validado somente Python **3.12.14** e o Chrome disponível neste ambiente.
Não foram executados testes em outros sistemas/versões Python/navegadores,
medidas de grandes volumes, toque em aparelho físico, paginação integral de PDF,
recuperação após reinício, dados reais, reservas, risco ou execução operacional.
As capturas de Canvas para impressão foram conferidas; isso não substitui uma
validação de paginação de todos os PDFs possíveis.

Não há pendência conhecida de aceite obrigatório no escopo especificado.
Nenhum commit, publicação ou alteração externa de negociação foi realizado.
