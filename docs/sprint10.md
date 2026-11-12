# Sprint 10 — Estratégias modulares

**Projeto** ReplayQuant  
**Nível** intermediário  
**Referência** [Planejamento](planejamento.md), seções 4, 10, 21 e 23  
**Pré-requisitos** Sprints 06 a 09 implementadas e verificadas  
**Estado** implementação e validação registradas em [sprint10-validacao.md](sprint10-validacao.md). Os contratos e o prompt abaixo ficam preservados como referência da etapa.

## 1. Objetivo e estado de entrada

Comparar SMA, cruzamento de EMA e RSI por um contrato de estratégia comum, reutilizando execução, risco, reservas, ledger, métricas e apresentação. Cada estratégia recebe sua própria sessão e seu próprio capital. Cada avaliação deve permitir reconstruir o indicador e o motivo do sinal ou de sua ausência.

Trabalhar em `/home/cams7/Dev/Cripto_Tests/replayquant`. A referência consultada é o commit `92eb2dd`. Inspecionar HEAD, `git status`, instruções `AGENTS.md` aplicáveis e alterações posteriores antes de implementar. Ler os contratos e registros de validação das Sprints 06 a 09. Verificar os pré-requisitos pela suíte existente e pelas demonstrações de entrada, registrando qualquer lacuna antes do trabalho dependente.

Atualmente, `replayquant/strategies.py` implementa `SMACross`, os modelos/parser aceitam parâmetros SMA, e `SMASession`/`RiskSession` instanciam essa estratégia diretamente. Há risco schema 4 com análise obrigatória, API incremental, relatórios offline e exemplos SMA expandidos. A implementação deve evoluir esses pontos e reutilizar o núcleo financeiro.

## 2. Escopo

Entregar contrato de estratégia, registro por nome/versão, adaptação da SMA existente, EMA_CROSS e RSI_REVERSION. Fixar inicialização, suavização, aquecimento, igualdade, precisão, motivos e isolamento. Parametrizar regras na configuração e expor identidade e avaliações nos artefatos e no HTML.

Continuar com `FICTICIA/BTCUSDT/1m`, posição comprada única, preenchimentos totais e uma intenção comum pendente por sessão. Taxas, slippage, filtros, revalidação, reservas, bloqueios e proteções seguem os contratos da Sprint 09. Preservar os caminhos manuais e SMA legados.

Usar Python >= 3.11, com a versão concreta e o ambiente registrados na validação. Biblioteca padrão e `unittest` atendem esta etapa. Manter execução offline e os assets/licenças existentes. Multipar, carteira compartilhada, otimização automática, seleção pelo lucro, walk-forward, dados reais, execução parcial e conectividade de negociação pertencem às etapas posteriores.

## 3. Contrato de estratégia e registro

### 3.1. Interface e isolamento

Definir interface tipada com identidade imutável, parâmetros validados e operação incremental equivalente a `on_close(candle) -> evaluation`. A estratégia recebe somente um candle fechado liberado pelo relógio. Seu estado contém histórico já observado e indicadores. A sessão entrega sinais ao fluxo existente de decisão, risco e ordens.

O registro resolve exatamente os pares `SMA_CROSS/1`, `EMA_CROSS/1` e `RSI_REVERSION/1`. Cada criação retorna uma instância nova. Nome/versão desconhecidos geram erro de validação antes de iniciar a sessão. Usar registro explícito local, com rejeição de duplicatas. A configuração seleciona implementações previamente registradas.

Estado de estratégia, histórico, ordens, reservas e carteira pertencem à sessão. Duas sessões intercaladas devem produzir os mesmos resultados que suas execuções isoladas. Aplicar as garantias existentes de deduplicação, conflito, ordenação e preparação/commit também à atualização do indicador. Falha de validação ou preparação deve preservar o último estado aceito.

### 3.2. Avaliações e sinais

Cada avaliação nova registra identidade e parâmetros, candle/horário de disponibilidade, contagem de observações, valores anterior/atual, prontidão, comparação, lado opcional e motivo estável. Distinguir `WARMUP`, `NO_CROSS`, `CROSS_UP`, `CROSS_DOWN`, `EXIT_OVERSOLD` e `EXIT_OVERBOUGHT` conforme a estratégia. Campos indisponíveis usam `null` e motivo. Descrever o significado de cada razão exportada.

Indicador pronto e prontidão para sinal são estados distintos. A primeira observação com indicador calculável ainda não tem indicador anterior para cruzamento. Uma avaliação com sinal mantém vínculos determinísticos com sinal, decisão, ordem e fill, inclusive quando a política rejeita a intenção.

A estratégia pode emitir BUY ou SELL independente da carteira. A sessão aplica as regras existentes para posição aberta, venda sem ativo, pendência e reentrada. Permanência numa região ou acima de uma média gera `NO_CROSS`, sem novas tentativas automáticas. Rejeição/cancelamento exige um novo cruzamento para nova intenção.

### 3.3. Tempo e precisão

Abertura elegível, fechamento, sinal e execução seguem a ordem lógica já definida. OHLC completo só entra na estratégia no fechamento. O próximo evento de abertura pode compartilhar timestamp nominal com o sinal. Sinal no último candle fica pendente/não executado conforme o contrato existente. Lacuna interrompe antes de consumir o candle posterior, preservando o prefixo aceito.

Usar `Decimal` nas entradas e na contabilidade. Para SMA, EMA e RSI desta versão, usar razões exatas nas recorrências e comparações. Converter `Decimal` finito em `Fraction` preserva seu valor. Exportar numerador/denominador e valor decimal de apresentação com política explícita. Arredondamento de apresentação não participa da decisão. Respeitar o contexto financeiro local e os limites atuais de entrada também pela API Python.

## 4. Regras completas dos indicadores

### 4.1. SMA_CROSS versão 1

Parâmetros inteiros reais `1 <= short_window < long_window`. A SMA de janela N é a soma dos últimos N fechamentos dividida por N. A longa fica disponível no N-ésimo fechamento e a primeira comparação de cruzamento no fechamento N+1.

BUY quando curta anterior <= longa anterior e curta atual > longa atual. SELL quando curta anterior >= longa anterior e curta atual < longa atual. Igualdade atual não sinaliza. Preservar os resultados e semântica dos exemplos antigos ao adaptar `SMACross` ao contrato comum.

### 4.2. EMA_CROSS versão 1

Parâmetros inteiros reais `1 <= short_window < long_window`. Para cada janela N, usar `alpha = 2 / (N + 1)`. Inicializar a EMA com a SMA dos primeiros N fechamentos. A partir do fechamento seguinte, calcular `EMA_t = alpha * close_t + (1 - alpha) * EMA_anterior`.

Inicializar curta e longa em seus próprios pontos. A longa fica disponível em `long_window` observações. Sinais exigem duas observações consecutivas com ambas disponíveis, começando em `long_window + 1`. As desigualdades BUY/SELL e o tratamento de igualdade são os mesmos da SMA. Registrar a política `SMA_SEED` na identidade da estratégia versão 1.

### 4.3. RSI_REVERSION versão 1

Parâmetros `period` inteiro real >= 1 e limiares decimais `0 < oversold < overbought < 100`. Para cada variação de fechamento, calcular `gain = max(delta, 0)` e `loss = max(-delta, 0)`. Inicializar ganho/perda médios pelas médias simples das primeiras N variações, exigindo N+1 fechamentos.

Aplicar suavização de Wilder a cada variação seguinte, com `avg_gain_t = ((N - 1) * avg_gain_anterior + gain_t) / N` e fórmula equivalente para perda. Quando a soma é positiva, calcular `RSI = 100 * avg_gain / (avg_gain + avg_loss)`. Se apenas a perda média é zero, RSI=100. Se apenas o ganho médio é zero, RSI=0. Se ambos são zero, RSI=50, com indicação `FLAT_SEED_OR_STATE` no diagnóstico do indicador.

BUY na saída da sobrevenda, quando RSI anterior <= oversold e RSI atual > oversold. SELL na saída da sobrecompra, quando RSI anterior >= overbought e RSI atual < overbought. Igualdade atual não sinaliza. O primeiro sinal possível exige N+2 fechamentos. Se um salto cruzar ambos os limiares, aplicar os predicados direcionais, gerando no máximo um sinal. Registrar `WILDER_SMA_SEED` e a convenção de estado plano na versão 1.

## 5. Configuração, identidade e compatibilidade

Introduzir configuração **schema 5**, `mode: STRATEGY`, com risco e análise obrigatórios. Os schemas 1, 2 e 4 e o modo de saída 3 continuam aceitos com seus comportamentos documentados. A adaptação interna da SMA antiga resolve versão 1 sem exigir edição dos arquivos existentes.

Exemplo completo previsto para `experiments/sprint10-sma.json` com a fixture da seção 6, taxas e slippage zero para conferência manual dos indicadores e do fluxo.

```json
{
  "schema_version": 5,
  "mode": "STRATEGY",
  "source": "FICTICIA",
  "symbol": "BTCUSDT",
  "interval": "1m",
  "initial_cash": "1000",
  "fee_rate": "0",
  "slippage_rate": "0",
  "instrument_filters": {
    "step": "0.000001",
    "min_quantity": "0.000001",
    "min_notional": "0"
  },
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
    "name": "SMA_CROSS",
    "version": 1,
    "parameters": {"short_window": 2, "long_window": 3}
  }
}
```

Criar `experiments/sprint10-ema.json` substituindo somente o nome por `EMA_CROSS`. Criar `experiments/sprint10-rsi.json` substituindo o objeto strategy por `{"name":"RSI_REVERSION","version":1,"parameters":{"period":2,"oversold":"30","overbought":"70"}}`.

Validar campos exatos por estratégia, versão inteira real, limites de parâmetros, valores finitos, strings decimais e ausência de chaves duplicadas. Rejeitar booleanos como números, parâmetros de outra estratégia e combinações de modo/campos inválidas. Validar também instâncias construídas diretamente na API.

No caminho novo, manifesto, eventos e relatório identificam schema 5 e a estratégia resolvida por nome, versão, parâmetros e política numérica. Reutilizar regras financeiras da Sprint 09, explicitando a versão herdada de cada política. Registrar dados, configuração, código/assets e versão Python pelo mecanismo atual. Incluir módulos novos no hash de código. Caminho de saída e hora de execução continuam fora da identidade lógica. Mudança de estratégia, versão ou parâmetro deve alterar a identidade.

`--analise` é redundante no schema 5 e não muda sua identidade. A API impede desativar a análise desse modo. Mudanças no código podem alterar IDs dos cenários antigos. Comparações de regressão devem verificar os valores/eventos financeiros e temporais, considerando as regras existentes de identidade.

## 6. Fixtures e cálculos manuais obrigatórios

### 6.1. Fixture comum

Criar `data/fixtures/sprint10-candles.json`, envelope `schema_version: 1`, com sete candles fechados `FICTICIA/BTCUSDT/1m`, de 01/01/2026 12:00 a 12:07 UTC. Para cada candle, open=high=low=close igual ao preço da tabela e volume base `"1"`. Datas e decimais seguem o contrato atual. A abertura seguinte pode ter gap em relação ao fechamento anterior.

Os resultados abaixo são expectativas matemáticas desta especificação. A implementação deverá registrar os valores efetivamente observados.

| Fechamento número | Preço USDT/BTC | SMA 2 | SMA 3 | EMA 2 | EMA 3 | RSI 2 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 100000 | null | null | null | null | null |
| 2 | 90000 | 95000 | null | 95000 | null | null |
| 3 | 80000 | 85000 | 90000 | 85000 | 90000 | 0 |
| 4 | 100000 | 90000 | 90000 | 95000 | 95000 | 200/3 |
| 5 | 120000 | 110000 | 100000 | 335000/3 | 107500 | 600/7 |
| 6 | 100000 | 110000 | 320000/3 | 935000/9 | 103750 | 40 |
| 7 | 80000 | 90000 | 100000 | 2375000/27 | 91875 | 600/31 |

SMA e EMA geram BUY no fechamento 5 e SELL no fechamento 7. O BUY preenche na abertura do candle 6 a 100000, com quantidade 0.000166 BTC. O SELL final fica não executado, gerando código 2. A posição termina aberta, caixa 983.4 USDT, BTC 0.000166 e patrimônio bruto 996.68 USDT pelo último close de 80000. O stop absoluto é 60000 e o alvo 228000, definidos na avaliação do fechamento 5. A perda planejada na aprovação é 9.96 USDT e, na revalidação, 6.64 USDT. A liberação final de reservas segue a Sprint 09 sem liquidar o ativo.

RSI gera BUY no fechamento 4 e SELL no fechamento 6. As aberturas seguintes elegíveis são 5 e 7, a 120000 e 80000, sujeitas à aprovação e revalidação. Na aprovação, orçamento 10 USDT, stop 50000 e quantidade 0.0002 BTC. Na abertura seguinte, a perda planejada seria 14 USDT, excedendo o orçamento. Portanto o BUY é rejeitado na revalidação, sem fill ou taxa. O SELL posterior é rejeitado por ausência de ativo. O resultado financeiro é caixa 1000 USDT e BTC zero, com código 2. Esse caso verifica a integração entre estratégia e revalidação, independentemente dos sinais matemáticos.

### 6.2. Variante RSI com operação encerrada

Para uma demonstração RSI com fills, criar uma segunda fixture `data/fixtures/sprint10-candles-rsi.json` com os mesmos horários/fechamentos/volumes da comum. Fixar open no fechamento anterior, high=max(open,close) e low=min(open,close), usando 100000 como primeira abertura. Executar essa fixture com `experiments/sprint10-rsi.json`. O BUY preenche na abertura 5 a 100000, q=0.0002 BTC, desembolso 20 USDT. O SELL preenche na abertura 7 a 100000, recebimento 20 USDT. Caixa final 1000, BTC zero, taxas zero, lucro zero e código 0. Stop 50000 e alvo 190000 ficam sem toque.

### 6.3. Estabilidade do aquecimento

Comparar cada indicador recursivo em um mesmo sufixo temporal usando inicializações com quantidades diferentes de histórico anterior, por exemplo 0, 10 e 50 candles anteriores ao sufixo, em fixture determinística identificada. Calcular diferenças absolutas nos indicadores e listar divergências de sinais por timestamp. Comparar somente pontos onde ambos estão prontos, registrando pontos não comparáveis.

Esse experimento deve apenas calcular indicadores, sem misturar resultados financeiros de carteiras com horizontes diferentes. EMA/RSI dependem da semente e podem divergir mesmo depois da prontidão mínima. Registrar as diferenças observadas e a influência nos sinais. Para SMA, verificar igualdade depois de haver histórico comum suficiente para média atual e anterior. O histórico adicional sempre antecede o sufixo. Repetir cada inicialização deve reproduzir seus próprios valores exatos.

## 7. Integração e relatórios

Usar o mesmo núcleo de risco, ledger, reservas, proteção e execução para as três estratégias. Stop/alvo partem da avaliação do sinal e são preservados na revalidação, conforme a Sprint 09. Quantidade aprovada e filtros continuam verificáveis por entrada. Em cenários com custos, manter taxas e slippage adverso nos cálculos existentes, cobrando cada efeito uma única vez.

O schema 5 gera os onze artefatos correspondentes ao modo de risco atual, com metadados da estratégia e avaliações suficientes para auditoria. Preservar os contratos CSV financeiros e documentar extensões necessárias. Markdown e HTML exibem nome/versão, parâmetros, aquecimento, motivos, risco e resultado. Adaptar gráficos com nomes e unidades corretos para SMA, EMA e RSI, incluindo RSI em escala de 0 a 100 e limiares. Verificar modo sem JavaScript, escaping, tela estreita e impressão, mantendo assets offline.

Comparar execuções isoladas numa tabela documental com capital inicial, período/cobertura, custos, posição final, retorno, drawdown, operações e rejeições. Cada linha corresponde a uma carteira independente. A comparação não escolhe automaticamente uma estratégia vencedora. Benchmarks seguem o mesmo horizonte e regras existentes, com carteira isolada.

## 8. Entregáveis e validação

Entregar implementação do contrato/registro e estratégias, integração com parser/API/CLI/relatórios, fixtures e configurações das seções 5 e 6, testes de comportamento, README atualizado e os documentos abaixo.

- `docs/estrategias/sma.md`, `ema.md` e `rsi.md` com fórmulas, parâmetros, versão, semente, aquecimento, igualdade, exemplos e limitações.
- `docs/sprint10-glossario.md` com conceitos e unidades.
- `docs/sprint10-validacao.md` com ambiente, comandos, códigos, esperado/observado, exemplos financeiros, estabilidade do aquecimento, inspeção visual e pendências.

A CLI continua usando `executar --dados --config --saida --formato`. Os exemplos abaixo são receitas futuras a validar na raiz do repositório, com ambiente isolado preparado conforme o README. Se `.venv` já existir, usar seu Python. Registrar a versão concreta e não instalar dependências sem necessidade identificada.

```bash
python --version
python -m unittest discover -s tests -v
python -m replayquant --help
python -m replayquant executar --help
python -m replayquant demonstrar --formato json
python -m replayquant demonstrar --risco --estrategia sma --formato json
```

Após implementar, usar diretórios novos e registrar cada código de saída individualmente. Os três primeiros exemplos da fixture comum devem retornar 2 pelos motivos da seção 6. O último deve retornar 0.

```bash
sprint10_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint10-candles.json --config experiments/sprint10-sma.json --saida "$sprint10_dir/sma" --formato html > "$sprint10_dir/sma.html"
python -m replayquant executar --dados data/fixtures/sprint10-candles.json --config experiments/sprint10-ema.json --saida "$sprint10_dir/ema" --formato html > "$sprint10_dir/ema.html"
python -m replayquant executar --dados data/fixtures/sprint10-candles.json --config experiments/sprint10-rsi.json --saida "$sprint10_dir/rsi" --formato html > "$sprint10_dir/rsi.html"
python -m replayquant executar --dados data/fixtures/sprint10-candles-rsi.json --config experiments/sprint10-rsi.json --saida "$sprint10_dir/rsi-fechado" --formato html > "$sprint10_dir/rsi-fechado.html"
python -m unittest discover -s tests -v
node --check replayquant/assets/chart.js
git diff --check
```

Repetir cada estratégia em outro diretório e comparar os onze artefatos por bytes. O HTML é redirecionado para arquivo separado do diretório de artefatos. Registrar retorno 2 esperado como comportamento verificado, distinguindo-o de uma falha inesperada. Testar todos os formatos e a redundância de `--analise` no modo novo.

## 9. Critérios de aceite

1. Trocar somente a estratégia troca indicador/sinais, mantendo o núcleo financeiro e suas políticas verificáveis. Nome/versão e parâmetros são rastreáveis.
2. Valores exatos, aquecimento e cruzamentos conferem com a seção 6. EMA com janela 1, RSI com período 1, sequência plana, somente altas/baixas, limiares e igualdade possuem cobertura.
3. Uma diferença menor que a precisão decimal exibida ainda decide corretamente. Contexto decimal externo não altera cálculos nem é modificado.
4. Alterar o futuro não altera avaliações, sinais, decisões, reservas ou fills anteriores. Replay incremental e arquivo geram os mesmos resultados no mesmo prefixo.
5. Repetição de candle não repete recorrência ou sinal. Conflito, evento fora de ordem e falha de preparação preservam o estado aceito.
6. Pendências, rejeição por risco/caixa/exposição/mínimos, cancelamento, gaps e saída protetiva usam o fluxo existente também para EMA/RSI. Preservar os testes de prioridade, ambiguidade e proteção do candle de entrada.
7. Sessões intercaladas são independentes. Registro duplicado ou estratégia desconhecida falha antes de qualquer operação financeira.
8. Schemas legados, demonstrações e resultados financeiros das fixtures existentes passam nas regressões. Conferir também o exemplo SMA expandido equivalente entre Sprint 07 e Sprint 09.
9. Reservas, ledger, trades, curva, métricas e benchmarks reconciliam. A fixture RSI fechada confirma lucro zero com duas execuções. A fixture comum confirma rejeição e posição aberta conforme cada estratégia.
10. Há investigação reproduzível de estabilidade do aquecimento e documentação individual das três estratégias. Sua conclusão registra diferenças e sinais observados.
11. Todos os formatos apresentam identidade, unidades e indisponibilidade corretamente. HTML offline tem verificação visual e de execução JavaScript registrada.
12. Roteiro separa esperado de observado e informa comandos realmente executados, limitações e pendências. Lucratividade não é condição de aceite.

## 10. Prompt autossuficiente de execução

O bloco abaixo referencia contratos versionados disponíveis no repositório e contém a instrução de implementação da etapa.

```text
Implemente a Sprint 10 — Estratégias modulares do ReplayQuant no diretório
/home/cams7/Dev/Cripto_Tests/replayquant. Evolua o projeto existente até concluir
código, testes, exemplos e documentação desta etapa.

Inspecione git status, AGENTS.md aplicáveis, HEAD, código e testes. A referência
consultada na especificação é 92eb2dd. Preserve alterações existentes e posteriores.
Leia integralmente docs/sprint10.md, seções 1 a 9, docs/planejamento.md e os contratos
das Sprints 06 a 09 com seus registros de validação. Verifique a suíte e as
demonstrações de entrada da seção 8. Registre lacunas de pré-requisito antes de
trabalho dependente. Use Python >=3.11, ambiente isolado, biblioteca padrão e unittest.

Implemente um contrato incremental de estratégia, avaliações explicativas e registro
local pelos pares SMA_CROSS/1, EMA_CROSS/1 e RSI_REVERSION/1. Crie estado por sessão.
Reutilize o motor financeiro, risco, execução, reservas e ledger atuais. Preserve
API e configurações legadas. Valide nome, versão, parâmetros, tipos e faixas tanto
no JSON estrito como pela API, incluindo rejeição de booleanos como números.

Implemente exatamente as fórmulas, sementes e regras da seção 4. SMA/EMA usam
cruzamento com igualdade anterior permitida e desigualdade atual estrita. EMA usa
alpha=2/(N+1) e semente SMA de N fechamentos. RSI usa médias iniciais de N variações,
suavização de Wilder e RSI=100*ganho_médio/(ganho_médio+perda_média), com RSI=50
quando ambos são zero. BUY ao cruzar oversold para cima e SELL ao cruzar overbought
para baixo. SMA/EMA exigem longa+1 fechamentos para sinal e RSI exige período+2.
Use razões exatas na recorrência/comparação e Decimal na contabilidade. Apresentação
arredondada não decide sinais. Registre valores anteriores/atuais, prontidão e motivos.

Introduza schema 5 mode STRATEGY com análise e risco obrigatórios, seguindo o JSON
completo da seção 5. Nome/versão/parâmetros e políticas compõem a identidade. Preserve
schemas 1/2/4 e saída 3. --analise é redundante no modo novo. Integre a seleção pela
CLI executar existente, pela API incremental e pela geração dos onze artefatos do
modo de risco, com schema e metadados novos documentados.

Implemente as fixtures e configurações das seções 5 e 6. Confira manualmente a tabela
exata de indicadores. Na fixture comum, SMA/EMA têm BUY no fechamento 5, fill a 100000
com q=0.000166 e SELL final não executado, caixa 983.4, BTC 0.000166, patrimônio
996.68 e código 2. RSI sinaliza BUY no fechamento 4 e SELL no 6, mas rejeita a compra
na revalidação por risco, mantendo caixa 1000 e BTC zero, código 2. Na fixture RSI com aberturas no fechamento anterior, valide os dois fills a 100000, q=0.0002, lucro zero, caixa 1000 e código 0.

Preserve causalidade, ordem dos eventos, revalidação e proteção da Sprint 09.
A estratégia recebe somente candles fechados já liberados. Duplicatas não atualizam
indicadores outra vez. Conflitos e falhas preservam o estado aceito. Teste prefixos,
lacunas, pendência final, igualdade, sequências planas, limites, rejeições e sessões
intercaladas. Compare arquivo com API incremental e repetições com artefatos iguais.
Execute a investigação de estabilidade com históricos anteriores diferentes da
seção 6.3, exportando diferenças de valores e sinais em sufixo comum.

Adapte Markdown/HTML e gráficos às três estratégias, com nomes/unidades/limiares,
prontidão e motivos. Preserve assets, licenças, funcionamento offline, escaping e
alternativa sem JavaScript. Verifique tela estreita, impressão e erros JavaScript.
Atualize README. Crie docs/estrategias/sma.md, ema.md e rsi.md,
docs/sprint10-glossario.md e docs/sprint10-validacao.md. A comparação documental
mostra carteiras independentes, custos, risco, amostra e cobertura.

Execute e registre os comandos da seção 8, cada código individualmente, formatos,
comparação dos onze artefatos e regressões das Sprints 06 a 09. Inclua o cenário SMA
expandido equivalente, sem exigir hashes antigos após alterações do código. Corrija
as falhas encontradas dentro do escopo. Use os doze critérios da seção 9 para revisar
a entrega. Não antecipe multipar, carteira compartilhada, seleção automática,
otimização, dados reais ou negociação conectada.

No registro final, informe arquivos alterados, ambiente, comandos efetivamente
executados, esperado/observado, limitações e pendências. Testes ainda não executados
permanecem identificados como pendentes. Conclua a implementação e sua validação.
```
