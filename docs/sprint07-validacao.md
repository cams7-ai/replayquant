# Sprint 07 — Registro de validação

## Atualização: TradingView Lightweight Charts incorporado

Em **07/11/2026**, após autorização do usuário, o SVG foi substituído por
**Lightweight Charts 5.2.0**, com bundle standalone incorporado ao HTML e
controlador local em `replayquant/assets/chart.js`. A apresentação ganhou zoom,
navegação, controles de período, cursor de preço/tempo, eixos nativos e detalhes
exatos de candles/execuções. Os marcadores usam o horário e o preço efetivo do
fill; linhas entre compra/venda mantêm as cores do líquido após taxas.

O gráfico exige JavaScript, com mensagem alternativa quando desabilitado. As
tabelas e a memória de cálculo permanecem estáticas e acessíveis. A impressão
captura o Canvas atual como PNG; **Ver tudo** permite incluir todo o período.
Não há CDN, busca de dados ou recursos externos ao abrir o arquivo. O link de
atribuição à TradingView é navegação opcional, não carregamento de recurso.

### Dependência, licença e identidade

- Bundle obtido do pacote oficial `lightweight-charts@5.2.0` no registro npm,
  com integridade **SHA-512 verificada** contra os metadados publicados.
- LICENSE Apache-2.0 do pacote e NOTICE do tag oficial `v5.2.0` foram preservados.
  A dependência incluída `fancy-canvas@2.1.0` usa MIT; seu aviso oficial também
  foi incluído, pois não estava presente no tarball npm.
- Fontes, versão e hashes estão em
  `replayquant/assets/lightweight-charts-vendor.json`. LICENSE/NOTICE e atribuição
  aparecem no próprio HTML, e o bundle conserva seu cabeçalho original.
- O manifesto inclui **todos os arquivos de `replayquant/assets/`** na lista
  ordenada `code_files`, além dos Python e metadados já existentes. A verificação
  independente do hash foi atualizada para cobrir esses assets. Assim, mudar
  JavaScript ou avisos altera a identidade mesmo sem mudar arquivos Python.
- `frontend_dependencies` registra a biblioteca no manifesto SMA. Não foram
  instalados pacotes Python ou npm; o projeto continua executável offline.

### Verificações realmente executadas

| Verificação | Código/resultado observado |
| --- | --- |
| `.venv/bin/python -m unittest discover -s tests -v` | **0; 71 testes aprovados** em Python 3.12.14 |
| `demonstrar --estrategia sma --formato html` | **0**, HTML independente com oito candles e duas execuções |
| Duas invocações `executar` com fixture/configuração ampliadas e `--formato html` | **0/0**, 240 candles, seis execuções e posição final zerada |
| Comparação byte a byte de manifesto, eventos e relatório das duas saídas | Três arquivos idênticos |
| Chrome headless com DNS externo bloqueado, em desktop e layout móvel | **0/0**, inicialização e verificações de interação aprovadas |
| Caso de preços constantes no Chrome | **0**, gráfico inicializado sem execuções |
| `git diff --check` | **0**, sem erro de whitespace |

Os testes adaptados verificam os mesmos contratos financeiros e temporais na
nova fronteira de apresentação, passando a inspecionar o payload incorporado em
vez de elementos SVG. Conferem dados fechados, preços efetivos, ganho/perda após
taxas, posição aberta sem lucro inventado, lacunas, códigos da CLI, reconstrução
por `report.json`, contexto decimal externo, versões/licenças, integridade dos
assets e proteção de strings contra fechamento de `script`. Uma checagem antiga
que procurava `NaN` em todo o HTML foi restringida aos dados do gráfico: a
biblioteca usa legitimamente essa palavra em seu código interno.

O CSS das tabelas foi limitado a `.table-wrap` após a conferência móvel identificar
que o estilo responsivo do relatório interferia na tabela interna do Canvas.
Na validação final, a tabela interna mediu **1018 px** em desktop e **324 px** no
layout de **390 px**, coincidindo com seus contêineres e sem corte do gráfico.

### Interações e conferência visual

Uma cópia instrumentada em `/tmp/replayquant-lwc-browser-check.html` foi aberta
no Chrome com `--host-resolver-rules='MAP * ~NOTFOUND'`,
`--disable-background-networking`, `--dump-dom` e `--screenshot`. A cópia móvel
`/tmp/replayquant-lwc-browser-mobile.html` fixa o layout em 390 px para contornar
a largura mínima de janela do headless. A instrumentação usa a API pública e
eventos DOM, sem alterar o HTML entregue. Foram conferidos:

- Versão **5.2.0**, **240 candles** e **seis marcadores** com os preços efetivos.
- **Últimos 60**: faixa de 60 candles; **Zoom +**: aproximadamente 40.2;
  **Zoom −**: aproximadamente 60.3; **Ver tudo**: período completo.
- Roda do mouse reduziu a faixa de aproximadamente 241 para 219 candles.
- Navegação temporal mudou a faixa mantendo a posição do eixo esquerdo:
  **203.5 px** em desktop e **33 px** em layout móvel; escala direita oculta.
- Cursor na primeira compra exibiu os valores exatos **99940.85101 USDT/BTC**,
  **0.001 BTC** e taxa **0.09994085101 USDT** no texto abaixo do gráfico.
- A captura de impressão gerou PNG válido com candles, linhas e marcadores.
  `/tmp/replayquant-lwc-print-capture.png` foi extraído e inspecionado; não foi
  feita revisão de paginação de PDF.
- A página não carregou recursos externos: a lista de recursos observada estava
  vazia. Não houve erros de inicialização nos casos verificados.

Capturas inspecionadas: `/tmp/replayquant-lwc-expanded-desktop.png` e
`/tmp/replayquant-lwc-expanded-mobile.png`. Os DOMs com as medidas estão em
`/tmp/replayquant-lwc-check-desktop.html` e
`/tmp/replayquant-lwc-check-mobile.html`. A checagem usa captura pública do Canvas
para concluir atualizações pendentes antes de ler faixas no modo headless.

HTMLs finais: `/tmp/replayquant-sma-expandido.html` e
`/tmp/replayquant-sma-lightweight.html`. Artefatos e argumentos/códigos das
invocações finais em `/tmp/replayquant-lightweight-g0bpfp5d`. Identidade da execução ampliada:

```text
run_id = 0270b4aa0ec6f97f9d99e2d9d576dae8a100fc414d0c2df8550707f0c1936054
```

Resultado financeiro preservado: caixa **1000.90155066834 USDT**, BTC **zero**,
três operações encerradas (duas positivas e uma negativa), taxas
**0.60339361166 USDT**, lucro realizado **0.90155066834 USDT**. Não foram alterados
candles, parâmetros SMA, sinais, ordens ou ledger nesta integração.

A validação de navegador foi feita no Chrome disponível no ambiente. Não foram
executadas matrizes de outros navegadores, testes de toque em aparelho físico,
contrastes em todos os temas ou medições de desempenho em grandes volumes.
Os números JavaScript são exclusivos do desenho; preços, taxas, resultados e
razões de decisão continuam exatos no Python e nas strings do relatório.

Os registros seguintes são históricos e descrevem as apresentações anteriores.


## Atualização: eixo de preço fixo e grade de tempo

Em **07/11/2026**, o eixo de preço passou a ser uma camada fixa à esquerda
durante a rolagem horizontal, com título e valores sempre visíveis. A escala
compartilha os mesmos limites, altura e coordenadas dos candles. Linhas verticais
pontilhadas foram alinhadas às marcações de horário, com espaçamento que permite
acompanhar os candles durante a rolagem. Na impressão, a escala é incorporada
ao SVG para continuar alinhada quando o gráfico é redimensionado.

Verificações efetivamente executadas em Python 3.12.14:

- `.venv/bin/python -m unittest discover -s tests -v`: código **0**, **70 testes
  aprovados**. A regressão adicional confere a escala fixa, igualdade de valores
  e coordenadas com a escala de impressão, e alinhamento das linhas pontilhadas
  verticais aos horários.
- `executar` com os arquivos ampliados e `--formato html`: código **0**, HTML
  atualizado em `/tmp/replayquant-sma-expandido.html`, com artefatos em
  `/tmp/replayquant-eixo-fixo-ag_8kyix/execucao`.
- `git diff --check`: código **0**.

Também foi feita verificação real de rolagem no Chrome headless, com uma cópia
instrumentada do gráfico em `/tmp/replayquant-axis-browser-check.html` (a saída
normal continua sem JavaScript). Em desktop **1440×1100**, após rolar **1800 px**,
a posição horizontal do eixo permaneceu **203.5 px** e o gráfico moveu-se
exatamente 1800 px. Em tela **390×1300**, após rolar **2400 px**, o eixo permaneceu
em **33 px** e o gráfico moveu-se exatamente 2400 px. Em ambos, a escala SVG foi
**1:1** e os topos dos SVGs de preço e candles permaneceram alinhados.

As capturas `/tmp/replayquant-axis-desktop.png` e
`/tmp/replayquant-axis-mobile.png` foram inspecionadas visualmente após a rolagem;
os preços continuaram visíveis e as linhas verticais acompanharam os horários.
Os comandos Chrome com `--dump-dom`, `--virtual-time-budget=1000` e `--screenshot`
retornaram **0**. As medidas foram conferidas por asserts sobre os DOMs gerados.
Não foi feita inspeção de PDF; o teste estrutural confere a escala de impressão.
Não houve alteração de dados, sinais, execuções ou resultados financeiros.


## Atualização: ganhos, perda e saldo final positivo no cenário sintético

Em **07/11/2026**, a fixture ampliada foi ajustada a pedido do usuário para
exibir operações com lucro e prejuízo líquidos e terminar com lucro realizado
positivo. Foram preservados os 240 candles, os parâmetros SMA 9/21, capital,
quantidade, taxas/slippage e a fixture original de oito candles. O trecho final,
a partir de 15:27 UTC, recebeu uma reversão de preços sintética controlada,
com aritmética inteira em centavos e PRNG local de semente 707. Esse desenho
intencional serve à demonstração visual, sem evidência de rentabilidade real.

Resultados efetivamente observados após taxas e slippage:

| Operação | Compra UTC | Venda UTC | Resultado líquido USDT |
| --- | --- | --- | --- |
| 1 | 12:38 | 13:25 | +0.73754871919 |
| 2 | 14:20 | 15:02 | +0.77489849630 |
| 3 | 15:26 | 15:39 | -0.61089654715 |
| Total | — | — | **+0.90155066834** |

Caixa inicial **1000 USDT**, caixa final **1000.90155066834 USDT**, BTC final
**zero**, nenhuma ordem pendente e taxas totais **0.60339361166 USDT**. O lucro
reconcilia com a soma dos três pares encerrados e com caixa final menos inicial;
não depende de marcação ou liquidação fictícia de posição aberta.

O HTML passou a mostrar a soma dos resultados realizados no resumo quando há
múltiplas operações, além do total abaixo do gráfico. As cores são determinadas
pelo líquido após taxas. O contrato JSON de `round_trip_result` foi preservado:
continua indisponível quando há múltiplas idas e voltas. O motor não foi alterado.

Verificações executadas em Python 3.12.14:

- `.venv/bin/python -m unittest discover -s tests -v`: código **0**, **69 testes
  aprovados**, incluindo uma regressão do cenário com ganho, perda, BTC zero e
  reconciliação exata do lucro realizado.
- Duas execuções de `executar` com os arquivos ampliados e `--formato html`:
  código **0** em ambas, 240 avaliações e seis preenchimentos. `manifest.json`,
  `events.jsonl` e `report.json` foram comparados byte a byte e coincidiram.
- `git diff --check`: código **0** após correção de um espaço final.

HTML atualizado em `/tmp/replayquant-sma-expandido.html`; artefatos e registro
das invocações em `/tmp/replayquant-sma-misto-ab7dw_kc/`. Os registros seguintes
são históricos e descrevem as versões anteriores do cenário.


## Atualização: cenário ampliado de candles

Em **07/11/2026**, foi incluída a fixture adicional
`data/fixtures/sprint07-candles-expandido.json`, com **240 candles contíguos de 1m**
entre 12:00 e 16:00 UTC de 01/01/2026. A configuração
`experiments/sprint07-sma-expandido.json` usa janelas 9/21 e mantém capital 1000,
quantidade 0.001 BTC e taxa/slippage 0.001. A fixture original de oito candles
permanece como referência de testes e demonstração manual.

Os candles são sintéticos, com pavios e volume variável, gerados uma vez por
aritmética inteira em centavos e PRNG local com semente 7. O JSON fixo é a fonte
versionada do experimento; não representa preços de exchange ou calibração de
liquidez/volatilidade real. Não houve ajuste de parâmetros para obter lucro.

Validação efetivamente executada em Python 3.12.14:

- Leitura e validação pelo parser do projeto, replay completo e HTML pela CLI:
  código **0**, 240 avaliações/candles, cinco preenchimentos/marcadores e duas
  idas e voltas encerradas no gráfico.
- Caixa final **900.27010585533 USDT**, BTC final **0.001** e taxas acumuladas
  **0.50266143467 USDT**. O caixa não é patrimônio ou lucro: há posição aberta.
- Demonstração original SMA em JSON: código **0**, oito candles e conferência
  automática dos resultados originais aprovada.
- `git diff --check`: código **0**.

HTML gerado em `/tmp/replayquant-sma-expandido.html`. Artefatos e registro da
invocação em `/tmp/replayquant-sma-expandido-g3rk988p/`. A suíte anterior não foi reexecutada nesta alteração de
fixtures/documentação; não houve mudança no código do motor ou do gráfico.


## Atualização: gráfico de candles e resultados líquidos

Em **07/11/2026**, foi adicionado gráfico SVG independente à saída HTML SMA,
com candles processados, marcadores nos horários/preços efetivos de COMPRA e
VENDA e ligação colorida pelo resultado de cada ida e volta após taxas. O
resumo financeiro também destaca ganho/perda. Verde indica ganho líquido,
vermelho perda e cinza empate; compras têm marcador azul. A variação do candle
usa cores próprias de alta/queda, sem determinar o resultado financeiro.

O relatório SMA schema 2 recebeu o campo adicional `candles`, derivado somente
dos eventos CLOSE aceitos, para reconstruir o gráfico a partir de `report.json`.
Não foram alterados cálculos financeiros, decisões, dados de entrada ou o schema
manual. O cálculo visual usa razões exatas, sem influência do contexto decimal;
float é usado somente nas coordenadas de desenho. Posições abertas e ordens não
executadas não recebem lucro realizado ou marcadores de preenchimento fictício.

Verificações realmente executadas em Python **3.12.14**:

| Comando | Código observado | Resultado |
| --- | --- | --- |
| `.venv/bin/python -m unittest discover -s tests -v` | 0 | **68 testes aprovados**, incluindo oito novos testes do gráfico |
| `.venv/bin/python -m replayquant demonstrar --estrategia sma --formato html > /tmp/replayquant-sma-candles.html` | 0 | HTML com oito candles, COMPRA a 100100, VENDA a 99900, perda líquida 0.4 e taxas 0.2 USDT |
| `git diff --check` | 0 | Sem erros de whitespace |

Os testes cobrem ganho líquido positivo, empate, ganho bruto que vira perda após
taxas, ausência de execução, posição aberta, lacuna sem exibir candles futuros,
preços constantes, compatibilidade com relatórios antigos, escape de conteúdo,
contexto decimal externo e reconstrução do HTML a partir dos artefatos da CLI.
Todos os 60 testes anteriores continuaram aprovados, incluindo reprodução dos
três artefatos e regressões manuais.

O HTML foi inspecionado visualmente com Chrome headless em **1440×2000** e
**390×2400**, incluindo o gráfico e sua rolagem horizontal em tela estreita.
Capturas em `/tmp/replayquant-sma-chart-desktop.png` e
`/tmp/replayquant-sma-chart-mobile.png`. A execução local do Chrome fora da
sandbox usou perfis em `/tmp`, sem dependências externas na página. Não foi
feita inspeção de impressão/PDF ou de grandes volumes de candles.

O registro abaixo descreve a validação original, anterior à inclusão do gráfico;
sua identidade de execução pertence à versão então verificada.


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
