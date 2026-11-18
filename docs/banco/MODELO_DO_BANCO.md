# Modelo do banco de dados

Gerado a partir do código (`python scripts/banco/gerar_modelo.py`), então vale sempre o que está nos
`models.py`. Banco SQLite com Flask-SQLAlchemy; mudanças no esquema só por migração (Flask-Migrate).

**32 tabelas, 289 colunas e 42 chaves estrangeiras.** As 21 tabelas da API da Câmara usam os mesmos ids da API (reprocessar uma coleta atualiza em vez de duplicar).

Legenda: **PK** chave primária · **FK** chave estrangeira · **Nulo** = a coluna aceita valor vazio.

Diagrama entidade-relacionamento completo: `diagrama-er.svg`, desenhado pelo Graphviz a partir de
`diagrama-er.dot` (`dot -Tsvg diagrama-er.dot -o diagrama-er.svg`).

Classificação das entidades: **forte** (chave primária própria, existe sozinha), **associativa**
(resolve um relacionamento N:N) e **fraca** (só existe ligada à tabela pai; a chave primária inclui a
FK do pai). Nenhuma é abstrata: o modelo não tem generalização/especialização (herança).

`noticia_fonte` e `trecho_rag` não têm FK para as tabelas da Câmara: guardam `tipo` + `ref_id`,
e o back-end confere se o registro existe.

## Proposições (API da Câmara)

### `proposicao` (Proposicao)

Projeto de lei, PEC ou outra proposta.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | INTEGER | não | PK |
| `sigla_tipo` | TEXT | não |  |
| `cod_tipo` | INTEGER | não |  |
| `descricao_tipo` | TEXT | não |  |
| `numero` | INTEGER | não |  |
| `ano` | INTEGER | não | índice |
| `ementa` | TEXT | não |  |
| `ementa_detalhada` | TEXT | sim |  |
| `keywords` | TEXT | sim |  |
| `data_apresentacao` | DATETIME | não | índice |
| `url_inteiro_teor` | TEXT | sim |  |
| `cod_situacao` | INTEGER | sim |  |
| `situacao` | TEXT | sim |  |
| `data_status` | DATETIME | sim |  |
| `regime` | TEXT | sim |  |
| `apreciacao` | TEXT | não |  |
| `filhos_sincronizados_em` | DATETIME | sim | índice |
| `criado_em` | DATETIME | não |  |
| `atualizado_em` | DATETIME | não |  |
| `sincronizado_em` | DATETIME | não | índice |
| `hash_origem` | VARCHAR(64) | não |  |

### `proposicao_autor` (ProposicaoAutor)

Quem assina a proposicao.

Classificação: entidade associativa.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `proposicao_id` | INTEGER | não | PK, FK → `proposicao.id` |
| `ordem` | INTEGER | não | PK |
| `deputado_id` | INTEGER | sim | FK → `deputado.id`, índice |
| `nome` | TEXT | não |  |
| `cod_tipo` | INTEGER | não |  |
| `tipo` | TEXT | não |  |
| `proponente` | BOOLEAN | não |  |
| `sincronizado_em` | DATETIME | não |  |

### `proposicao_tema` (ProposicaoTema)

Temas de cada proposicao.

Classificação: entidade associativa.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `proposicao_id` | INTEGER | não | PK, FK → `proposicao.id` |
| `cod_tema` | INTEGER | não | PK, FK → `tema.cod_tema`, índice |
| `relevancia` | INTEGER | não |  |
| `sincronizado_em` | DATETIME | não |  |

### `tema` (Tema)

Tema oficial, usado como categoria do portal.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `cod_tema` | INTEGER | não | PK |
| `nome` | TEXT | não |  |
| `icone` | TEXT | não |  |
| `criado_em` | DATETIME | não |  |
| `atualizado_em` | DATETIME | não |  |
| `sincronizado_em` | DATETIME | não | índice |
| `hash_origem` | VARCHAR(64) | não |  |

### `tramitacao` (Tramitacao)

Passo do andamento da proposicao.

Classificação: entidade fraca.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `proposicao_id` | INTEGER | não | PK, FK → `proposicao.id` |
| `sequencia` | INTEGER | não | PK |
| `data_hora` | DATETIME | não | índice |
| `orgao_id` | INTEGER | não | FK → `orgao.id`, índice |
| `sigla_orgao` | TEXT | não |  |
| `cod_tipo_tramitacao` | TEXT | não |  |
| `descricao` | TEXT | não |  |
| `cod_situacao` | INTEGER | sim |  |
| `situacao` | TEXT | sim |  |
| `despacho` | TEXT | não |  |
| `regime` | TEXT | sim |  |
| `ambito` | TEXT | não |  |
| `apreciacao` | TEXT | não |  |
| `url` | TEXT | sim |  |
| `sincronizado_em` | DATETIME | não |  |

## Votações (API da Câmara)

### `orientacao` (Orientacao)

Orientacao de partido ou bloco, so no Plenario.

Classificação: entidade fraca.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `votacao_id` | TEXT | não | PK, FK → `votacao.id` |
| `partido_bloco` | TEXT | não | PK |
| `tipo_lideranca` | TEXT | não |  |
| `partido_id` | INTEGER | sim | FK → `partido.id`, índice |
| `orientacao` | TEXT | não |  |
| `sincronizado_em` | DATETIME | não |  |

Restrições: `ck_orientacao_tipo_lideranca`: tipo_lideranca IN ('P', 'B').

### `votacao` (Votacao)

Deliberacao em Plenario ou comissao.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | TEXT | não | PK |
| `data` | DATE | não | índice |
| `data_hora_registro` | DATETIME | não | índice |
| `evento_id` | INTEGER | sim | FK → `evento.id`, índice |
| `orgao_id` | INTEGER | não | FK → `orgao.id` |
| `sigla_orgao` | TEXT | não |  |
| `proposicao_id` | INTEGER | sim | FK → `proposicao.id` |
| `descricao` | TEXT | não |  |
| `aprovacao` | BOOLEAN | sim |  |
| `filhos_sincronizados_em` | DATETIME | sim | índice |
| `criado_em` | DATETIME | não |  |
| `atualizado_em` | DATETIME | não |  |
| `sincronizado_em` | DATETIME | não | índice |
| `hash_origem` | VARCHAR(64) | não |  |

### `votacao_proposicao` (VotacaoProposicao)

Proposicoes afetadas pela votacao.

Classificação: entidade associativa.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `votacao_id` | TEXT | não | PK, FK → `votacao.id` |
| `proposicao_id` | INTEGER | não | PK, FK → `proposicao.id`, índice |
| `sincronizado_em` | DATETIME | não |  |

### `voto` (Voto)

Voto nominal de cada deputado.

Classificação: entidade associativa.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `votacao_id` | TEXT | não | PK, FK → `votacao.id` |
| `deputado_id` | INTEGER | não | PK, FK → `deputado.id`, índice |
| `tipo_voto` | TEXT | sim |  |
| `data_registro` | DATETIME | não |  |
| `sigla_partido` | TEXT | não |  |
| `sincronizado_em` | DATETIME | não |  |

## Parlamentares (API da Câmara)

### `bloco` (Bloco)

Bloco partidario ou federacao.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | INTEGER | não | PK |
| `nome` | TEXT | não |  |
| `federacao` | BOOLEAN | não |  |
| `id_legislatura` | INTEGER | não | FK → `legislatura.id`, índice |
| `filhos_sincronizados_em` | DATETIME | sim | índice |
| `criado_em` | DATETIME | não |  |
| `atualizado_em` | DATETIME | não |  |
| `sincronizado_em` | DATETIME | não | índice |
| `hash_origem` | VARCHAR(64) | não |  |

### `bloco_partido` (BlocoPartido)

Composicao atual do bloco.

Classificação: entidade associativa.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `bloco_id` | INTEGER | não | PK, FK → `bloco.id` |
| `partido_id` | INTEGER | não | PK, FK → `partido.id`, índice |
| `sincronizado_em` | DATETIME | não |  |

### `deputado` (Deputado)

Parlamentar da Camara.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | INTEGER | não | PK |
| `nome` | TEXT | não | índice |
| `sigla_uf` | TEXT | não | índice |
| `sexo` | TEXT | não |  |
| `email` | TEXT | sim |  |
| `url_foto` | TEXT | não |  |
| `id_legislatura` | INTEGER | não | FK → `legislatura.id` |
| `partido_id` | INTEGER | sim | FK → `partido.id`, índice |
| `sigla_partido` | TEXT | não |  |
| `criado_em` | DATETIME | não |  |
| `atualizado_em` | DATETIME | não |  |
| `sincronizado_em` | DATETIME | não | índice |
| `hash_origem` | VARCHAR(64) | não |  |

Restrições: `ck_deputado_sexo`: sexo IN ('M', 'F').

### `frente` (Frente)

Frente parlamentar.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | INTEGER | não | PK |
| `titulo` | TEXT | não |  |
| `id_legislatura` | INTEGER | não | FK → `legislatura.id`, índice |
| `keywords` | TEXT | sim |  |
| `filhos_sincronizados_em` | DATETIME | sim | índice |
| `criado_em` | DATETIME | não |  |
| `atualizado_em` | DATETIME | não |  |
| `sincronizado_em` | DATETIME | não | índice |
| `hash_origem` | VARCHAR(64) | não |  |

### `frente_membro` (FrenteMembro)

Deputado que participa da frente.

Classificação: entidade associativa.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `frente_id` | INTEGER | não | PK, FK → `frente.id` |
| `deputado_id` | INTEGER | não | PK, FK → `deputado.id`, índice |
| `cod_titulo` | TEXT | não |  |
| `titulo` | TEXT | não |  |
| `data_inicio` | DATE | sim |  |
| `data_fim` | DATE | sim |  |
| `sincronizado_em` | DATETIME | não |  |

### `legislatura` (Legislatura)

Periodo de mandato.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | INTEGER | não | PK |
| `data_inicio` | DATE | não |  |
| `data_fim` | DATE | não |  |
| `criado_em` | DATETIME | não |  |
| `atualizado_em` | DATETIME | não |  |
| `sincronizado_em` | DATETIME | não | índice |
| `hash_origem` | VARCHAR(64) | não |  |

### `lideranca` (Lideranca)

Lideres e vice-lideres das bancadas.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | INTEGER | não | PK |
| `deputado_id` | INTEGER | não | FK → `deputado.id`, índice |
| `bancada_nome` | TEXT | não |  |
| `bancada_tipo` | TEXT | não |  |
| `titulo` | TEXT | não |  |
| `data_inicio` | DATE | não |  |
| `data_fim` | DATE | sim |  |
| `criado_em` | DATETIME | não |  |
| `atualizado_em` | DATETIME | não |  |
| `sincronizado_em` | DATETIME | não | índice |
| `hash_origem` | VARCHAR(64) | não |  |

Restrições: `uq_lideranca_deputado_bancada_titulo_inicio`: única (deputado_id, bancada_nome, titulo, data_inicio).

### `partido` (Partido)

Sigla sem UNIQUE: ligacoes sempre pelo id.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | INTEGER | não | PK |
| `sigla` | TEXT | não |  |
| `nome` | TEXT | não |  |
| `url_logo` | TEXT | sim |  |
| `criado_em` | DATETIME | não |  |
| `atualizado_em` | DATETIME | não |  |
| `sincronizado_em` | DATETIME | não | índice |
| `hash_origem` | VARCHAR(64) | não |  |

## Órgãos e eventos (API da Câmara)

### `deputado_orgao` (DeputadoOrgao)

Cargos de deputados em orgaos.

Classificação: entidade associativa.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `deputado_id` | INTEGER | não | PK, FK → `deputado.id` |
| `orgao_id` | INTEGER | não | PK, FK → `orgao.id`, índice |
| `data_inicio` | DATE | não | PK |
| `cod_titulo` | TEXT | não |  |
| `titulo` | TEXT | não |  |
| `data_fim` | DATE | sim |  |
| `sincronizado_em` | DATETIME | não |  |

### `evento` (Evento)

Sessao ou reuniao.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | INTEGER | não | PK |
| `data_hora_inicio` | DATETIME | não | índice |
| `data_hora_fim` | DATETIME | sim |  |
| `situacao` | TEXT | não | índice |
| `descricao_tipo` | TEXT | não |  |
| `descricao` | TEXT | não |  |
| `orgao_id` | INTEGER | não | FK → `orgao.id` |
| `local` | TEXT | sim |  |
| `url_registro` | TEXT | sim |  |
| `url_documento_pauta` | TEXT | sim |  |
| `filhos_sincronizados_em` | DATETIME | sim | índice |
| `criado_em` | DATETIME | não |  |
| `atualizado_em` | DATETIME | não |  |
| `sincronizado_em` | DATETIME | não | índice |
| `hash_origem` | VARCHAR(64) | não |  |

### `orgao` (Orgao)

Plenario, comissoes, Mesa Diretora.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | INTEGER | não | PK |
| `sigla` | TEXT | não |  |
| `nome` | TEXT | não |  |
| `apelido` | TEXT | não |  |
| `cod_tipo_orgao` | INTEGER | não |  |
| `tipo_orgao` | TEXT | não |  |
| `filhos_sincronizados_em` | DATETIME | sim | índice |
| `criado_em` | DATETIME | não |  |
| `atualizado_em` | DATETIME | não |  |
| `sincronizado_em` | DATETIME | não | índice |
| `hash_origem` | VARCHAR(64) | não |  |

### `pauta_item` (PautaItem)

Item da pauta de um evento.

Classificação: entidade fraca.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `evento_id` | INTEGER | não | PK, FK → `evento.id` |
| `ordem` | INTEGER | não | PK |
| `proposicao_id` | INTEGER | sim | FK → `proposicao.id`, índice |
| `proposicao_relacionada_id` | INTEGER | sim |  |
| `relator_id` | INTEGER | sim | FK → `deputado.id`, índice |
| `regime` | TEXT | sim |  |
| `situacao_item` | TEXT | sim |  |
| `topico` | TEXT | sim |  |
| `texto_parecer` | TEXT | sim |  |
| `votacao_id` | TEXT | sim | FK → `votacao.id`, índice |
| `sincronizado_em` | DATETIME | não |  |

## Equipe (portal)

### `administrador` (Administrador)

Membro da equipe.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | INTEGER | não | PK |
| `nome` | VARCHAR(100) | não |  |
| `email` | VARCHAR(254) | não | índice |
| `senha_hash` | VARCHAR(255) | não |  |
| `papel` | VARCHAR(20) | não |  |
| `ativo` | BOOLEAN | não |  |
| `criado_em` | DATETIME | não |  |
| `atualizado_em` | DATETIME | não |  |
| `ultimo_acesso` | DATETIME | sim |  |

Restrições: `ck_administrador_papel`: papel IN ('admin', 'editor').

## Notícias (portal)

### `noticia` (Noticia)

Noticia ou relatorio escrito pela IA ou pela equipe.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | INTEGER | não | PK |
| `titulo` | VARCHAR(200) | não |  |
| `slug` | VARCHAR(220) | não | índice |
| `resumo` | VARCHAR(500) | não |  |
| `corpo` | TEXT | não |  |
| `tipo` | VARCHAR(20) | não |  |
| `origem` | VARCHAR(20) | não |  |
| `cod_tema` | INTEGER | não | FK → `tema.cod_tema` |
| `status` | VARCHAR(20) | não |  |
| `criado_em` | DATETIME | não |  |
| `publicado_em` | DATETIME | sim | índice |
| `alterado_em` | DATETIME | sim |  |
| `visualizacoes` | INTEGER | não |  |

Restrições: `ck_noticia_origem`: origem IN ('ia', 'equipe'); `ck_noticia_status`: status IN ('rascunho', 'em_revisao', 'publicada', 'rejeitada', 'arquivada'); `ck_noticia_tipo`: tipo IN ('noticia', 'relatorio').

### `noticia_fonte` (NoticiaFonte)

Registros da API usados na noticia.

Classificação: entidade fraca.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `noticia_id` | INTEGER | não | PK, FK → `noticia.id` |
| `tipo` | VARCHAR(20) | não | PK |
| `ref_id` | VARCHAR(20) | não | PK |
| `ordem` | INTEGER | não |  |

Restrições: `ck_noticia_fonte_tipo`: tipo IN ('proposicao', 'votacao', 'deputado', 'evento', 'orgao', 'partido').

### `noticia_revisao` (NoticiaRevisao)

Historico de revisao, uma linha por acao.

Classificação: entidade associativa.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | INTEGER | não | PK |
| `noticia_id` | INTEGER | não | FK → `noticia.id` |
| `admin_id` | INTEGER | não | FK → `administrador.id`, índice |
| `acao` | VARCHAR(20) | não |  |
| `comentario` | TEXT | sim |  |
| `data_hora` | DATETIME | não |  |

Restrições: `ck_noticia_revisao_acao`: acao IN ('editou', 'aprovou', 'rejeitou', 'publicou', 'arquivou').

## IA e busca (portal)

### `geracao_ia` (GeracaoIA)

Cada execucao da IA, mesmo com erro.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | INTEGER | não | PK |
| `noticia_id` | INTEGER | sim | FK → `noticia.id`, índice |
| `modelo_geracao` | VARCHAR(100) | não |  |
| `modelo_embedding` | VARCHAR(100) | não |  |
| `consulta` | TEXT | não |  |
| `top_k` | INTEGER | não |  |
| `versao_prompt` | VARCHAR(50) | não |  |
| `entrada` | TEXT | não |  |
| `tokens_entrada` | INTEGER | sim |  |
| `tokens_saida` | INTEGER | sim |  |
| `duracao_ms` | INTEGER | sim |  |
| `status` | VARCHAR(20) | não |  |
| `erro` | TEXT | sim |  |
| `criado_em` | DATETIME | não |  |

Restrições: `ck_geracao_ia_status`: status IN ('ok', 'erro').

### `geracao_trecho` (GeracaoTrecho)

Trechos recuperados em cada geracao.

Classificação: entidade associativa.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `geracao_id` | INTEGER | não | PK, FK → `geracao_ia.id` |
| `trecho_id` | INTEGER | não | PK, FK → `trecho_rag.id`, índice |
| `posicao` | INTEGER | não |  |
| `similaridade` | FLOAT | não |  |

### `trecho_rag` (TrechoRAG)

Pedaco de texto com embedding.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | INTEGER | não | PK |
| `tipo` | VARCHAR(20) | não |  |
| `ref_id` | VARCHAR(20) | não |  |
| `parte` | INTEGER | não |  |
| `texto` | TEXT | não |  |
| `tokens` | INTEGER | não |  |
| `embedding` | BLOB | não |  |
| `modelo_embedding` | VARCHAR(100) | não |  |
| `hash_texto` | VARCHAR(64) | não | índice |
| `criado_em` | DATETIME | não |  |

Restrições: `ck_trecho_rag_tipo`: tipo IN ('proposicao', 'tramitacao', 'votacao', 'evento', 'pauta_item'); `uq_trecho_rag_tipo_ref_parte_modelo`: única (tipo, ref_id, parte, modelo_embedding).

## Sistema (portal)

### `coleta` (Coleta)

Cada chamada do coletor.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | INTEGER | não | PK |
| `recurso` | VARCHAR(50) | não |  |
| `tipo` | VARCHAR(20) | não |  |
| `endpoint` | VARCHAR(255) | não |  |
| `parametros` | TEXT | sim |  |
| `data_inicio_ref` | DATE | sim |  |
| `data_fim_ref` | DATE | sim |  |
| `iniciado_em` | DATETIME | não |  |
| `finalizado_em` | DATETIME | sim |  |
| `total_itens` | INTEGER | não |  |
| `itens_novos` | INTEGER | não |  |
| `itens_atualizados` | INTEGER | não |  |
| `status` | VARCHAR(20) | não |  |
| `mensagem_erro` | TEXT | sim |  |
| `requisicoes` | INTEGER | não |  |
| `erros_http` | INTEGER | não |  |

Restrições: `ck_coleta_status`: status IN ('ok', 'parcial', 'erro'); `ck_coleta_tipo`: tipo IN ('incremental', 'completa', 'detalhe').

### `log_sistema` (LogSistema)

Acoes do coletor, da IA e dos administradores.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | INTEGER | não | PK |
| `data_hora` | DATETIME | não | índice |
| `nivel` | VARCHAR(10) | não | índice |
| `modulo` | VARCHAR(20) | não |  |
| `acao` | VARCHAR(100) | não |  |
| `descricao` | TEXT | não |  |
| `admin_id` | INTEGER | sim | FK → `administrador.id`, índice |
| `coleta_id` | INTEGER | sim | FK → `coleta.id`, índice |
| `entidade` | VARCHAR(50) | sim |  |
| `entidade_id` | VARCHAR(50) | sim |  |

Restrições: `ck_log_sistema_modulo`: modulo IN ('coletor', 'IA', 'admin'); `ck_log_sistema_nivel`: nivel IN ('info', 'aviso', 'erro').

## Visitantes (portal)

### `visitante` (Visitante)

Visitante anonimo, identificado por cookie.

Classificação: entidade forte.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `id` | VARCHAR(36) | não | PK |
| `preferencias` | TEXT | sim |  |
| `consentimento` | BOOLEAN | não |  |
| `criado_em` | DATETIME | não |  |
| `ultimo_acesso` | DATETIME | não | índice |

### `visitante_tema` (VisitanteTema)

Acessos do visitante por tema.

Classificação: entidade associativa.

| Coluna | Tipo | Nulo | Chave |
|---|---|---|---|
| `visitante_id` | VARCHAR(36) | não | PK, FK → `visitante.id` |
| `cod_tema` | INTEGER | não | PK, FK → `tema.cod_tema`, índice |
| `acessos` | INTEGER | não |  |
