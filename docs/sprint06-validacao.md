# Sprint 06 — Registro de validação

Validação executada em **06/11/2026**, na raiz do ReplayQuant, com **Python
3.12.14** e ambiente `.venv`. A implementação usa somente a biblioteca padrão.
Não foram instalados pacotes externos, acessadas exchanges, usadas credenciais ou
enviadas ordens. Os valores abaixo são observados em simulação fictícia.

## 1. Estado da entrega

Implementados motor sequencial, leitura JSON estrita, configuração versionada,
carteira em memória, ordens manuais, preenchimento na abertura seguinte,
idempotência, eventos, manifesto, relatório e CLI. A especificação permanece em
[sprint06.md](sprint06.md); instruções de uso em [README.md](../README.md).

A suíte relevante passou: **27 testes**, incluindo subcasos de validação de
entrada e invocações da CLI. Não há pendências conhecidas nos requisitos da
Sprint 06. Não foram implementadas as sprints seguintes.

## 2. Comandos efetivamente executados

Preparação na raiz do projeto:

| Comando | Código observado | Resultado observado |
| --- | --- | --- |
| `python3 --version` | 0 | Python 3.12.14 |
| `python3 -m venv .venv` | 0 | Ambiente criado localmente |
| `source .venv/bin/activate` | 0 | Sessão Bash com o ambiente ativado; comandos subsequentes usaram seu Python |
| `python --version` | 0 | Python 3.12.14 |

Após a implementação final do código, foram executados os comandos abaixo. Cada
código foi conferido individualmente por um executor local com `subprocess.run`;
sua saída e stderr foram preservados em arquivo temporário.

| Comando | Código observado | Resultado observado |
| --- | --- | --- |
| `python -m replayquant --help` | 0 | Subcomandos `demonstrar` e `executar` disponíveis |
| `python -m replayquant demonstrar --formato texto` | 0 | Exemplo obrigatório conferido; fórmulas, saldos, taxas e limites apresentados |
| `python -m replayquant demonstrar --formato json` | 0 | JSON válido; resultado líquido 0.799000 USDT; stderr vazio |
| `python -m unittest discover -s tests -v` | 0 | 27 testes aprovados (`OK`) |
| `python -m replayquant executar --dados data/fixtures/sprint06-candles.json --config experiments/sprint06-manual.json --saida "$validacao_dir/execucao-a" --formato json` | 0 | Três artefatos gerados |
| Mesmo comando com `--saida "$validacao_dir/execucao-b"` | 0 | Segunda execução independente gerada |
| `cmp "$validacao_dir/execucao-a/manifest.json" "$validacao_dir/execucao-b/manifest.json"` | 0 | Manifestos idênticos byte a byte |
| `cmp "$validacao_dir/execucao-a/events.jsonl" "$validacao_dir/execucao-b/events.jsonl"` | 0 | Eventos idênticos byte a byte |
| `cmp "$validacao_dir/execucao-a/report.json" "$validacao_dir/execucao-b/report.json"` | 0 | Relatórios idênticos byte a byte |
| `git diff --check` | 0 | Nenhum erro de whitespace nos arquivos rastreados alterados |

O diretório temporário efetivamente criado nesta verificação foi
`/tmp/replayquant-sprint06-l3sdl0n9`. Os comandos receberam seus caminhos absolutos;
`validacao_dir` na tabela é uma abreviação para esse diretório. O arquivo
`commands.json` nesse local contém argumentos, códigos e saídas dos comandos da
verificação final. Esses artefatos podem ser removidos pela limpeza do sistema;
a conclusão desta documentação não depende de sua permanência.

Para reproduzir a comparação em outra execução, usar um diretório novo, na mesma
sessão Bash com `.venv` ativada:

```bash
validacao_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint06-candles.json --config experiments/sprint06-manual.json --saida "$validacao_dir/execucao-a" --formato json
python -m replayquant executar --dados data/fixtures/sprint06-candles.json --config experiments/sprint06-manual.json --saida "$validacao_dir/execucao-b" --formato json
cmp "$validacao_dir/execucao-a/manifest.json" "$validacao_dir/execucao-b/manifest.json"
cmp "$validacao_dir/execucao-a/events.jsonl" "$validacao_dir/execucao-b/events.jsonl"
cmp "$validacao_dir/execucao-a/report.json" "$validacao_dir/execucao-b/report.json"
```

Verificar o código de cada comando individualmente. O exemplo não deve reutilizar
`runs/sprint06-manual` nem apagar resultados para forçar uma nova gravação.

## 3. Resultado financeiro esperado e observado

| Valor | Esperado USDT | Observado USDT |
| --- | --- | --- |
| Caixa inicial | 1000 | 1000 |
| Compra: bruto | 100 | 100.000 |
| Compra: taxa | 0.1 | 0.100000 |
| Compra: desembolso | 100.1 | 100.100000 |
| Caixa após compra | 899.9 | 899.900000 |
| Venda: bruto | 101 | 101.000 |
| Venda: taxa | 0.101 | 0.101000 |
| Venda: recebimento | 100.899 | 100.899000 |
| Taxas totais | 0.201 | 0.201000 |
| Resultado líquido da ida e volta | 0.799 | 0.799000 |
| Caixa final | 1000.799 | 1000.799000 |

A posição passou de 0 para 0.001 BTC e terminou em 0.000 BTC. Zeros finais são
preservados pela serialização, sem diferença numérica. As comparações financeiras
usaram `Decimal` exato, sem tolerância de float.

Identificação observada na verificação final do código:

```text
run_id = 0148770c06bda306fdaae8e3f94b87c7b7d1ca652ef76fc312d3ab8931b9ac96
```

Esse ID não é constante da aplicação: muda se os bytes das entradas, código ou
versão Python mudarem. A suíte também recalculou independentemente hashes dos
arquivos, lista ordenada do código e identidade final.

## 4. Comportamentos conferidos pela suíte

| Grupo | Evidência observada |
| --- | --- |
| Tempo e causalidade | Submissão preservou saldos; eventos com o mesmo timestamp respeitaram sequência; preenchimento antecipado foi recusado; aberturas não expuseram OHLCV futuro |
| Prefixo | Alterar high/low/close/volume posteriores preservou preenchimentos e prefixo financeiro; processar um prefixo menor produziu o mesmo preenchimento anterior |
| Caixa com taxa | Compra com capital 100 foi recusada sem débito; com capital 100.1 houve aceitação estimada e rejeição na abertura de 101000, sem preenchimento parcial |
| Posição e pendência | Venda sem BTC, compra com posição aberta e segunda solicitação enquanto pendente foram recusadas, preservando o estado pertinente |
| Encerramento | Última ordem ficou UNEXECUTED com NO_FUTURE_OPEN; roteiro vazio conservou caixa e taxa zero; compra isolada manteve BTC sem resultado inventado |
| Idempotência | Duplicatas equivalentes de ordem, candle e preenchimento não repetiram efeitos; conflito de ID foi recusado sem alterar o snapshot financeiro |
| Entrada | JSON inválido, chaves duplicadas, schema booleano, campos extras/ausentes, floats, não finitos, limites decimais, taxas inválidas, slippage não zero, OHLC inválido, aberto, datas sem fuso, lacunas e ordem temporal incorreta foram recusados |
| API Python e UTC | Construções diretas inválidas foram recusadas; offsets equivalentes normalizaram para o mesmo instante UTC |
| Aritmética | Precisão externa 2, ROUND_UP e trap/flag de Inexact não afetaram o resultado nem foram alterados; falhas de representação exata não efetivaram débitos, taxas ou preenchimentos |
| CLI e gravação | Códigos 0/1/2 conferidos; stdout JSON válido; arquivo, diretório e symlink existentes recusados sem alteração; falha de escrita retornou erro técnico e preservou marcador de incompletude |
| Falhas inesperadas | RuntimeError não foi transformado em rejeição de ordem |
| Independência | Replay com socket bloqueado funcionou; cópia isolada em diretório com espaço produziu o mesmo relatório, sem projetos vizinhos |

Os casos negativos foram invocados pela suíte com entradas temporárias. Os códigos
observados foram: **1** para dados inválidos/arquivo ausente/saída existente,
**2** para ordem recusada ou sem abertura futura e **2** para sintaxe inválida do
`argparse`. Ordens recusadas não fizeram o teste falhar: cada teste verificou o
código e o estado esperados. Uma falha técnica fictícia de gravação foi injetada
com `unittest.mock`; isso valida o tratamento, sem alegar uma falha física de disco.

## 5. Decisões de implementação

- Arquivos completos são pré-validados; lacunas impedem iniciar o replay.
  `Session` também verifica as fases de abertura/fechamento e continuidade das
  aberturas quando recebe eventos pela API.
- Contexto financeiro local de precisão 40 com trap de `Inexact`. Saldos derivados
  não herdam os limites de representação da entrada, mas precisam ser não
  negativos, finitos e exatamente representáveis. Falha técnica/aritmética
  interrompe a chamada; o evento de abertura já liberado pode permanecer no log,
  sem comprometer saldo, ordem pendente, taxa ou preenchimento.
- `requirements.lock` documenta zero dependências externas; a versão de runtime
  fica em `.python-version`. Nenhuma instalação é necessária para executar na raiz.
- Manifesto usa a lista ordenada de caminhos relativos/hashes especificada; não
  inclui hora real, caminho absoluto, estado Git ou documentação no hash do código.
- Gravação usa diretório exclusivo e arquivos temporários individuais, com
  manifesto por último e marcador `INCOMPLETE` até terminar. Uma saída incompleta
  não é reutilizada ou apagada automaticamente.

## 6. Limitações e verificações não executadas

Foi validado somente Python **3.12.14** neste ambiente. O requisito declarado é
3.11+, mas não foi executada uma matriz de versões ou sistemas operacionais.
Não foram testados desempenho em grandes volumes, recuperação após reinício,
persistência transacional contra queda do sistema, liquidez real ou dados de
exchange. Esses itens não fazem parte do aceite desta sprint.

O modelo supõe preenchimento total, liquidez ilimitada e slippage zero; não tem
modelo de spread. Não utiliza volume final para validar a abertura. Não há
reservas, gestão de risco, indicadores, carteira persistente, marcação a mercado,
benchmark ou avaliação de rentabilidade. O resultado de 0.799 USDT é uma conferência
manual fictícia, não evidência de viabilidade de investimento.

Nenhum commit ou publicação foi realizado.
