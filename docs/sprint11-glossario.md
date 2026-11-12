# Glossário da Sprint 11

| Termo | Significado no ReplayQuant |
| --- | --- |
| Instrumento | Origem, símbolo, moedas e intervalos autorizados no catálogo |
| Moeda base | Ativo negociado, como BTC ou ETH, usado em quantidades e volume |
| Moeda de cotação | USDT, usada em preços, caixa, taxas e resultados |
| Catálogo | Snapshot imutável de instrumentos, filtros, disponibilidade e hipóteses de regras |
| Chave de instrumento | Par `(source, symbol)`, único no catálogo |
| Disponibilidade | Intervalo `[available_from, available_until)` com fim opcional |
| Janela solicitada | Intervalo `[start, end)` declarado para a execução |
| Candle elegível | Candle inteiro contido na janela e na disponibilidade do instrumento |
| Listagem tardia | Disponibilidade começa depois do início solicitado |
| Fim de disponibilidade | Limite exclusivo para novas aberturas executáveis |
| Resolução no fechamento | Saída OHLC com horário modelado no fim de um candle válido, inclusive na fronteira final |
| Step | Incremento de quantidade na moeda base |
| Nocional mínimo | Valor mínimo da ordem em USDT |
| SYNTHETIC_ASSUMPTION | Regras fictícias declaradas para a demonstração |
| CURRENT_RULES_ASSUMED_FOR_PERIOD | Hipótese de aplicar regras atuais a outro período |
| rules_as_of | Data de referência declarada das regras, sem comprovação de disponibilidade histórica |
| Cobertura FULL | Todos os candles da janela solicitada foram aceitos |
| Cobertura PARTIAL | Há um prefixo ou recorte aceito menor que a janela solicitada |
| Cobertura NONE | Nenhum candle foi aceito |
| UNAVAILABLE | Combinação sem candles elegíveis, com métricas de desempenho nulas e motivo |
| INSTRUMENT_UNAVAILABLE | Abertura fora da disponibilidade ou pendência encerrada por esse limite |
| AssetBalance | Saldo schema 6 com `cash` e `asset_quantity`, sem campo público `btc` |
| BUY_HOLD_ASSET | Benchmark comprado no ativo base resolvido, com capital próprio |
| Matriz independente | Produto estratégia × dataset, com uma sessão e capital por combinação |
| Identidade lógica | Hash da composição canônica dos filhos e de suas identidades por conteúdo |
| Proveniência da receita | Hash dos bytes originais, que pode mudar ao reordenar listas equivalentes |
| Grupo de ranking | Execuções completas com capital, cotação, custos, risco e horizonte comparáveis |
| Empate exato | Retornos racionais iguais recebem a mesma posição, sem arredondamento decisório |
| INCOMPLETE | Marcador de gravação iniciada e ainda não concluída |

Consulte [Sprint 11](sprint11.md) e [validação](sprint11-validacao.md).
