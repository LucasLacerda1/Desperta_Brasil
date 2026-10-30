# Desperta Brasil — ajuste do banco para o sistema real (Fase 1.5)

> Para o Claude Code. Coloque este arquivo em `docs/AJUSTE_BANCO_SISTEMA.md` e peça: "Leia docs/AJUSTE_BANCO_SISTEMA.md e execute".
> Escrito em 30/10/2026, depois do relatório da Fase 1. Faça isto **antes da Fase 2 (coletor)**.

## 0. Por que este ajuste existe

O modelo relacional do trabalho (32 tabelas) é o **modelo lógico**: diz quais dados o portal guarda e como eles se ligam. Um sistema que sincroniza todo dia com a API da Câmara e serve um portal precisa também de uma **camada física**: colunas de controle, índices para as consultas reais, configuração do SQLite e migrações. Isso não aparece no diagrama, mas sem isso o coletor não sabe o que mudou, a busca fica lenta e o esquema não pode evoluir com segurança.

Regras deste ajuste:
- **Continua com 32 tabelas e 42 FKs.** Nenhuma tabela nova, nenhuma tabela ou coluna do modelo lógico removida ou renomeada.
- O que entra é **técnico**: colunas de controle, índices, uma restrição de unicidade, padrões (defaults), PRAGMAs, convenção de nomes, migrações e uma tabela virtual de busca (FTS5), que não conta como tabela do modelo, como o índice do sqlite-vec.
- Siga o padrão TaskFlow do `CLAUDE.md` (seção 3) em tudo.
- O banco atual não tem dados reais: pode ser apagado e recriado.

Resumo do que muda:

| # | Mudança | Por quê |
|---|---|---|
| 1 | Convenção de nomes de restrições + Flask-Migrate (Alembic) com `render_as_batch` | O SQLite só altera tabelas recriando-as; sem nomes fixos o Alembic não consegue mudar restrições. O esquema vai mudar (ex.: ajustes de `nullable` depois da carga de validação) |
| 2 | SQLite em modo WAL, `busy_timeout` e `synchronous=NORMAL` | O coletor grava em segundo plano enquanto a API lê e grava (visualizações, visitantes). Sem WAL, aparece `database is locked` |
| 3 | Colunas de sincronização nas tabelas da API | Saber quando cada registro entrou, quando mudou de verdade e quando foi visto pela última vez na API. Alimenta `itens_novos`/`itens_atualizados`, o RAG e a remoção de vínculos que sumiram |
| 4 | Controle de sub-recursos (`filhos_sincronizados_em`) | Várias tabelas vêm de chamadas extras (`/autores`, `/votos`, `/pauta`…). O coletor precisa saber o que ainda está pendente ou desatualizado |
| 5 | Campos novos em `coleta` | Coleta incremental ("desde a última janela concluída"), aviso de dados desatualizados (RNF05) e diagnóstico de falhas da API |
| 6 | Chave natural em `lideranca` | É a única tabela da API com id gerado pelo banco; sem uma chave natural, cada coleta duplicaria as lideranças |
| 7 | Índices para as consultas do portal e do coletor | Página principal em menos de 2 s (RNF01), páginas de proposição, votação e deputado, filtros por data |
| 8 | Busca de texto com FTS5 em `noticia` | Busca por palavras (RF12) sem `LIKE '%...%'`, ignorando acentos |
| 9 | Padrões que faltam (`tema.icone`) e regras de normalização | O coletor não consegue inserir `tema` porque `icone` é obrigatório e não vem da API |
| 10 | Regra de fuso horário | A API manda horário de Brasília sem fuso; o SQLite grava `now()` em UTC. Sem regra, as datas se misturam |

---

## 1. Convenção de nomes e migrações

Em `desperta/ext/db/__init__.py`:

```python
from sqlalchemy import MetaData

# ----------------------------------------------------------
# Nomes fixos para indices e restricoes (necessario para o Alembic)
# ----------------------------------------------------------
CONVENCAO_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

db = SQLAlchemy(metadata=MetaData(naming_convention=CONVENCAO_NOMES))
migrate = Migrate(render_as_batch=True)
```

- Os `CheckConstraint` passam a ter só o nome do campo (`name="status"`), porque a convenção já acrescenta `ck_<tabela>_`. O nome final continua `ck_noticia_status`.
- `UniqueConstraint` com nome explícito (`uq_trecho_rag_tipo_ref_parte_modelo`) pode ficar como está.
- Depois de aplicar **todas** as mudanças deste documento: apagar `instance/desperta.db`, rodar `flask db init`, `flask db migrate -m "esquema inicial"`, revisar o arquivo gerado e rodar `flask db upgrade`.
- O FTS5 (seção 8) não é detectado pelo autogenerate: acrescente-o à mão na migração inicial com `op.execute(...)` no `upgrade()` e o `DROP TRIGGER`/`DROP TABLE noticia_fts` correspondente no `downgrade()`. No `env.py`, use `include_object` para o autogenerate ignorar `noticia_fts*`.
- `flask init-db` continua existindo para desenvolvimento e testes, mas passa a criar também o FTS5. Em produção vale só `flask db upgrade`.
- Nova tarefa Invoke: `invoke migrate` (`flask --app app.py db upgrade`).

## 2. Configuração do SQLite

Acrescentar ao listener que já liga `foreign_keys`:

```python
cursor.execute("PRAGMA foreign_keys=ON")
cursor.execute("PRAGMA journal_mode=WAL")
cursor.execute("PRAGMA busy_timeout=5000")
cursor.execute("PRAGMA synchronous=NORMAL")
```

- WAL deixa leitores e um escritor trabalharem ao mesmo tempo. Em `:memory:` o SQLite ignora o WAL, e os testes continuam funcionando.
- `.gitignore`: acrescentar `*.db-wal` e `*.db-shm`.
- Em `Config`: `SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}`.

## 3. Colunas de sincronização nas tabelas da API

Criar `desperta/ext/db/mixins.py` com dois mixins (comentários no estilo TaskFlow):

```python
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from desperta.ext.db import db


# === SincronizacaoMixin (registro principal vindo da API) ===
class SincronizacaoMixin:
    # quando o registro entrou no banco
    criado_em: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now())
    # quando o conteudo mudou de verdade (hash diferente); o coletor preenche
    atualizado_em: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now())
    # ultima vez que o registro apareceu numa resposta da API
    sincronizado_em: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now(), index=True)
    # SHA-256 dos campos gravados, para saber se algo mudou
    hash_origem: Mapped[str] = mapped_column(db.String(64), nullable=False)


# === VinculoSincronizadoMixin (linha filha ou associativa vinda da API) ===
class VinculoSincronizadoMixin:
    sincronizado_em: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now())
```

**Tabelas principais (11) recebem `SincronizacaoMixin`:** proposicao, votacao, deputado, partido, orgao, evento, legislatura, tema, lideranca, bloco, frente.
Uso: `class Proposicao(SincronizacaoMixin, db.Model):`.

**Tabelas filhas e associativas (10) recebem `VinculoSincronizadoMixin`:** proposicao_autor, proposicao_tema, tramitacao, voto, orientacao, votacao_proposicao, deputado_orgao, bloco_partido, frente_membro, pauta_item.

Regras (o coletor da Fase 2 usa, mas o comportamento fica documentado aqui):
- `atualizado_em` **não** usa `onupdate`: só muda quando `hash_origem` muda. Se usasse `onupdate`, marcar `sincronizado_em` mudaria também `atualizado_em`.
- `hash_origem` = SHA-256 do JSON (chaves ordenadas) **dos valores que vão para as colunas do modelo**, não da resposta inteira da API (que tem `uri` e links que mudam sem importar).
- Linha nova → conta em `itens_novos`. Hash diferente → atualiza colunas e `atualizado_em`, conta em `itens_atualizados`. Hash igual → só `sincronizado_em`.
- **Vínculos que sumiram:** ao sincronizar os filhos de um pai (ex.: membros de um órgão, partidos de um bloco, membros de uma frente, autores e temas de uma proposição), gravar `sincronizado_em = início da coleta` em cada linha recebida e, no fim, apagar as linhas daquele pai com `sincronizado_em` anterior ao início. Assim `bloco_partido` fica só com a composição atual, como o grupo decidiu.
- O RAG (Fase 3) recalcula embeddings só dos registros com `atualizado_em` posterior ao último processamento.

## 4. Controle de sub-recursos

Coluna nova `filhos_sincronizados_em: Mapped[Optional[datetime]] = mapped_column(db.DateTime, index=True)` em 6 tabelas:

| Tabela | Sub-recursos que ela controla |
|---|---|
| proposicao | `/autores`, `/temas`, `/tramitacoes` |
| votacao | `/votacoes/{id}` (proposições afetadas), `/votos`, `/orientacoes` |
| evento | `/eventos/{id}` (url da pauta), `/pauta` |
| orgao | `/orgaos/{id}/membros` |
| bloco | `/blocos/{id}/partidos` |
| frente | `/frentes/{id}` (keywords), `/frentes/{id}/membros` |

Nulo = os filhos ainda não foram buscados. O coletor busca primeiro os pendentes (nulo) e depois os mais antigos. Para eventos, recoletar enquanto `situacao` não for de evento encerrado.

Observação para o coletor: `proposicao` tem campos obrigatórios que só vêm em `/proposicoes/{id}` (`descricao_tipo`, `url_inteiro_teor`, `data_status`, `regime`, `apreciacao`). Grave a proposição só depois de chamar o detalhe; a listagem serve apenas para descobrir ids.

## 5. Campos novos em `coleta`

| Coluna | Tipo | Nulo | Regra |
|---|---|---|---|
| recurso | String(50) | não | nome lógico: `proposicoes`, `votacoes`, `eventos`, `deputados`, `partidos`, `orgaos`, `orgao_membros`, `mesa`, `liderancas`, `blocos`, `frentes`, `temas`, `legislaturas`; index |
| tipo | String(20) | não | `incremental`, `completa`, `detalhe`; `CheckConstraint` |
| data_inicio_ref | Date | sim | início da janela de datas pedida à API |
| data_fim_ref | Date | sim | fim da janela |
| requisicoes | Integer | não | default 0; quantas chamadas HTTP |
| erros_http | Integer | não | default 0; respostas 429/5xx, inclusive as que deram certo depois de nova tentativa |

Índice composto `ix_coleta_recurso_status_finalizado` em (`recurso`, `status`, `finalizado_em`).

Para que servem:
- **Coleta incremental:** a próxima janela de um recurso começa na `data_fim_ref` da última coleta `ok` daquele recurso (com 1 dia de sobreposição). Votações: janelas dentro do mesmo ano, como a API exige.
- **RNF05:** "dados atualizados até" = maior `finalizado_em` com `status = 'ok'`. Criar em `desperta/sistema/services.py` a função `ultima_coleta_concluida(recurso=None)`.

## 6. Chave natural em `lideranca`

```python
__table_args__ = (
    UniqueConstraint(
        "deputado_id", "bancada_nome", "titulo", "data_inicio",
        name="uq_lideranca_deputado_bancada_titulo_inicio"
    ),
)
```

O `id` continua gerado pelo banco, mas o upsert usa essa chave. As outras 20 tabelas da API já têm o id da API ou uma PK composta natural.

## 7. Índices

Princípio: índice para cada filtro ou ordenação que a API do portal ou o coletor vão fazer. O SQLite usa o começo de uma PK composta, mas não o segundo campo sozinho.

**Segundo campo das PKs compostas** (consulta "pelo outro lado"):

| Tabela | Índice em | Consulta |
|---|---|---|
| proposicao_tema | cod_tema | proposições de um tema |
| voto | deputado_id | votos de um deputado |
| deputado_orgao | orgao_id | membros de um órgão |
| bloco_partido | partido_id | blocos de um partido |
| frente_membro | deputado_id | frentes de um deputado |
| votacao_proposicao | proposicao_id | votações que afetaram uma proposição |
| visitante_tema | cod_tema | (relatórios por tema) |
| geracao_trecho | trecho_id | gerações que usaram um trecho |

**Compostos e simples:**

| Tabela | Índice | Consulta |
|---|---|---|
| noticia | (status, publicado_em) | página principal e listas: só publicadas, mais recentes primeiro |
| noticia | (cod_tema, status, publicado_em) | página do tema |
| noticia_fonte | (tipo, ref_id) | "notícias sobre esta proposição/votação" |
| noticia_revisao | (noticia_id, data_hora) | histórico e "quem publicou" |
| proposicao | (sigla_tipo, numero, ano) | busca por "PL 1234/2024" (não único) |
| tramitacao | (proposicao_id, data_hora) | andamento em ordem e última tramitação (órgão atual) |
| tramitacao | data_hora | tramitações recentes (RF08) |
| votacao | (proposicao_id, data) | votações de uma proposição |
| votacao | (orgao_id, data) | votações do Plenário por período |
| votacao | data_hora_registro | ordem padrão da API |
| evento | (orgao_id, data_hora_inicio) | agenda de um órgão |
| evento | situacao | eventos ainda não encerrados (recoleta) |
| deputado | (id_legislatura, sigla_partido) | bancadas da legislatura |
| deputado | sigla_uf | deputados por estado |
| lideranca | (bancada_nome, data_inicio) | líderes de uma bancada |
| log_sistema | (modulo, data_hora) | tela de log por módulo |
| log_sistema | nivel | filtro de erros |
| geracao_ia | (status, criado_em) | gerações com erro |
| visitante | ultimo_acesso | tarefa LGPD (12 meses) |
| trecho_rag | hash_texto | conferir se o texto mudou |

Índices simples ficam com `index=True` na coluna; compostos em `__table_args__` com `db.Index("ix_<tabela>_<campos>", ...)`. Não duplicar índice que a PK ou outro índice composto já cobre pelo primeiro campo (ex.: o índice simples `noticia.status` existente pode sair, porque `(status, publicado_em)` cobre).

## 8. Busca de texto (FTS5) nas notícias

Tabela virtual ligada a `noticia`, sem acento na busca:

```sql
CREATE VIRTUAL TABLE noticia_fts USING fts5(
    titulo, resumo, corpo,
    content='noticia', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER noticia_fts_ai AFTER INSERT ON noticia BEGIN
    INSERT INTO noticia_fts(rowid, titulo, resumo, corpo)
    VALUES (new.id, new.titulo, new.resumo, new.corpo);
END;

CREATE TRIGGER noticia_fts_ad AFTER DELETE ON noticia BEGIN
    INSERT INTO noticia_fts(noticia_fts, rowid, titulo, resumo, corpo)
    VALUES ('delete', old.id, old.titulo, old.resumo, old.corpo);
END;

CREATE TRIGGER noticia_fts_au AFTER UPDATE OF titulo, resumo, corpo ON noticia BEGIN
    INSERT INTO noticia_fts(noticia_fts, rowid, titulo, resumo, corpo)
    VALUES ('delete', old.id, old.titulo, old.resumo, old.corpo);
    INSERT INTO noticia_fts(rowid, titulo, resumo, corpo)
    VALUES (new.id, new.titulo, new.resumo, new.corpo);
END;
```

- O gatilho de UPDATE é só **`OF titulo, resumo, corpo`**: somar `visualizacoes` não reindexa a notícia.
- Guardar o SQL numa função `criar_busca_texto()` em `desperta/ext/db/busca.py`, chamada por `flask init-db`, pela fixture de testes e pela migração inicial.
- Em `desperta/noticias/services.py`, função `buscar_noticias(termo, inicio=None, fim=None, cod_tema=None)`: junta `noticia_fts MATCH :termo` com `noticia` e devolve só `status = 'publicada'`, ordenado por relevância (`bm25`) e depois `publicado_em`. Escapar o termo do usuário (aspas) para não quebrar a sintaxe do MATCH.
- A tabela virtual não é modelo SQLAlchemy e não entra na contagem das 32.

## 9. Padrões e normalização

- `tema.icone`: `server_default="article"` (ícone genérico do Material Symbols). Criar em `desperta/proposicoes/models.py` a constante `ICONES_TEMA = {cod_tema: "nome_do_icone", ...}`, vazia por enquanto; o coletor usa o mapa e cai no padrão quando o tema não está nele. A equipe preenche o mapa depois.
- `administrador`: coluna nova `atualizado_em` (DateTime, não nulo, `server_default=now`, `onupdate=now`). Em `noticia` **não** há `onupdate` (seção 5.4 do `CLAUDE.md`).
- Normalização (regra do coletor, documentar em `desperta/coletor/__init__.py` quando ele for criado): texto vazio `""` vira `None` em coluna opcional; em coluna obrigatória fica `""`. Ids que vêm como texto (`tema.cod`, `bloco.id`, `idLegislatura` de bloco) são convertidos para `int`.
- `deputado.id_legislatura`: um deputado aparece em várias legislaturas com o mesmo id. O upsert só troca `id_legislatura` (e partido) se a legislatura nova for **maior** que a gravada.

## 10. Fuso horário

- Datas e horas **da API** (`data_hora`, `data_apresentacao`, `data_hora_inicio`, `data_registro`…) ficam como a API manda: **horário de Brasília, sem fuso**.
- Colunas **do portal e técnicas** (`criado_em`, `atualizado_em`, `sincronizado_em`, `publicado_em`, `iniciado_em`, `data_hora` de log e revisão, `ultimo_acesso`…) ficam em **UTC**, que é o que `CURRENT_TIMESTAMP` do SQLite grava. No Python, usar `datetime.now(timezone.utc).replace(tzinfo=None)` ao preencher à mão.
- Na Fase 4, a API do portal devolve datas em ISO 8601 **com fuso**: `-03:00` nas da Câmara e `Z` nas do portal. Escrever essa regra como comentário no topo de `desperta/ext/db/mixins.py`.

---

## 11. O que NÃO fazer neste ajuste

- Não criar tabelas novas (fila de jobs, histórico, payload bruto da API). O banco continua guardando só o que o portal e a IA leem.
- Não afrouxar `nullable` de nenhuma coluna: isso espera a carga de validação da Fase 2.
- Não mudar ids, PKs ou FKs do modelo lógico.
- Não implementar o coletor: aqui só entram as colunas, índices e funções de apoio citadas (`ultima_coleta_concluida`, `buscar_noticias`, `criar_busca_texto`).
- Não criar `to_dict()`/schemas de API: isso é Fase 4.

## 12. Ordem de execução

1. Convenção de nomes e `render_as_batch` (seção 1); renomear os `CheckConstraint`.
2. PRAGMAs e `SQLALCHEMY_ENGINE_OPTIONS` (seção 2).
3. Mixins e colunas de sincronização (seções 3 e 4).
4. `coleta`, `lideranca`, `tema.icone`, `administrador.atualizado_em` (seções 5, 6 e 9).
5. Índices (seção 7).
6. FTS5 e `buscar_noticias` (seção 8); `ultima_coleta_concluida` (seção 5).
7. Atualizar os testes da Fase 1 que contam colunas, índices ou nomes de restrição.
8. Escrever os testes novos (seção 13).
9. Apagar o banco, `flask db init`, `flask db migrate -m "esquema inicial"`, revisar, acrescentar o FTS5 na migração, `flask db upgrade`.
10. `invoke test` e `invoke lint`; mostrar o resultado.
11. Commit: `Banco: camada fisica para sincronizacao com a API (colunas de controle, indices, FTS5, migracoes)`.

## 13. Testes que devem passar no fim

Novos arquivos `tests/test_banco_sistema.py` e `tests/test_migracoes.py`, além dos 126 testes da Fase 1 ajustados.

**Estrutura**
- Continuam **32 tabelas** no `db.metadata` e **42 FKs**; `noticia_fts` existe no banco, mas não no `metadata`.
- Total de colunas = 222 + 67 = **289** (44 de `SincronizacaoMixin` nas 11 tabelas principais, 10 de `VinculoSincronizadoMixin`, 6 de `filhos_sincronizados_em`, 6 em `coleta`, 1 em `administrador`).
- As 11 tabelas principais têm `criado_em`, `atualizado_em`, `sincronizado_em` e `hash_origem`, todas `NOT NULL`; as 10 filhas têm `sincronizado_em`.
- As 6 tabelas da seção 4 têm `filhos_sincronizados_em` opcional e indexado.
- Todo índice e toda restrição têm nome que segue a convenção (`ix_`, `uq_`, `ck_`, `fk_`, `pk_`); nenhum nome gerado automaticamente (`sqlite_autoindex_...` só em PKs e restrições `UNIQUE` é aceitável).
- Cada índice da seção 7 existe, com as colunas na ordem indicada.

**SQLite**
- Num banco em arquivo temporário (`tmp_path`), `PRAGMA journal_mode` devolve `wal`, `PRAGMA busy_timeout` devolve `5000` e `PRAGMA foreign_keys` devolve `1`.

**Sincronização**
- Inserir um registro principal sem informar datas preenche `criado_em`, `atualizado_em` e `sincronizado_em`.
- Atualizar só `sincronizado_em` **não** muda `atualizado_em`.
- `hash_origem` é obrigatório (inserir sem ele dá `IntegrityError`).
- `lideranca`: duas linhas com o mesmo (deputado_id, bancada_nome, titulo, data_inicio) dão `IntegrityError`; com `data_inicio` diferente, são aceitas.
- Upsert do SQLite (`sqlalchemy.dialects.sqlite.insert(...).on_conflict_do_update`) funciona em `proposicao` (pela PK) e em `lideranca` (pela chave natural) sem duplicar.
- Remoção de vínculos: com `bloco_partido` de 3 partidos, marcar 2 com `sincronizado_em` novo e apagar os antigos daquele bloco deixa 2 linhas.

**Coleta**
- `coleta.tipo` fora de `incremental`/`completa`/`detalhe` é barrado pelo `CheckConstraint`.
- `requisicoes` e `erros_http` começam em 0.
- `ultima_coleta_concluida()` ignora coletas com `status` `erro` e `parcial`, devolve a maior `finalizado_em` das `ok`, e filtra por `recurso` quando pedido; devolve `None` sem coletas.

**Padrões**
- Inserir `tema` sem `icone` grava `"article"`.
- `administrador.atualizado_em` muda ao alterar o nome.
- Somar 1 em `noticia.visualizacoes` não muda `alterado_em`.

**Busca (FTS5)**
- `buscar_noticias("saude")` encontra notícia publicada com "Saúde" no título.
- Não devolve notícias em `rascunho`, `em_revisao`, `rejeitada` ou `arquivada`.
- Depois de editar o `corpo`, a palavra nova é encontrada e a antiga não.
- Depois de apagar a notícia, ela some da busca.
- Somar visualizações não dispara o gatilho de reindexação (conferir com `noticia_fts` intacto, por exemplo pelo número de linhas em `noticia_fts_docsize`).
- Termo com aspas ou caracteres especiais (`"PL 1234"`, `saúde*`) não gera erro.
- Filtros `inicio`/`fim` e `cod_tema` restringem o resultado.

**Migrações**
- Num banco em arquivo temporário, `flask db upgrade` cria as 32 tabelas, `noticia_fts` e os 3 gatilhos, e `alembic_version` fica com a revisão inicial.
- Depois do upgrade, `flask db migrate` (autogenerate) **não encontra diferenças** entre os modelos e o banco (rodar via `alembic.autogenerate.compare_metadata` e conferir lista vazia, ignorando `noticia_fts*`).
- `flask db downgrade base` apaga tudo sem erro.

**Qualidade**
- `invoke test` sem falhas e `invoke lint` sem erros.

## 14. Atualizar o `CLAUDE.md` do repositório

Ao terminar, o `CLAUDE.md` do repositório deve ser trocado pela versão nova que o grupo enviar junto com este arquivo (ela já cita este ajuste). Não edite o `CLAUDE.md` por conta própria além disso.
