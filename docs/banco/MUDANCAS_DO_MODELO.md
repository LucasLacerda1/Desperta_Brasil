# O que mudou no modelo do banco desde o começo

O primeiro modelo relacional do grupo é de 28/10/2026: **30 tabelas** (21 da API da Câmara e 9 do portal),
40 relacionamentos 1:N e 9 N:N. O modelo de hoje, gerado do código em `MODELO_DO_BANCO.md`, tem
**32 tabelas, 289 colunas e 42 chaves estrangeiras** (42 relacionamentos 1:N e 10 N:N).

## Tabelas novas (2)

| Tabela | Por quê |
|---|---|
| `trecho_rag` | Pedaços de texto (proposição, tramitação, votação, evento) com o vetor de cada modelo de linguagem, para a busca da IA. |
| `geracao_trecho` | Quais trechos a busca encontrou em cada escrita de notícia (`geracao_ia`), com a posição e a nota. É a ligação N:N nova. |

## Colunas novas

| Onde | Colunas | Para quê |
|---|---|---|
| Todas as 21 tabelas da API | `sincronizado_em` | Quando o coletor conferiu o registro pela última vez. |
| As 11 tabelas principais da API (proposição, votação, deputado, órgão, evento...) | `criado_em`, `atualizado_em`, `hash_origem` | O hash do que a API mandou decide se a linha precisa ser atualizada (sem regravar o que não mudou). |
| Proposição, votação, evento, órgão, bloco, frente | `filhos_sincronizados_em` | Quando os filhos (autores, votos, pauta...) foram buscados; sem isso, o registro fica pendente para a coleta seguinte. |
| `coleta` | `recurso`, `data_inicio_ref`, `data_fim_ref`, `requisicoes`, `erros_http` | Saber o que cada coleta buscou, em qual período, quantas chamadas fez e quantas falharam. |
| `geracao_ia` | `modelo_geracao`, `modelo_embedding`, `consulta`, `top_k` | Registrar como cada notícia foi escrita: o gerador, o modelo da busca e a consulta usada. |
| `administrador` | `atualizado_em` | Quando o cadastro da pessoa foi editado (o login muda só o `ultimo_acesso`). |

## Colunas que passaram a aceitar vazio (migrações)

A Câmara manda alguns campos em branco, e o banco guarda exatamente o que ela mandou:

| Migração | Colunas | Caso real |
|---|---|---|
| `535ba879b66f` (04/11) | `voto.tipo_voto` | Votação secreta: a API registra só a presença, sem o voto. |
| `f8a2f7162512` (04/11) | `proposicao.regime`, `proposicao.data_status`, `proposicao.url_inteiro_teor`, `tramitacao.regime` | Proposições que a Câmara publica sem esses dados. |

## Índices fora das 32 tabelas

Não fazem parte do modelo lógico e podem ser refeitos a partir das tabelas:

- busca por palavras (FTS5 do SQLite): `noticia_fts`, `trecho_fts` e as versões pela raiz das palavras,
  `noticia_fts_raiz` (migração `19b825043af5`, 15/11) e `trecho_fts_raiz`;
- busca por vetores (sqlite-vec): `vec_trecho` e `vec_trecho_e5`.

## Migrações, em ordem

1. `ac243e1b323f` (30/10): esquema inicial, com as 32 tabelas.
2. `535ba879b66f` (04/11): voto sem tipo (votação secreta).
3. `f8a2f7162512` (04/11): campos que a Câmara deixa vazios ficam opcionais.
4. `19b825043af5` (15/11): índice de busca pela raiz das palavras.
