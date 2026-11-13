# Dados históricos locais — Sprint 13

Origem: Binance Vision / Binance Public Data, mercado Spot. Aquisição explícita em 13/11/2026, para estudo educacional local. Os oito minutos usados pelo motor são recortados desses quatro arquivos completos. Nenhum valor foi inventado ou ajustado para obter lucro.

- [Documentação da fonte](https://github.com/binance/binance-public-data).
- [Termos específicos dos datasets](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md), consultados em 13/11/2026.
- O recibo `entrada/acquisition.json` conserva URLs, data UTC, hashes e tamanhos. Os arquivos `.CHECKSUM` são os originais recebidos.
- A licença dos scripts da fonte não substitui as condições dos datasets. Dados e derivados mantêm atribuição à Binance Vision e referência às condições específicas da fonte; não se afirma patrocínio ou endosso.

| ZIP original | Bytes | SHA-256 verificado |
| --- | --- | --- |
| BTCUSDT-1m-2024-12-31.zip | 71638 | 756551b6eb4f0a0173af3333762e6c95d08c7503bb3b7b79807e10a02575a4af |
| BTCUSDT-1m-2025-01-01.zip | 69062 | 10a12909f1b0e3fcc6b7f502e5ea9be5d1ba3455dd8ab16cc61c8650640ba7c0 |
| ETHUSDT-1m-2024-12-31.zip | 67432 | 70ae988d84bb7ad0692dccbb126dec26b8a388fbc8cdd11bda06cbfe40837cf6 |
| ETHUSDT-1m-2025-01-01.zip | 66406 | 26cc71cf7a2bd0232cf0e8aaaf529fc6674ba20059028023eb346232ee4dbf91 |

O diretório `entrada` permite importar offline em SQLite novo usando `experiments/sprint13-importacao-real.json`. O download não é necessário para repetir a validação local. Os dados não comprovam universo histórico completo; filtros e custos usados são hipóteses do cenário. As verificações se referem aos bytes registrados, não a futuras revisões do acervo.
