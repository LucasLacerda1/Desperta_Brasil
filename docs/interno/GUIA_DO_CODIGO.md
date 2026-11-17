# Guia do código do Desperta Brasil

> **Documento interno da equipe** (sai do repositório público quando o site for ao ar). Para o Rhuan e o Caio (e quem entrar no projeto depois). Escrito pelo Claude Code em 17/11/2026, a pedido do Lucas, a partir do código da `main` (commit `d31c654`).
>
> O objetivo é que vocês consigam abrir qualquer arquivo do projeto e saber o que ele faz, por que existe e com quem conversa. O guia vai do geral para o detalhe: primeiro a ideia e o caminho dos dados, depois cada pacote, arquivo por arquivo, com o número da linha das partes importantes. No fim, o **Apêndice A** lista todas as classes e funções do pacote `desperta`, com o link para a linha exata.
>
> As decisões citadas como "25.14", "12.1" etc. são as seções do `CLAUDE.md`, na raiz do repositório, onde o grupo registra cada escolha e o porquê. Quando alguma coisa aqui parecer estranha, o motivo quase sempre está lá.

## Sumário

1. [O projeto em uma página](#1-o-projeto-em-uma-página)
2. [Arquitetura e o caminho dos dados](#2-arquitetura-e-o-caminho-dos-dados)
3. [Como rodar e como trabalhar](#3-como-rodar-e-como-trabalhar)
4. [O padrão TaskFlow e a organização das pastas](#4-o-padrão-taskflow-e-a-organização-das-pastas)
5. [O banco de dados](#5-o-banco-de-dados)
6. [O coletor (dados da Câmara)](#6-o-coletor-dados-da-câmara)
7. [A IA: busca (RAG) e escrita das notícias](#7-a-ia-busca-rag-e-escrita-das-notícias)
8. [As notícias: fila, notícia viva, prioridade, planta e publicação](#8-as-notícias-fila-notícia-viva-prioridade-planta-e-publicação)
9. [Transparência: lacunas da Câmara e situação explicada](#9-transparência-lacunas-da-câmara-e-situação-explicada)
10. [A API REST](#10-a-api-rest)
11. [Login da equipe e segurança](#11-login-da-equipe-e-segurança)
12. [O agendador (as rotinas que rodam sozinhas)](#12-o-agendador-as-rotinas-que-rodam-sozinhas)
13. [Os testes](#13-os-testes)
14. [Os scripts e os estudos](#14-os-scripts-e-os-estudos)
15. [O protótipo do site (front-end)](#15-o-protótipo-do-site-front-end)
16. [O que falta e para onde o projeto vai](#16-o-que-falta-e-para-onde-o-projeto-vai)
17. [Glossário](#17-glossário)
- [Apêndice A: todas as classes e funções, com a linha](#apêndice-a-todas-as-classes-e-funções-com-a-linha)

---

## 1. O projeto em uma página

O **Desperta Brasil** é um portal de notícias sobre a Câmara dos Deputados, escrito para o brasileiro comum. Ele funciona em cinco passos:

1. **Coleta.** De hora em hora, o coletor busca na API de Dados Abertos da Câmara as proposições (projetos de lei, PECs…), as votações, os eventos, os deputados etc., e guarda tudo num banco SQLite, com os mesmos ids da Câmara.
2. **Indexação.** Os textos dos registros viram "trechos", e duas redes neurais (a RoBERTaLexPT e o e5) transformam cada trecho num vetor de 768 números. Isso permite buscar por significado, e não só por palavra.
3. **Escrita.** Para cada fato novo (uma votação, uma mudança de situação, uma proposição nova), o sistema escreve um rascunho de notícia. Hoje quem escreve é o `GeradorFrases`: frases prontas, montadas só com os dados do banco, sem inventar nada.
4. **Revisão ou publicação automática.** O rascunho é conferido contra a **planta da notícia** (a estrutura padrão). Se passar e o sistema confiar nele, pode ser publicado sozinho; se não, vai para a fila da equipe.
5. **Leitura.** O site (Vue 3) lê tudo pela API REST (Flask). O site nunca chama a Câmara nem a IA na hora da visita: o banco funciona como cache.

**Números de 17/11/2026 (banco real):** 12.502 proposições, 190.606 tramitações, 1.818 votações, 7.654 votos, 1.677 deputados, 72.511 trechos indexados (as duas redes neurais), cerca de 1.230 notícias na fila; banco com cerca de 775 MB. O código tem 12.258 linhas no pacote `desperta`, 9.428 linhas de testes (920 testes) e 3.271 linhas de scripts.

**Princípios que explicam muitas escolhas:**

- **Transparência total (22.5).** O banco guarda exatamente o que a API mandou (até o `"."` que a Câmara usa no lugar de "não informado"). O código classifica e explica. Se a Câmara não informou algo, o portal diz isso, com prova.
- **Nunca inventar.** O gerador só usa dados do banco; um número ou um nome que não está no banco não aparece no texto.
- **Tudo open source (18).** Bibliotecas e modelos abertos, sem serviço pago.
- **Nada se perde (25.13).** O coletor grava tudo; o filtro decide só a forma da notícia (notícia própria, atualização ou boletim).

---

## 2. Arquitetura e o caminho dos dados

```
                    API de Dados Abertos da Câmara (REST, JSON)
                                     │
                                     ▼
   ┌───────────────────────── coletor (desperta/coletor) ─────────────────────────┐
   │ cliente HTTP com novas tentativas → um módulo por recurso → upsert pelo id   │
   └───────────────────────────────────┬───────────────────────────────────────────┘
                                       ▼
                     SQLite (instance/desperta.db, 32 tabelas)
                     + FTS5 (busca por palavras) + sqlite-vec (vetores)
                                       │
          ┌────────────────────────────┼─────────────────────────────┐
          ▼                            ▼                             ▼
  indexação (ia/services)      escrita (ia/geracao,           API REST (Flask,
  trechos → RoBERTa e e5       ia/gerador, ia/automatico,     blueprints em /api)
  → trecho_rag + índices       ia/boletim, ia/relatorio)             │
                                       │                             ▼
                                       ▼                     site (Vue 3, branch
                         notícias (noticias/*): notícia       prototipo-front) e,
                         viva, prioridade, planta,            no futuro, o app
                         publicação automática
```

**A ordem de uma rodada do agendador** (`flask coletar agendada <rotina>`, seção 12):

1. Coleta da rotina (horária, diária, semanal ou mensal).
2. Indexação: os trechos novos ou que mudaram ganham vetor nas duas redes neurais.
3. Geração: os fatos novos viram rascunhos (ou atualizações de uma notícia viva).
4. Na diária: os boletins do dia anterior. Na semanal: o relatório da semana.
5. Publicação automática: confere os rascunhos na planta e publica os que passam (se estiver ligada).

Tudo isso roda **sob a mesma trava** (`instance/coletor.lock`), para duas coletas nunca gravarem ao mesmo tempo.

**Por que Flask + API REST + front separado.** É a arquitetura que o professor passou no TaskFlow. O back-end entrega JSON, e qualquer cliente pode usá-lo: o site em Vue hoje, um aplicativo amanhã.

**Por que SQLite.** É um arquivo só, sem servidor, gratuito e muito rápido para leitura. O limite que importa não é o tamanho (o SQLite aguenta terabytes), e sim a escrita: **um processo escrevendo por vez**. Para um portal de notícias isso serve bem, porque os visitantes só leem e quem escreve é o coletor, um de cada vez. Com WAL (seção 5.2), leitura e escrita acontecem ao mesmo tempo. O PostgreSQL entra só quando o site precisar de mais de um servidor (decisão 11.1).

---

## 3. Como rodar e como trabalhar

### 3.1 Instalar

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install torch                  # ou a versão para processador: --index-url https://download.pytorch.org/whl/cpu
pip install invoke
invoke install                     # pip install -e ".[tudo]": dev, testes, IA, visualizador e análises
invoke test                        # pytest com cobertura: 920 testes
```

O `pyproject.toml` declara todas as dependências em grupos (`dev`, `test`, `ia`, `ver`, `analise`; `tudo` junta todos). Regra do projeto (24.3): dependência nova entra num grupo do `pyproject.toml`, nunca num `pip install` avulso.

### 3.2 Comandos do dia a dia

As tarefas do Invoke ficam em [`tasks.py`](../../tasks.py) e chamam os comandos do Flask:

| Invoke | O que faz |
|---|---|
| `invoke run` | sobe a API em `http://localhost:5000` |
| `invoke test` / `lint` / `format` | testes com cobertura / flake8 / Black |
| `invoke initdb`, `invoke migrate` | cria o banco do zero / aplica as migrações |
| `invoke coletar`, `invoke carga-validacao` | coletas à mão |
| `invoke baixar-modelo`, `invoke indexar` | baixa as redes neurais / indexa os trechos |
| `invoke gerar-novos`, `invoke boletins`, `invoke relatorio-semanal` | escreve os rascunhos, os boletins, o relatório |
| `invoke verificar-banco`, `invoke testar-persistencia` | confere o banco (só leitura) / testa gravação numa cópia |
| `invoke ver-banco` | abre o banco no navegador (Datasette, só leitura) |
| `invoke agendar`, `agenda`, `desagendar` | liga, mostra e desliga o agendador (systemd) |

E os comandos do Flask mais usados (`flask --app app.py ...`):

- `flask coletar horaria|diaria|semanal|mensal|agendada <rotina>|relatorio|...` ([`desperta/coletor/cli.py`](../../desperta/coletor/cli.py));
- `flask ia indexar|buscar|gerar|gerar-novos|boletins|relatorio-semanal|publicar-automaticas|...` ([`desperta/ia/cli.py`](../../desperta/ia/cli.py));
- `flask banco verificar|testar-persistencia` ([`desperta/ext/cli/__init__.py`](../../desperta/ext/cli/__init__.py));
- `flask equipe criar-admin|listar` ([`desperta/auth/cli.py`](../../desperta/auth/cli.py));
- `flask db upgrade|migrate|check` (Flask-Migrate).

### 3.3 Configuração

Tudo que muda de máquina para máquina vem de variável de ambiente, lida em [`desperta/config.py`](../../desperta/config.py) com um valor padrão para desenvolvimento (12-Factor). O arquivo `.env` (fora do git) define os valores locais; o `.env.example` mostra todos. As mais importantes:

| Variável | Para quê |
|---|---|
| `DATABASE_URL` | qual banco usar (padrão `sqlite:///desperta.db`, dentro de `instance/`) |
| `SECRET_KEY` | assina o cookie de sessão da equipe |
| `TIPOS_ACOMPANHADOS` | `PL,PLP,PEC,MPV,PDL`: os tipos de proposição que viram notícia |
| `ROBERTA_DIR`, `E5_DIR`, `IA_DISPOSITIVO` | onde estão as redes neurais e se usam a placa de vídeo |
| `RAG_MODELO` | qual rede a escrita usa na busca (`e5`, padrão) |
| `PUBLICACAO_AUTOMATICA` | `ensaio` (padrão), `ligada` ou `desligada` (seção 8.6) |
| `CORS_ORIGINS`, `LIMITE_*`, `LOGIN_*` | segurança da API (seções 10 e 11) |

`TestConfig` (linha 76) troca o banco por um SQLite **em memória**, então os testes nunca tocam no banco real.

### 3.4 Git

A `main` é a versão estável. Cada trabalho é feito numa branch, com commits pequenos em português, e entra na `main` por pull request com merge do Lucas ("Create a merge commit"). Todo commit leva `Co-authored-by` do Caio e do Rhuan (22.8). Nunca vão para o git: `.venv/`, `instance/` (banco, modelos, análises), `.env`, `*.db`.

---

## 4. O padrão TaskFlow e a organização das pastas

O projeto segue o TaskFlow, o exemplo do professor (seção 3 do `CLAUDE.md`). Três ideias:

1. **Application Factory.** Não existe um `app` global. [`create_app()`](../../desperta/__init__.py#L25) cria a aplicação, carrega a configuração, liga as extensões, registra os modelos e registra cada pacote de domínio. Os testes chamam `create_app(TestConfig)` e ganham uma aplicação nova, com banco em memória.
2. **Extensões desacopladas** em `desperta/ext/`: cada uma é criada sem app e ligada depois com `init_app(app)` (banco, CORS, erros, limite, comandos).
3. **Um pacote por domínio**, cada um com `models.py` (tabelas), `services.py` (regras e consultas), `routes.py` (só HTTP) e `__init__.py` (registra o blueprint). **A rota não consulta o banco: chama o service.** É isso que deixa as regras testáveis sem HTTP.

```
desperta/
    __init__.py         create_app(): monta a aplicação
    config.py           Config e TestConfig
    ext/                extensões: db (banco, busca, verificação), api (auxiliares HTTP),
                        erros (erros viram JSON), limite (excesso de requisições), cors, cli
    auth/               equipe: login, sessão, papéis (1 tabela)
    proposicoes/        proposição, autores, temas, tramitações (5 tabelas) + situações explicadas
    votacoes/           votação, voto, orientação, proposições afetadas (4)
    parlamentares/      deputado, partido, legislatura, liderança, bloco, frente (8)
    orgaos/             órgão, cargos, evento, item de pauta (4)
    noticias/           notícia, fontes, revisões (3) + notícia viva, prioridade, planta
    ia/                 geração, trechos do RAG (3) + busca, redes neurais, gerador, boletins
    sistema/            log e coletas (2) + lacunas da Câmara
    visitantes/         visitante e temas lidos (2; as rotas ainda não existem)
    coletor/            o coletor (não é blueprint)
tests/                  920 testes (pytest)
scripts/                agendador, visualizador do banco, estudos e triagens
migrations/             Flask-Migrate (Alembic): 4 migrações
docs/                   documentos do projeto (este guia, a planta da notícia...)
```

**Ordem em `create_app`** ([`desperta/__init__.py`](../../desperta/__init__.py#L25)): `init_db` → `init_cors` → `init_erros` → `init_limite` → `init_cli` → `init_coletor` → `register_models()` → os `init_app` dos domínios → a rota `/api/health`. O `register_models()` ([`ext/db/__init__.py:47`](../../desperta/ext/db/__init__.py#L47)) importa todos os `models.py` **dentro da função** (import tardio): assim todas as tabelas entram no `metadata` sem import circular.

---

## 5. O banco de dados

### 5.1 As 32 tabelas

São 21 tabelas que espelham a API da Câmara e 11 do portal. O desenho é do grupo (seção 5 do `CLAUDE.md`, com o diagrama e o modelo relacional) e não muda sem o grupo concordar.

| Pacote | Tabelas | Observação |
|---|---|---|
| `proposicoes` | `proposicao`, `proposicao_autor`, `proposicao_tema`, `tema`, `tramitacao` | `tramitacao` é entidade fraca (PK `proposicao_id` + `sequencia`) |
| `votacoes` | `votacao`, `voto`, `orientacao`, `votacao_proposicao` | **o id da votação é texto** (`"2310837-8"`) |
| `parlamentares` | `deputado`, `partido`, `legislatura`, `lideranca`, `bloco`, `bloco_partido`, `frente`, `frente_membro` | `partido.sigla` **não é única** |
| `orgaos` | `orgao`, `deputado_orgao`, `evento`, `pauta_item` | |
| `noticias` | `noticia`, `noticia_fonte`, `noticia_revisao` | `noticia_fonte` guarda `tipo` + `ref_id`, sem FK |
| `ia` | `geracao_ia`, `trecho_rag`, `geracao_trecho` | `trecho_rag.embedding` = 768 floats (3.072 bytes) |
| `sistema` | `log_sistema`, `coleta` | |
| `auth` | `administrador` | |
| `visitantes` | `visitante`, `visitante_tema` | |

**Regras que aparecem em todo lugar:**

- **Os ids são os da API.** As PKs das tabelas espelhadas usam `autoincrement=False`. Reprocessar uma coleta faz upsert pelo id, sem duplicar (RNF06).
- **Valores fixos** (status, tipo, papel) são constantes no `models.py` com `CheckConstraint` no banco. Exemplo: [`NOTICIA_STATUS`](../../desperta/noticias/models.py) = rascunho, em_revisao, publicada, rejeitada, arquivada.
- **Sem atalhos em triângulo (regra T1):** se x → y → z, x não liga direto em z. As exceções aceitas estão no `CLAUDE.md` (5.1).
- **Os modelos seguem o estilo SQLAlchemy 2.0 tipado** do TaskFlow: `Mapped[...]`, `mapped_column`, `relationship("Classe", back_populates=...)`, cabeçalho `# === Classe ===` e `__repr__` no fim. Exemplo completo: [`desperta/proposicoes/models.py`](../../desperta/proposicoes/models.py).

### 5.2 Configuração do SQLite

Em [`ext/db/__init__.py:35`](../../desperta/ext/db/__init__.py#L35), toda conexão nova recebe:

- `PRAGMA foreign_keys=ON`: sem isso, o SQLite **não confere chave estrangeira**.
- `PRAGMA journal_mode=WAL`: escrita num arquivo à parte (`-wal`), então a API lê enquanto o coletor grava.
- `PRAGMA busy_timeout=5000`: espera até 5 s por um bloqueio, em vez de falhar na hora.
- `PRAGMA synchronous=NORMAL`: seguro com WAL e mais rápido.
- `registrar_funcoes()`: a função `raiz()` da busca, usada dentro do SQL (seção 5.4).

A `CONVENCAO_NOMES` (linha 13) dá nome fixo a índices e restrições (`uq_...`, `ck_...`, `fk_...`), o que o Alembic precisa para gerar migrações certas no SQLite. O `Migrate(render_as_batch=True)` faz o Alembic recriar a tabela quando o SQLite não sabe alterar uma coluna.

### 5.3 Colunas técnicas de sincronização

[`ext/db/mixins.py`](../../desperta/ext/db/mixins.py): `SincronizacaoMixin` acrescenta às tabelas da API

- `criado_em`: quando entrou no banco;
- `atualizado_em`: quando o conteúdo mudou de verdade;
- `sincronizado_em`: a última vez que o registro apareceu numa resposta da API;
- `hash_origem`: SHA-256 dos valores gravados.

O coletor compara o hash para saber se algo mudou (seção 6.3). Algumas tabelas também têm `filhos_sincronizados_em` (proposição, votação, evento, órgão): fica nulo enquanto os filhos (autores, votos, pauta, membros) não foram coletados, e é assim que o sistema sabe o que está **pendente**. Essas colunas são da camada física (`docs/AJUSTE_BANCO_SISTEMA.md`) e não mudam o modelo lógico do grupo.

### 5.4 Busca de texto (FTS5) e busca pela raiz das palavras

[`ext/db/busca.py`](../../desperta/ext/db/busca.py):

- `noticia_fts` e `trecho_fts`: índices FTS5 com as palavras como estão, mantidos por gatilhos.
- `noticia_fts_raiz` e `trecho_fts_raiz` (decisão 25.3): o texto reduzido à **raiz** pelo Snowball (`snowballstemmer`). "Professores", "professora" e "professor" viram a mesma raiz. Como o Snowball depende do acento, o índice guarda as duas raízes de cada palavra, com e sem acento, e quem digita "vacinacao" também acha "vacinação" ([`_raizes_da_palavra`](../../desperta/ext/db/busca.py#L33)).
- Quem mantém os índices da raiz é o **código, não o banco**: [`acompanhar_pela_raiz()`](../../desperta/ext/db/busca.py#L68) liga eventos do ORM em `Noticia` e `TrechoRAG`. De propósito não há gatilho chamando `raiz()`: se outra versão do código rodasse sem a função registrada, a gravação quebraria.
- [`conferir_busca_raiz()`](../../desperta/ext/db/busca.py#L181) é a rede de segurança: se o índice não tem uma linha por notícia, ele é refeito.

Todo SQL específico do SQLite fica isolado aqui e em `ia/vetores.py` e `ia/palavras.py` (decisão 11.1). Se um dia o banco virar PostgreSQL, só esses arquivos mudam.

### 5.5 Índices vetoriais (sqlite-vec)

[`ia/vetores.py`](../../desperta/ia/vetores.py): tabelas virtuais `vec_trecho` (RoBERTaLexPT) e `vec_trecho_e5` (e5), uma por rede neural. Elas guardam o vetor de cada trecho e respondem "os N trechos mais parecidos com este vetor" (distância do cosseno). Não fazem parte das 32 tabelas e podem ser refeitas a partir de `trecho_rag` (`flask ia reconstruir`). O `migrations/env.py` ignora essas tabelas e as FTS5, para o Flask-Migrate não tentar apagá-las.

### 5.6 Migrações

[`migrations/versions/`](../../migrations/versions): `ac243e1b323f` (esquema inicial), `535ba879b66f` (voto sem tipo, votação só com o placar), `f8a2f7162512` (campos que a Câmara manda nulos) e `19b825043af5` (índice da raiz). **Toda mudança de esquema é migração**, testada antes numa cópia do banco, com backup (`instance/desperta-antes-*.db`).

### 5.7 Verificação e persistência

- [`ext/db/verificacao.py`](../../desperta/ext/db/verificacao.py) (`flask banco verificar`, só leitura): integridade, chaves estrangeiras, as 32 tabelas, a versão da migração, WAL, **votos contra o placar da Câmara** (`_placares`, linha 124), referências sem FK, índices de busca e vetoriais, embeddings, datas e coletas interrompidas. No banco real: 23 aprovados, 0 falhas.
- [`coletor/persistencia.py`](../../desperta/coletor/persistencia.py) (`flask banco testar-persistencia`): numa **cópia** feita pelo backup do SQLite, testa ida e volta, upsert sem duplicar, atualização no lugar, erro isolado, restrições e cascata.

---

## 6. O coletor (dados da Câmara)

Pasta [`desperta/coletor/`](../../desperta/coletor). Não é blueprint: é usado pelos comandos `flask coletar ...` e pelo agendador.

### 6.1 O cliente HTTP

[`cliente.py`](../../desperta/coletor/cliente.py), classe `ClienteCamara` (linha 23):

- [`_chamar()`](../../desperta/coletor/cliente.py#L46): faz o GET e, em 429 ou 5xx (`STATUS_REPETIR`, linha 5), timeout ou queda de conexão, **tenta de novo** com espera exponencial: 2, 4, 8 e 16 s (`ESPERAS_PADRAO`, linha 6), até 5 tentativas (RNF02). Erro 4xx ou JSON inválido levanta `ErroAPI` na hora.
- [`paginar()`](../../desperta/coletor/cliente.py#L81): segue o link `next` da API e devolve item por item (gerador Python, sem carregar tudo na memória).
- [`definir_orcamento()`](../../desperta/coletor/cliente.py#L38): a horária tem 20 minutos. Depois disso, nenhuma chamada nova começa (`TempoEsgotado`), e o resto fica para a próxima hora (14.2).
- Os contadores `requisicoes` e `erros_http` vão para a tabela `coleta` (11.4).
- Nos testes, o cliente recebe uma API falsa ([`tests/api_falsa.py`](../../tests/api_falsa.py)) e um `dormir` que não espera: **os testes nunca chamam a Câmara de verdade**.

### 6.2 A execução de uma coleta

[`execucao.py`](../../desperta/coletor/execucao.py), classe `Execucao` (linha 25), usada como `with Execucao(...) as execucao:`.

- **Ao entrar,** cria uma linha em `coleta` com status `parcial`. Ela só vira `ok` no fim: se o processo morrer no meio, a coleta não conta como concluída.
- [`principal()`](../../desperta/coletor/execucao.py#L88): o **upsert** de um registro principal. Ele calcula o hash dos valores e:
  - registro novo → cria, conta em `itens_novos`;
  - hash diferente → atualiza no lugar, conta em `itens_atualizados`;
  - hash igual → só marca `sincronizado_em`.
- [`vinculo()`](../../desperta/coletor/execucao.py#L134): o mesmo para linhas filhas e associativas.
- [`_proteger()`](../../desperta/coletor/execucao.py#L74): cada registro é gravado dentro de `db.session.begin_nested()` (um SAVEPOINT). Se um registro falhar, por exemplo um campo obrigatório vazio, **só ele é desfeito**: o erro vai para `log_sistema` e a coleta segue (decisão 10.2).
- [`processar()`](../../desperta/coletor/execucao.py#L183): processa um item pai.
  - Um erro de API desse item não derruba a coleta, mas **5 falhas seguidas** (`MAX_FALHAS_API_SEGUIDAS`) indicam que a API caiu, e a coleta para.
  - Um **404 no detalhe do próprio item** (o registro sumiu da Câmara) vira um aviso `nao_encontrado_na_camara` e o item é pulado nas 24 h seguintes (25.8).
- [`concluir_item()`](../../desperta/coletor/execucao.py#L240): `commit` a cada item, para não segurar o banco durante as chamadas HTTP.
- [`remover_sumidos()`](../../desperta/coletor/execucao.py#L161): apaga os filhos que não vieram nesta coleta (por exemplo, um autor retirado), comparando `sincronizado_em` com o início da coleta.

### 6.3 Um módulo por recurso

| Arquivo | O que coleta | Detalhes que importam |
|---|---|---|
| [`proposicoes.py`](../../desperta/coletor/proposicoes.py) | proposições, autores, temas, tramitações | A listagem só descobre ids; cada uma é gravada a partir do detalhe. **Os filhos só são buscados se a proposição é nova, está pendente ou mudou de `data_status`** ([`_precisa_dos_filhos`](../../desperta/coletor/proposicoes.py#L108), decisão 12.1). Isso derrubou o número de chamadas. Na horária, pula as conferidas há menos de 6 h ([`_ja_conferidas`](../../desperta/coletor/proposicoes.py#L159)). |
| [`votacoes.py`](../../desperta/coletor/votacoes.py) | votações, votos, orientações, proposições afetadas | Votação simbólica tem `/votos` vazio; votação só com o placar tem votos sem tipo (22.2). |
| [`eventos.py`](../../desperta/coletor/eventos.py) | eventos e pauta | Todo órgão da lista do evento é cadastrado (D5); a API repete o item de pauta, e fica uma linha por item (12.4). |
| [`deputados.py`](../../desperta/coletor/deputados.py) | deputados | A listagem traz o mesmo deputado uma vez por partido; quando as linhas diferem, vale o detalhe (22.3). |
| [`blocos.py`](../../desperta/coletor/blocos.py) | blocos e partidos do bloco | A API devolve o id do bloco no lugar do partido; o coletor procura pela sigla na mesma legislatura (12.3). |
| [`orgaos.py`](../../desperta/coletor/orgaos.py), [`partidos.py`](../../desperta/coletor/partidos.py), [`legislaturas.py`](../../desperta/coletor/legislaturas.py), [`liderancas.py`](../../desperta/coletor/liderancas.py), [`frentes.py`](../../desperta/coletor/frentes.py), [`temas.py`](../../desperta/coletor/temas.py) | tabelas de apoio | Os temas ganham ícone Material Symbols (`ICONES_TEMA`, 25.2). |

Auxiliares:

- [`normalizacao.py`](../../desperta/coletor/normalizacao.py): converte o que a API manda (ids em texto, datas, 0/1) e calcula o hash. As datas da Câmara ficam no **horário de Brasília**, sem fuso, como a API manda; as colunas técnicas ficam em **UTC**.
- [`referencias.py`](../../desperta/coletor/referencias.py): quando um registro cita outro que ainda não está no banco (o autor é um deputado novo, a votação cita um requerimento), busca esse outro na API antes de gravar, por causa das chaves estrangeiras.
- [`janelas.py`](../../desperta/coletor/janelas.py): divide períodos longos em janelas de até 3 meses, porque a API recusa maiores.
- [`relatorio.py`](../../desperta/coletor/relatorio.py) (`flask coletar relatorio`): colunas que falharam, falhas da API, pendentes e avisos.

### 6.4 As rotinas e a trava

[`rotinas.py`](../../desperta/coletor/rotinas.py) junta os módulos no calendário do RF02:

- [`horaria()`](../../desperta/coletor/rotinas.py#L37): votações e eventos de ontem e de hoje primeiro, as proposições do dia por último, com orçamento de 20 minutos.
- [`diaria()`](../../desperta/coletor/rotinas.py#L55): proposições dos últimos 3 dias, pautas e votações pendentes.
- [`semanal()`](../../desperta/coletor/rotinas.py#L63): varredura de 30 dias, tabelas de apoio, membros de órgãos, Mesa, lideranças e blocos.
- [`mensal()`](../../desperta/coletor/rotinas.py#L74): frentes.

[`trava.py`](../../desperta/coletor/trava.py): **uma coleta por vez**. O arquivo `instance/coletor.lock` guarda o PID e a hora. Se a trava existe e o processo daquele PID ainda roda, a nova coleta não começa. Se o processo morreu, ou se a trava tem mais de 6 h, ela é considerada abandonada e removida (13.6). Com SIGTERM, a coleta fecha o registro e libera a trava antes de sair.

---

## 7. A IA: busca (RAG) e escrita das notícias

Pasta [`desperta/ia/`](../../desperta/ia). Primeiro, um esclarecimento importante: **as redes neurais do projeto não escrevem as notícias.** A RoBERTaLexPT e o e5 transformam texto em vetores, para a busca. Quem escreve hoje é o `GeradorFrases`, por regras. A Roberta escritora (Fase 3b, seção 17) é um modelo futuro, que ainda vai ser treinado.

### 7.1 Trechos

[`trechos.py`](../../desperta/ia/trechos.py) decide o que vira texto pesquisável:

- **proposição:** sigla, número, ementa, ementa detalhada e palavras-chave;
- **tramitação:** só as dos últimos 90 dias, começando pela proposição (16.3);
- **votação:** a descrição, o órgão, a data, o resultado e o que os dados dizem dos votos (22.5);
- **evento e item de pauta.**

Cada texto vira um ou mais trechos de até 400 tokens, com 50 de sobreposição.

### 7.2 As duas redes neurais

[`embeddings.py`](../../desperta/ia/embeddings.py), classe `ModeloEmbedding`:

- Carrega o modelo de uma pasta local (`local_files_only`, sem internet), no dispositivo de `IA_DISPOSITIVO` (`auto` usa a placa NVIDIA se existir).
- [`embutir()`](../../desperta/ia/embeddings.py#L171): tokeniza (até 512 tokens), roda o modelo com `torch.no_grad()`, faz a **média dos estados da última camada, pesada pela máscara de atenção** (mean pooling), e normaliza para comprimento 1 (L2). O resultado são 768 floats por trecho.
- **RoBERTaLexPT** (`eduagarcia/RoBERTaLexPT-base`): treinada em textos jurídicos em português, mas para preencher lacunas, não para comparar frases. Por isso os vetores dela ficam todos parecidos (cosseno entre 0,95 e 0,99).
- **e5** (`intfloat/multilingual-e5-base`, MIT, decisão 25.10): treinada justamente para comparar significado. Usa os prefixos `passage: ` nos trechos e `query: ` na consulta. Nos julgamentos do grupo (20 consultas, 4 leitores), ela ganhou com folga. É a usada na escrita (`RAG_MODELO=e5`).
- Se a pasta do modelo não existe (por exemplo, o pendrive da RoBERTa fora), o código levanta `ModeloAusente`, grava um aviso no log e segue sem aquele modelo (21.3).

### 7.3 Indexação

[`services.indexar()`](../../desperta/ia/services.py#L85):

1. Gera os textos de origem.
2. Calcula o SHA-256 de cada texto e compara com o `hash_texto` já guardado. **Só o que é novo ou mudou ganha vetor.**
3. Grava em lotes de 64: vetor em `trecho_rag.embedding` e no índice `vec_trecho*`. Cada lote é confirmado (`commit`), então parar no meio não perde nada.
4. Remove os trechos cuja origem sumiu, menos os que alguma geração usou (o histórico fica).

Cada modelo tem os seus trechos: o mesmo texto aparece duas vezes em `trecho_rag`, com `modelo_embedding` diferente.

### 7.4 Busca híbrida (RAG)

[`services.buscar()`](../../desperta/ia/services.py#L215), decisão 16.1:

1. **Busca por palavras:** os 50 melhores do índice da raiz, ordenados pelo `bm25` ([`palavras.py`](../../desperta/ia/palavras.py)).
2. **Busca vetorial:** a consulta vira vetor e o sqlite-vec devolve os 50 trechos mais próximos ([`vetores.buscar`](../../desperta/ia/vetores.py)).
3. **Junção por RRF** (Reciprocal Rank Fusion, [`_juntar_por_rrf`](../../desperta/ia/services.py#L205)): cada trecho soma `peso / (60 + posição)` em cada lista. Quem aparece bem nas duas sobe. Os 8 maiores vão para o gerador.

Os filtros por tipo e por período valem para as duas buscas. O filtro entra por um JOIN com `trecho_rag` (com `rowid IN (...)`, o SQLite avaliava o FTS5 trecho a trecho e chegava a 44 s; com o JOIN, menos de 0,1 s).

### 7.5 A geração de uma notícia

[`geracao.gerar_noticia()`](../../desperta/ia/geracao.py), passo a passo:

1. Lê a origem (a votação ou a proposição) e monta a `entrada` (JSON com os ids).
2. Confere se o **mesmo fato** já tem notícia ([`chave_do_fato`](../../desperta/ia/geracao.py), 25.16): votação pelo id da votação; proposição nova pelo id da proposição; mudança de situação pela proposição e a data da situação. Antes, a comparação usava a entrada inteira, que inclui a data da situação, e a mesma votação era escrita de novo a cada passo do andamento. Esse defeito foi corrigido em 17/11.
3. Escolhe o tema: o principal da Câmara (relevância 0, 25.2), ou o tema especial 0, "Sem tema informado pela Câmara" (25.6).
4. Monta os `DadosNoticia` (proposição, votação, últimos passos, lacunas, link da ficha) e faz a busca do RAG.
5. Chama o gerador e manda o fato para o **destino** certo ([`viva.destino_do_fato`](../../desperta/noticias/viva.py)): entra numa notícia aberta da proposição, vira rascunho de atualização da publicada, ou abre uma notícia nova.
6. Grava `geracao_ia` (modelos, consulta, entrada, tokens, duração) e `geracao_trecho` (os trechos usados, com a posição e a nota do RRF). **Toda execução grava `geracao_ia`, mesmo com erro** (status `erro`, `noticia_id` nulo).

### 7.6 O GeradorFrases (quem escreve)

[`gerador.py`](../../desperta/ia/gerador.py). Interface `Gerador.escrever(consulta, trechos, dados)` → `TextoGerado(titulo, resumo, corpo)`. Há o `GeradorFalso` (para os testes) e o `GeradorFrases` (o de verdade, versão `frases-v3`). Ele **nunca escreve um fato que não esteja nos dados**:

- [`simplificar_ementa()`](../../desperta/ia/gerador.py): só com regras, tira o que é fórmula ("Altera a Lei nº X para…" vira "prever…"), sem acrescentar nada.
- `_nova`, `_situacao`, `_votacao`: o título e o parágrafo principal de cada caso. Exemplos reais:
  - "PL 1234/2024 institui o Dia Nacional da Merenda" / "O projeto de lei PL 1234/2024, de autoria de…, foi apresentado em… O texto institui…";
  - "A situação do projeto de lei PL 396/2007 na Câmara mudou para "Pronta para Pauta". A proposta já passou pelas etapas exigidas e pode entrar na pauta de votação."
- **Votação de mérito** ([`e_votacao_de_merito`](../../desperta/votacoes/services.py)): "Câmara aprova…" só quando a votação decidiu o próprio projeto. Requerimento, destaque e redação final nunca viram "Câmara aprova projeto", porque seria um fato falso.
- `_corpo`: as seções da planta (`## O que propõe`, `## Resultado da votação`, `## Onde está na Câmara`, `## O que a Câmara não informou`).

### 7.7 A geração automática

[`automatico.py`](../../desperta/ia/automatico.py):

- [`fatos_da_janela()`](../../desperta/ia/automatico.py): os fatos dos últimos 3 dias (`GERACAO_JANELA_DIAS`), nesta ordem: votações que afetam um tipo acompanhado, **mudanças de situação de verdade** (a situação ficou outra, e não só a data andou; [`situacao_mudou`](../../desperta/proposicoes/services.py), 25.1) e proposições novas.
- [`gerar_novos()`](../../desperta/ia/automatico.py): para cada fato, pula o pendente e o já feito, classifica como notícia própria ou boletim (seção 7.8) e chama `gerar_noticia`. Também atualiza o tema das notícias no tema especial quando a Câmara classifica a proposição (25.6).
- [`depois_da_coleta()`](../../desperta/ia/automatico.py): indexa nas duas redes e gera os rascunhos com a de `RAG_MODELO`.

### 7.8 Boletins do dia

[`boletim.py`](../../desperta/ia/boletim.py), decisão 25.17:

- [`classificar()`](../../desperta/ia/boletim.py): **notícia própria** para a votação do projeto no Plenário, o marco de situação, PEC, MPV, PL ou PLP nova e qualquer fato com falha grave da Câmara. **Boletim** para a votação de procedimento no Plenário, a votação em comissão, a mudança de situação que não é marco e o PDL novo. **Na dúvida, notícia própria**, com aviso no log.
- O fato pequeno de proposição que já tem notícia viva também entra nela como atualização.
- [`gerar_boletins()`](../../desperta/ia/boletim.py): na diária, os boletins do dia anterior, um por tipo de fato (Plenário, comissões, andamento e proposições novas). Cada fato é uma linha com o link da página da proposição.

### 7.9 Relatório semanal

[`relatorio.py`](../../desperta/ia/relatorio.py), decisão 25.5: domingo, o resumo dos sete dias (votações, avanços, proposições novas, temas mais comuns), com frases prontas, como rascunho do tipo `relatorio`.

---

## 8. As notícias: fila, notícia viva, prioridade, planta e publicação

Pasta [`desperta/noticias/`](../../desperta/noticias).

### 8.1 Modelo e fluxo de status

[`models.py`](../../desperta/noticias/models.py): `Noticia` (título, slug, resumo, corpo, tipo, origem, tema, status, datas, visualizações), `NoticiaFonte` (de onde veio cada fato) e `NoticiaRevisao` (cada ação da equipe: editou, aprovou, rejeitou, publicou, arquivou).

```
rascunho ──aprovar──▶ em_revisao ──publicar──▶ publicada ──arquivar──▶ arquivada
    │                     │
    └──────rejeitar───────┴──▶ rejeitada
```

- O **slug** (endereço da notícia) acompanha o título até a publicação; depois, nunca muda.
- `alterado_em` só muda quando o texto muda, e não quando alguém visualiza.

### 8.2 Os services

[`services.py`](../../desperta/noticias/services.py), o maior arquivo do projeto (711 linhas):

- `criar_rascunho`, `gerar_slug`, `editar_noticia`, `mudar_status` (com o caso do rascunho de atualização), `mudar_status_em_lote` (até 200), `excluir_noticia` (só admin, só rascunho ou rejeitada, 10.4).
- **Parte pública:** `listar_publicadas`, `pagina_principal`, `buscar_publicadas` (busca pela raiz, com período em horário de Brasília), `publicada_pelo_slug`, `contar_visualizacao`.
- **Saída da API:** `como_cartao`, `como_completa` (com `secoes`, `transparencia` e a lista de atualizações), `como_foi_feita` (gerador, revisões, quem publicou e se foi publicada sozinha), `fontes_com_links`.
- **Área da equipe:** `listar_para_revisao` (a fila, com os filtros), `como_detalhe_de_revisao` (com o histórico, os trechos que a IA usou, as lacunas com o nível, a prioridade e a conferência da planta).
- [`secoes_do_corpo()`](../../desperta/noticias/services.py): divide o corpo nas seções `## ` para a API entregar cada parte separada.

### 8.3 Notícia viva

[`viva.py`](../../desperta/noticias/viva.py), decisão 25.16: **uma notícia por proposição.**

- O fato que abriu a notícia fica no topo: o título, o parágrafo principal e o tema não mudam.
- Cada fato novo entra na seção `## Atualizações`, da mais recente para a mais antiga.
- Se a notícia já foi publicada, o fato novo vira um **rascunho de atualização**. Ao ser publicado, ele entra na notícia original (mesmo endereço) e fica arquivado como histórico.
- [`juntar()`](../../desperta/noticias/viva.py) e o script `scripts/triagem/noticia_viva.py` juntaram os rascunhos repetidos da fila em 17/11: de 2.116 para 1.230 notícias.

### 8.4 Fila por prioridade

[`prioridade.py`](../../desperta/noticias/prioridade.py), decisão 25.15: alta, média ou baixa, com os motivos, calculada na hora (sem coluna no banco).

- **Alta:** relatório, votação do projeto no Plenário, marco, PEC ou MPV nova, falha grave da Câmara.
- **Baixa:** procedimento em comissão, PDL novo, passo sem situação.
- **Média:** o resto.

Na notícia viva, vale o fato mais importante. As lacunas de muitas notícias são calculadas em lote ([`lacunas_em_lote`](../../desperta/sistema/lacunas.py)), com poucas consultas.

### 8.5 Planta da notícia

[`planta.py`](../../desperta/noticias/planta.py) e [`docs/PLANTA_DA_NOTICIA.md`](../PLANTA_DA_NOTICIA.md), decisão 25.18. A estrutura padrão de toda notícia: imparcial, resumida e para o brasileiro comum.

[`conferir_texto()`](../../desperta/noticias/planta.py) mede o texto:

- **Título:** de 10 a 120 caracteres, nunca cortado, com a sigla.
- **Parágrafo principal:** até 2 frases e 60 palavras, sigla explicada, sem placar e sem lacuna.
- **Sem palavra de opinião:** "polêmico", "histórico", "finalmente", "conseguiu"…
- **Blocos obrigatórios por caso.**

[`conferir()`](../../desperta/noticias/planta.py) soma as regras de **confiança**: foi escrita na planta, ninguém da equipe mexeu nela, não tem falha grave da Câmara e a situação está no dicionário.

### 8.6 Publicação automática

[`publicar_automaticas()`](../../desperta/noticias/planta.py), com `PUBLICACAO_AUTOMATICA`:

- `ensaio` (padrão): só conta e marca na fila.
- `ligada`: publica o que passa.
- `desligada`: não faz nada.

A publicação é assinada pelo cadastro técnico "Publicação automática" (desativado, sem login), e o site diz que a notícia saiu sem revisão da equipe. Medido em 17/11: 62% das notícias próprias passariam. As mudanças de situação passam sempre; as proposições novas quase nunca, porque o título copia a ementa inteira e passa de 120 caracteres. Resumir a ementa num título curto é trabalho para a Roberta escritora.

---

## 9. Transparência: lacunas da Câmara e situação explicada

### 9.1 O que a Câmara não informou

[`sistema/lacunas.py`](../../desperta/sistema/lacunas.py), decisão 25.14. Cada lacuna tem:

- **código:** por exemplo `sem_tema`, `so_placar`, `sem_regime`;
- **nível interno**, que o leitor não vê:
  1. contradição (votos que não batem com o placar, registro que sumiu);
  2. ocultação (só o placar, sem o voto de cada deputado; sem tema há mais de 30 dias);
  3. atraso (sem tema ainda);
  4. campo vazio (situação, regime ou inteiro teor);
  5. prática normal (votação simbólica, que não é falha);
- **grau de certeza do motivo:** comprovado, indicado (dedução) ou sem explicação;
- **prova:** o endereço da API consultado, o campo, **o valor como veio** (`null (vazio)`, `"." (só um ponto)`, `[] (lista vazia)`) e a data da consulta;
- **o link** "Para mais informações, acesse o site da Câmara dos Deputados", que aponta para a ficha da proposição.

O texto afirma só o que dá para provar. Exemplo: no PDL 995/2026, os dados abertos **não dizem** que a votação foi secreta. Eles registram 466 presenças sem o voto e o placar de 404 a 61, e a notícia conta só isso (código `so_placar`).

### 9.2 Situação explicada

[`proposicoes/situacoes.py`](../../desperta/proposicoes/situacoes.py): os 47 códigos de situação da Câmara, cada um com uma explicação em linguagem comum, aprovada pelo Lucas em 17/11. O leitor vê sempre o nome exato da Câmara, mais a explicação. A lista `MARCOS` (interna) diz quais situações viram notícia própria. Um código desconhecido aparece só com o nome da Câmara e gera um aviso no log.

### 9.3 Votos

[`votacoes/services.py`](../../desperta/votacoes/services.py): [`classificar_votos()`](../../desperta/votacoes/services.py) separa as votações em simbólica, só placar, inconsistente e nominal; `situacao_dos_votos()` acrescenta pendente e erro na coleta. As orientações saem em três grupos: partidos, lideranças (Governo, Maioria, Minoria e Oposição) e blocos (10.1).

---

## 10. A API REST

Rotas finas em cada `routes.py`; as regras ficam nos services. Auxiliares comuns em [`ext/api/__init__.py`](../../desperta/ext/api/__init__.py):

- `corpo_json` exige JSON (isso também protege contra formulário de outro site);
- `parametro_int`, `parametro_texto` e `pagina` validam os parâmetros;
- `paginado` monta as listas como `{itens, pagina, por_pagina, total, paginas}`;
- `iso` e `iso_camara` formatam as datas: as do portal saem em UTC, com `Z`; as da Câmara, com `-03:00`;
- `periodo_em_utc` converte o filtro de dia, mês e ano.

| Rota | Quem | O que faz |
|---|---|---|
| `GET /api/health` | público | saúde da API |
| `GET /api/noticias`, `/principal`, `/busca`, `/<slug>` | público | publicadas por tema, página principal, busca e detalhe (com seções, transparência e atualizações) |
| `GET /api/proposicoes/<id>`, `/<id>/tramitacoes`, `/temas` | público | proposição com a situação explicada e as lacunas, andamento, temas |
| `GET /api/votacoes/<id>` | público | resultado, situação dos votos, votos, orientações e lacunas |
| `GET /api/sistema/situacao` | público | última coleta e aviso de dados desatualizados (RNF05) |
| `POST /api/auth/login`, `/logout`, `GET /eu`, `POST /eu/senha` | equipe | login e sessão |
| `GET/POST /api/auth/equipe`, `PATCH /equipe/<id>` | admin | cadastro da equipe |
| `GET /api/noticias/admin` (+ filtros), `GET/PATCH /admin/<id>`, `POST /admin` | equipe | fila, detalhe, edição, notícia escrita pela equipe |
| `POST /api/noticias/admin/<id>/<acao>`, `/admin/lote` | equipe | aprovar, publicar, rejeitar, arquivar (um ou em lote) |
| `DELETE /api/noticias/admin/<id>` | admin | apaga rascunho ou rejeitada |
| `GET /api/sistema/coletas`, `/log` | admin | coletas e log |

**Erros** ([`ext/erros/__init__.py`](../../desperta/ext/erros/__init__.py)): o service levanta `DadosInvalidos` (400), `NaoAutenticado` (401), `AcessoNegado` (403), `NaoEncontrado` (404), `Conflito` (409) ou `MuitasTentativas` (429), e um handler transforma em `{"erro": "mensagem"}`. As rotas não tratam erro, e um registro em uso nunca vira 500.

**Limite de requisições** ([`ext/limite/__init__.py`](../../desperta/ext/limite/__init__.py), 25.4): por IP, numa janela de 60 s. São 600 requisições no geral e 60 na busca, com conta própria; acima disso, a API responde 429 com `Retry-After`. Quem está logado na área da equipe não entra na conta.

**CORS** ([`ext/cors`](../../desperta/ext/cors/__init__.py), 10.5): só para as origens de `CORS_ORIGINS`, com o cookie. Em desenvolvimento, o Vite repassa `/api` para o Flask e o CORS nem entra.

---

## 11. Login da equipe e segurança

- **Senha:** com hash do Werkzeug ([`Administrador.set_senha`](../../desperta/auth/models.py#L60)). A `senha_hash` nunca sai na API.
- **Sessão** ([`auth/sessao.py`](../../desperta/auth/sessao.py)): cookie assinado pelo Flask com a `SECRET_KEY`, `HttpOnly`, `SameSite=Lax` e duração de 8 h.
  - A cada requisição, o administrador é lido de novo do banco: quem foi desativado perde o acesso na hora.
  - A sessão guarda os últimos 16 caracteres da `senha_hash` ([`_marca_da_senha`](../../desperta/auth/sessao.py#L24)), então **trocar a senha encerra as outras sessões**.
  - Os decoradores `login_obrigatorio` e `so_admin` protegem as rotas.
- **Tentativas de login** ([`auth/services.autenticar`](../../desperta/auth/services.py#L269)): depois de 5 falhas em 15 minutos, por e-mail, ou 4 vezes isso por IP, o login responde 429.
- **Papéis:** `editor` (revisa e publica) e `admin` (também cuida da equipe e vê coletas e log). Ninguém é apagado: quem sai vira `ativo = False`, para manter o histórico, e sempre sobra um admin ativo.
- **O primeiro admin é criado pelo terminal:** `flask equipe criar-admin`.

---

## 12. O agendador (as rotinas que rodam sozinhas)

- [`scripts/agendador/agendador.py`](../../scripts/agendador/agendador.py) gera **timers de usuário do systemd** com os caminhos da pasta e do `.venv`:
  - `horaria`: toda hora, no minuto 5;
  - `diaria`: 3h30;
  - `semanal`: domingo, 4h30;
  - `mensal`: dia 1, 5h30.

  Os três últimos têm `Persistent=true`: se o PC estava desligado, rodam quando ele ligar. A saída vai para `instance/agendador.log`.
- Cada timer chama [`flask coletar agendada <rotina>`](../../desperta/coletor/cli.py#L169): coleta, indexação, rascunhos, boletins (diária), relatório (semanal) e publicação automática, tudo sob a mesma trava. A horária não espera trava (fica para a hora seguinte); as outras esperam até 180 minutos.
- **Cuidados:**
  - O agendador roda **o código que está na pasta**, então a pasta principal deve ficar na `main`, e o trabalho em andamento, num worktree.
  - Os timers de usuário só rodam com o usuário logado.
  - Para parar uma coleta, use `kill -TERM <PID>`, nunca `pkill -f`.

---

## 13. Os testes

`invoke test` roda os 920 testes com cobertura (cerca de 40 s). Nenhum deles chama a Câmara, baixa modelo ou toca no banco real.

- [`tests/conftest.py`](../../tests/conftest.py): a fixture `app` cria a aplicação com `TestConfig` (SQLite em memória) e, no fim, fecha as conexões (por isso não há avisos de recurso aberto). A fixture `db` faz `create_all()` e `drop_all()`; as fixtures `api` e `cliente` dão uma API da Câmara falsa.
- [`tests/fabricas.py`](../../tests/fabricas.py): funções que montam registros válidos (`proposicao()`, `votacao()`, `noticia()`…) e `popular(db)`, que grava uma linha em cada uma das 32 tabelas.
- [`tests/api_falsa.py`](../../tests/api_falsa.py) e `tests/fixtures/camara/`: respostas gravadas da API real, em JSON.
- **Os testes de IA** usam modelos falsos (vetores determinísticos) e são pulados se o `sqlite-vec` ou o PyTorch não estiverem instalados. O que precisa da placa de vídeo é pulado sem ela.

| Arquivo | O que cobre |
|---|---|
| `test_banco_*` (6) | as 32 tabelas, PKs, restrições, cascata, `__repr__`, camada física, verificação |
| `test_migracoes.py` | as migrações sobem e descem |
| `test_coletor_*` (5) | cliente com novas tentativas, normalização, execução (savepoint, 404), cada recurso, rotinas e trava |
| `test_ia.py` (92), `test_busca_raiz.py`, `test_tema_principal.py` | indexação, busca, RRF, modelos, raiz |
| `test_gerador.py`, `test_geracao_automatica.py` | o texto do GeradorFrases e a geração automática |
| `test_noticia_viva.py`, `test_prioridade.py`, `test_planta.py`, `test_boletim.py`, `test_relatorio.py` | o plano das notícias (25.13 a 25.18) |
| `test_lacunas.py`, `test_transparencia.py` | lacunas com prova, situação explicada, votos |
| `test_rotas.py`, `test_auth_services.py`, `test_limite.py`, `test_cors_e_erros.py`, `test_noticias_exclusao.py` | a API, o login e a segurança |
| `test_agendador.py` | o gerador dos timers do systemd |
| `test_analise_pec.py`, `test_temas_prototipo.py` | os scripts de estudo |

**Regra do projeto:** rodar os testes antes de cada commit e nunca fazer commit com teste falhando.

---

## 14. Os scripts e os estudos

| Pasta | O que é |
|---|---|
| [`scripts/agendador/`](../../scripts/agendador) | gera os timers do systemd (seção 12) |
| [`scripts/ver_banco/`](../../scripts/ver_banco) | configuração do visualizador do banco (Datasette), com busca rápida, nomes no lugar dos ids e 15 consultas prontas |
| [`scripts/triagem/`](../../scripts/triagem) | as triagens feitas na fila real: os rascunhos de situação com texto errado (25.9) e a junção da notícia viva (25.16) |
| [`scripts/analise_pec/`](../../scripts/analise_pec) | **o estudo da leitura da PEC** com a RoBERTaLexPT (encerrado em 25.7): leitura encadeada, 1.000 repetições com dropout, whitening, comparação com os 4 leitores do grupo. A conclusão foi que a Roberta original não acha as frases importantes de uma PEC; ela entra no portal pela busca. Documentos: `docs/LEITURA_ENCADEADA.md` e `docs/ESTUDO_ROBERTA_X_GRUPO.md`. |
| [`scripts/temas_prototipo/`](../../scripts/temas_prototipo) | o estudo da **sugestão de tema** por exemplos (kNN e protótipos, com whitening e TF-IDF): 88% de acerto no primeiro tema. Ainda não está no portal. |

---

## 15. O protótipo do site (front-end)

Está na branch **`prototipo-front`** (não na `main`), na pasta `frontend/`: Vue 3 + Vite + Axios + vue-router, fonte Roboto e Source Serif, ícones Material Symbols, tema claro e escuro (paleta lápis, cobre e marfim; todo texto acima de 7:1 de contraste desde 17/11).

- **Páginas** (`src/paginas/`): `PaginaInicial`, `PaginaTema`, `PaginaTemas`, `PaginaBusca`, `PaginaNoticia` e, em `equipe/`, `PaginaEntrar` e `PaginaFila`.
- **Componentes** (`src/componentes/`): `CartaoNoticia`, `ComoFoiFeita`, `SecaoVotacao`, `BarraVotos`, `SecaoAndamento`, `QuadroProposicao`, `FaixaColeta` (aviso de dados desatualizados), `AvisoCookies`, `NavTemas`, `Paginacao`…
- `src/services/api.js`: o Axios com a base `/api`. O `vite.config.js` repassa `/api` para `http://localhost:5000`, como no TaskFlow.
- **Como rodar:** a API com a cópia do protótipo, `DATABASE_URL=sqlite:///desperta-prototipo.db flask --app app.py run`; e o front com `cd frontend && npm install && npm run dev`. Abra `http://localhost:5173`; a área da equipe fica em `/equipe/entrar`.
- **Limite atual:** o protótipo é de 14 e 15/11 e ainda não mostra o que a API passou a entregar depois: as seções, a situação explicada, as lacunas, as atualizações da notícia viva, a prioridade e a conferência da planta. O site de verdade é a Fase 5.

---

## 16. O que falta e para onde o projeto vai

**Plano das notícias:** notícias relacionadas (item 5) e o filtro calibrado com os formulários do grupo (item 6, `instance/analise_selecao/filtro_<nome>.json`).

**Para ir ao ar de verdade:**
1. Cookies e LGPD (RF13, RF17, RNF09): as tabelas `visitante` e `visitante_tema` existem, mas as rotas ainda não.
2. Servidor com HTTPS: Gunicorn + Nginx + Let's Encrypt, com `ProxyFix` para o limite enxergar o IP do visitante (21.4).
3. Licença do projeto (o grupo decide com o professor).
4. A equipe publicando, ou a publicação automática ligada.

**Fases seguintes:**
- Site de verdade (Fase 5), com a voz: Whisper na busca e Piper para ler a notícia.
- Roberta escritora (Fase 3b): treino nos desktops do grupo e com o professor. Ela é a peça que falta para os títulos curtos e para a publicação automática passar das proposições novas.
- Nota de relevância, teste de carga, relatórios por evento e por legislatura, sugestão de tema.

**Longo prazo (TCC):** mais casas legislativas (Senado, assembleias), entrando como coletores novos, e um aplicativo, que usa a mesma API REST.

---

## 17. Glossário

- **API de Dados Abertos da Câmara:** a fonte de todos os dados (`dadosabertos.camara.leg.br/api/v2`), gratuita e sem chave.
- **Proposição:** qualquer proposta: PL (projeto de lei), PLP (projeto de lei complementar), PEC (proposta de emenda à Constituição), MPV (medida provisória), PDL (projeto de decreto legislativo), REQ (requerimento)…
- **Tramitação:** cada passo do andamento de uma proposição.
- **Ementa:** o resumo oficial do que a proposição faz.
- **Situação:** onde a proposição está ("Aguardando Parecer", "Pronta para Pauta"…); os marcos são as situações importantes.
- **Votação simbólica:** sem registro do voto de cada deputado; o resultado é anunciado por quem preside a sessão.
- **Upsert:** gravar como novo se não existe, ou atualizar se já existe, sem duplicar.
- **Savepoint (`begin_nested`):** um ponto de volta dentro de uma transação, para desfazer só um registro.
- **WAL:** modo do SQLite em que a escrita vai para um arquivo à parte, deixando ler e escrever ao mesmo tempo.
- **FTS5:** o motor de busca por palavras do SQLite; o `bm25` é a nota de relevância dele.
- **Snowball / raiz:** a redução da palavra à raiz ("professores" → "profes").
- **Embedding / vetor:** a representação de um texto como 768 números; textos parecidos têm vetores próximos.
- **Mean pooling / L2:** a média dos vetores das palavras e a normalização para comprimento 1.
- **sqlite-vec:** a extensão que guarda os vetores e acha os mais próximos.
- **RAG:** Retrieval-Augmented Generation; aqui, buscar os trechos certos antes de escrever.
- **RRF:** Reciprocal Rank Fusion; juntar duas listas ordenadas somando `1/(60 + posição)`.
- **RoBERTaLexPT, e5:** as duas redes neurais da busca (seção 7.2).
- **Whitening:** tirar a média e igualar o peso das direções dos vetores; ajudou a RoBERTa no estudo dos temas.
- **GeradorFrases:** quem escreve as notícias hoje, por regras.
- **Notícia viva, boletim, planta, lacuna:** seções 8 e 9.
- **Worktree:** uma segunda pasta do mesmo repositório git, numa outra branch, usada para trabalhar sem tirar a pasta principal da `main`.

---

## Apêndice A: todas as classes e funções, com a linha

Gerado automaticamente a partir do código da `main` (`d31c654`), com a primeira linha da documentação de cada função. Os números de linha valem para esse commit; depois de mudanças no código, gere de novo.

### `desperta/__init__.py` (67 linhas)
- [desperta/__init__.py:25](../../desperta/__init__.py#L25) função `create_app(config_class)`

### `desperta/config.py` (81 linhas)
- [desperta/config.py:5](../../desperta/config.py#L5) classe `Config`
- [desperta/config.py:76](../../desperta/config.py#L76) classe `TestConfig`

### `desperta/auth/__init__.py` (7 linhas)
- [desperta/auth/__init__.py:5](../../desperta/auth/__init__.py#L5) função `init_app(app)`

### `desperta/auth/cli.py` (33 linhas)
- [desperta/auth/cli.py:16](../../desperta/auth/cli.py#L16) função `criar_admin(nome, email, papel, senha)`: Cria alguem da equipe pelo terminal; a API so deixa um admin criar outros.
- [desperta/auth/cli.py:26](../../desperta/auth/cli.py#L26) função `listar()`
- [desperta/auth/cli.py:32](../../desperta/auth/cli.py#L32) função `init_app(app)`

### `desperta/auth/models.py` (73 linhas)
- [desperta/auth/models.py:17](../../desperta/auth/models.py#L17) classe `Administrador`
- [desperta/auth/models.py:60](../../desperta/auth/models.py#L60) função `Administrador.set_senha(self, senha)`
- [desperta/auth/models.py:63](../../desperta/auth/models.py#L63) função `Administrador.confere_senha(self, senha)`
- [desperta/auth/models.py:69](../../desperta/auth/models.py#L69) função `Administrador.__repr__(self)`

### `desperta/auth/routes.py` (73 linhas)
- [desperta/auth/routes.py:14](../../desperta/auth/routes.py#L14) função `login()`
- [desperta/auth/routes.py:22](../../desperta/auth/routes.py#L22) função `logout()`
- [desperta/auth/routes.py:29](../../desperta/auth/routes.py#L29) função `eu()`
- [desperta/auth/routes.py:35](../../desperta/auth/routes.py#L35) função `trocar_senha()`
- [desperta/auth/routes.py:48](../../desperta/auth/routes.py#L48) função `listar_equipe()`
- [desperta/auth/routes.py:54](../../desperta/auth/routes.py#L54) função `criar_membro()`
- [desperta/auth/routes.py:68](../../desperta/auth/routes.py#L68) função `editar_membro(admin_id)`

### `desperta/auth/services.py` (298 linhas)
Regras do cadastro e do login da equipe.
- [desperta/auth/services.py:43](../../desperta/auth/services.py#L43) função `_agora()`
- [desperta/auth/services.py:50](../../desperta/auth/services.py#L50) função `_nome_valido(nome)`
- [desperta/auth/services.py:59](../../desperta/auth/services.py#L59) função `_email_valido(email)`
- [desperta/auth/services.py:68](../../desperta/auth/services.py#L68) função `_papel_valido(papel)`
- [desperta/auth/services.py:74](../../desperta/auth/services.py#L74) função `_senha_valida(senha)`
- [desperta/auth/services.py:82](../../desperta/auth/services.py#L82) função `_ativo_valido(ativo)`
- [desperta/auth/services.py:88](../../desperta/auth/services.py#L88) função `_email_livre(email, menos_id)`
- [desperta/auth/services.py:96](../../desperta/auth/services.py#L96) função `_admins_ativos(menos_id)`
- [desperta/auth/services.py:101](../../desperta/auth/services.py#L101) função `_registrar(acao, descricao, por, alvo, nivel)`
- [desperta/auth/services.py:115](../../desperta/auth/services.py#L115) função `_gravar()`
- [desperta/auth/services.py:126](../../desperta/auth/services.py#L126) função `como_dict(admin)`: O que a API mostra de alguem da equipe; nunca a senha_hash.
- [desperta/auth/services.py:144](../../desperta/auth/services.py#L144) função `listar_equipe()`: Ativos primeiro, depois por nome.
- [desperta/auth/services.py:150](../../desperta/auth/services.py#L150) função `buscar_administrador(admin_id)`
- [desperta/auth/services.py:160](../../desperta/auth/services.py#L160) função `criar_administrador(nome, email, senha, papel, por)`
- [desperta/auth/services.py:172](../../desperta/auth/services.py#L172) função `editar_cadastro(admin, nome, email, papel, ativo, senha, por)`: Muda so o que foi passado; atualizado_em muda so se algo mudou de verdade.
- [desperta/auth/services.py:206](../../desperta/auth/services.py#L206) função `desativar(admin, por)`: Quem sai da equipe perde o acesso, mas o historico continua ligado a ele.
- [desperta/auth/services.py:211](../../desperta/auth/services.py#L211) função `trocar_propria_senha(admin, senha_atual, senha_nova)`
- [desperta/auth/services.py:217](../../desperta/auth/services.py#L217) função `excluir_administrador(admin)`
- [desperta/auth/services.py:230](../../desperta/auth/services.py#L230) função `_recentes(chave, janela_s, agora)`
- [desperta/auth/services.py:237](../../desperta/auth/services.py#L237) função `_bloqueado(email, ip)`
- [desperta/auth/services.py:248](../../desperta/auth/services.py#L248) função `_anotar_falha(email, ip)`
- [desperta/auth/services.py:255](../../desperta/auth/services.py#L255) função `_esquecer_falhas(email)`
- [desperta/auth/services.py:260](../../desperta/auth/services.py#L260) função `limpar_tentativas()`: Para os testes e para o admin destravar alguem pelo flask shell.
- [desperta/auth/services.py:269](../../desperta/auth/services.py#L269) função `autenticar(email, senha, ip)`: Devolve o administrador ou levanta NaoAutenticado / MuitasTentativas.
- [desperta/auth/services.py:294](../../desperta/auth/services.py#L294) função `registrar_acesso(admin)`: Login: so ultimo_acesso; atualizado_em fica como esta.

### `desperta/auth/sessao.py` (82 linhas)
Sessao da equipe (cookie assinado pelo Flask com a SECRET_KEY).
- [desperta/auth/sessao.py:24](../../desperta/auth/sessao.py#L24) função `_marca_da_senha(admin)`
- [desperta/auth/sessao.py:28](../../desperta/auth/sessao.py#L28) função `entrar(admin)`
- [desperta/auth/sessao.py:36](../../desperta/auth/sessao.py#L36) função `sair()`
- [desperta/auth/sessao.py:41](../../desperta/auth/sessao.py#L41) função `admin_atual()`: Quem esta logado, ou None. Sessao de quem foi desativado ou trocou a senha e apagada.
- [desperta/auth/sessao.py:56](../../desperta/auth/sessao.py#L56) função `renovar(admin)`: Depois de trocar a propria senha, a sessao atual continua valendo.
- [desperta/auth/sessao.py:64](../../desperta/auth/sessao.py#L64) função `login_obrigatorio(rota)`
- [desperta/auth/sessao.py:74](../../desperta/auth/sessao.py#L74) função `so_admin(rota)`

### `desperta/coletor/__init__.py` (12 linhas)

### `desperta/coletor/blocos.py` (79 linhas)
- [desperta/coletor/blocos.py:8](../../desperta/coletor/blocos.py#L8) função `_partidos_da_legislatura(execucao, id_legislatura, cache)`: Sigla -> ids, so nos partidos daquela legislatura: a sigla sozinha nao e unica.
- [desperta/coletor/blocos.py:19](../../desperta/coletor/blocos.py#L19) função `_id_do_partido(execucao, referencias, id_bloco, id_legislatura, item, cache)`: Decisao 12.3: a API devolve em /blocos/{id}/partidos o id do bloco no lugar do id do partido. Nesse caso, procura pela sigla entre os partidos da legislatura...
- [desperta/coletor/blocos.py:39](../../desperta/coletor/blocos.py#L39) função `_coletar_um(execucao, referencias, item, cache)`
- [desperta/coletor/blocos.py:73](../../desperta/coletor/blocos.py#L73) função `coletar(cliente, id_legislatura)`

### `desperta/coletor/cli.py` (362 linhas)
- [desperta/coletor/cli.py:22](../../desperta/coletor/cli.py#L22) função `_cliente()`
- [desperta/coletor/cli.py:26](../../desperta/coletor/cli.py#L26) função `_caminho_trava()`
- [desperta/coletor/cli.py:30](../../desperta/coletor/cli.py#L30) função `_avisar(acao, descricao)`
- [desperta/coletor/cli.py:40](../../desperta/coletor/cli.py#L40) função `_trava_da_coleta(nome, esperar_s)`: Decisoes 12.1 e 13.6: uma coleta por vez. Com outra rodando, espera ate esperar_s segundos; se ela nao terminar, devolve False e deixa um aviso no log.
- [desperta/coletor/cli.py:67](../../desperta/coletor/cli.py#L67) função `_uma_coleta_por_vez(funcao)`: Com outra coleta rodando, este comando nao roda e deixa um aviso no log.
- [desperta/coletor/cli.py:79](../../desperta/coletor/cli.py#L79) função `_data(ctx, param, valor)`
- [desperta/coletor/cli.py:83](../../desperta/coletor/cli.py#L83) função `_janela(funcao)`
- [desperta/coletor/cli.py:88](../../desperta/coletor/cli.py#L88) função `_legislatura(funcao)`
- [desperta/coletor/cli.py:92](../../desperta/coletor/cli.py#L92) função `_tipo(inicio)`
- [desperta/coletor/cli.py:102](../../desperta/coletor/cli.py#L102) função `coletar_base(legislatura)`: Legislaturas, partidos, deputados, orgaos e temas.
- [desperta/coletor/cli.py:109](../../desperta/coletor/cli.py#L109) função `coletar_horaria()`: Votacoes e eventos (ontem e hoje) e proposicoes (1 dia), com limite de 20 minutos.
- [desperta/coletor/cli.py:116](../../desperta/coletor/cli.py#L116) função `coletar_diaria()`: Proposicoes dos ultimos 3 dias, pautas e votacoes pendentes.
- [desperta/coletor/cli.py:123](../../desperta/coletor/cli.py#L123) função `coletar_semanal()`: Varredura de 30 dias, tabelas de apoio, cargos em orgaos, Mesa, liderancas e blocos.
- [desperta/coletor/cli.py:130](../../desperta/coletor/cli.py#L130) função `coletar_mensal()`: Frentes.
- [desperta/coletor/cli.py:149](../../desperta/coletor/cli.py#L149) função `_agora_texto()`
- [desperta/coletor/cli.py:153](../../desperta/coletor/cli.py#L153) função `_resumo_das_coletas(depois_de_id)`
- [desperta/coletor/cli.py:169](../../desperta/coletor/cli.py#L169) função `coletar_agendada(rotina, esperar, sem_ia)`: Para o agendador: roda a rotina e, sob a mesma trava, indexa o que mudou e escreve os rascunhos novos.
- [desperta/coletor/cli.py:231](../../desperta/coletor/cli.py#L231) função `coletar_legislaturas()`
- [desperta/coletor/cli.py:237](../../desperta/coletor/cli.py#L237) função `coletar_temas()`
- [desperta/coletor/cli.py:243](../../desperta/coletor/cli.py#L243) função `coletar_orgaos()`
- [desperta/coletor/cli.py:250](../../desperta/coletor/cli.py#L250) função `coletar_partidos(legislatura)`
- [desperta/coletor/cli.py:258](../../desperta/coletor/cli.py#L258) função `coletar_deputados(legislatura)`
- [desperta/coletor/cli.py:268](../../desperta/coletor/cli.py#L268) função `coletar_proposicoes(inicio, fim, sigla_tipo, limite_pendentes)`
- [desperta/coletor/cli.py:277](../../desperta/coletor/cli.py#L277) função `coletar_eventos(inicio, fim)`
- [desperta/coletor/cli.py:284](../../desperta/coletor/cli.py#L284) função `coletar_eventos_pendentes(limite)`
- [desperta/coletor/cli.py:291](../../desperta/coletor/cli.py#L291) função `coletar_votacoes(inicio, fim)`
- [desperta/coletor/cli.py:298](../../desperta/coletor/cli.py#L298) função `coletar_membros(limite)`
- [desperta/coletor/cli.py:305](../../desperta/coletor/cli.py#L305) função `coletar_mesa(legislatura)`
- [desperta/coletor/cli.py:313](../../desperta/coletor/cli.py#L313) função `coletar_liderancas(legislatura)`
- [desperta/coletor/cli.py:321](../../desperta/coletor/cli.py#L321) função `coletar_blocos(legislatura)`
- [desperta/coletor/cli.py:329](../../desperta/coletor/cli.py#L329) função `coletar_frentes(legislatura)`
- [desperta/coletor/cli.py:338](../../desperta/coletor/cli.py#L338) função `coletar_relatorio()`: Colunas que falharam e instabilidade da API, a partir de coleta e log_sistema.
- [desperta/coletor/cli.py:361](../../desperta/coletor/cli.py#L361) função `init_app(app)`

### `desperta/coletor/cliente.py` (89 linhas)
- [desperta/coletor/cliente.py:9](../../desperta/coletor/cliente.py#L9) classe `ErroAPI`: A API nao respondeu com sucesso, mesmo depois das novas tentativas.
- [desperta/coletor/cliente.py:12](../../desperta/coletor/cliente.py#L12) função `ErroAPI.__init__(self, url, mensagem, status)`
- [desperta/coletor/cliente.py:18](../../desperta/coletor/cliente.py#L18) classe `TempoEsgotado`: O orcamento de tempo da rotina acabou. Nao e falha da API: o resto fica para a proxima coleta.
- [desperta/coletor/cliente.py:23](../../desperta/coletor/cliente.py#L23) classe `ClienteCamara`
- [desperta/coletor/cliente.py:24](../../desperta/coletor/cliente.py#L24) função `ClienteCamara.__init__(self, url_base, timeout, esperas, sessao, dormir, relogio)`
- [desperta/coletor/cliente.py:38](../../desperta/coletor/cliente.py#L38) função `ClienteCamara.definir_orcamento(self, segundos)`: A partir daqui, nenhuma chamada comeca depois de passar esse tempo; None tira o limite.
- [desperta/coletor/cliente.py:42](../../desperta/coletor/cliente.py#L42) função `ClienteCamara._conferir_orcamento(self)`
- [desperta/coletor/cliente.py:46](../../desperta/coletor/cliente.py#L46) função `ClienteCamara._chamar(self, url, params)`: Faz a chamada e devolve o JSON; repete em 429, 5xx, timeout e queda de conexao.
- [desperta/coletor/cliente.py:77](../../desperta/coletor/cliente.py#L77) função `ClienteCamara.obter(self, caminho, params)`: Chamada simples: devolve o conteudo de "dados".
- [desperta/coletor/cliente.py:81](../../desperta/coletor/cliente.py#L81) função `ClienteCamara.paginar(self, caminho, params)`: Percorre as paginas seguindo o link "next" e devolve cada item.

### `desperta/coletor/deputados.py` (88 linhas)
- [desperta/coletor/deputados.py:9](../../desperta/coletor/deputados.py#L9) função `_valores(id_deputado, dados, sexo)`
- [desperta/coletor/deputados.py:27](../../desperta/coletor/deputados.py#L27) função `_manter_legislatura_mais_nova(registro, valores)`: O mesmo id aparece em varias legislaturas: legislatura e partido so trocam pela mais nova.
- [desperta/coletor/deputados.py:39](../../desperta/coletor/deputados.py#L39) função `gravar_listagem(execucao, item, sexo)`
- [desperta/coletor/deputados.py:45](../../desperta/coletor/deputados.py#L45) função `gravar_detalhe(execucao, item)`: Recebe o item de /deputados/{id}, usado quando o deputado nao veio na listagem.
- [desperta/coletor/deputados.py:55](../../desperta/coletor/deputados.py#L55) função `_gravar_pagina_lida(execucao, cliente, itens, sexo)`: A listagem por legislatura traz o mesmo deputado uma vez por partido em que ele esteve. Gravar as duas linhas trocava o partido a cada coleta; nesse caso val...
- [desperta/coletor/deputados.py:75](../../desperta/coletor/deputados.py#L75) função `coletar(cliente, id_legislatura)`

### `desperta/coletor/eventos.py` (144 linhas)
- [desperta/coletor/eventos.py:19](../../desperta/coletor/eventos.py#L19) função `gravar_evento(execucao, item, referencias)`: Recebe o item de /eventos/{id}; todos os orgaos da lista sao cadastrados (D5).
- [desperta/coletor/eventos.py:44](../../desperta/coletor/eventos.py#L44) função `_votacao_do_mesmo_evento(id_evento, uri_votacao)`: A votacao entra depois do evento: se ainda nao existe, a pauta e refeita quando ela chegar.
- [desperta/coletor/eventos.py:51](../../desperta/coletor/eventos.py#L51) função `_agrupar_por_ordem(itens)`: A API repete o item com o mesmo ordem, uma linha por votacao; a PK guarda uma linha por item.
- [desperta/coletor/eventos.py:59](../../desperta/coletor/eventos.py#L59) função `_gravar_pauta(execucao, referencias, id_evento)`
- [desperta/coletor/eventos.py:95](../../desperta/coletor/eventos.py#L95) função `_coletar_um(execucao, referencias, id_evento)`
- [desperta/coletor/eventos.py:103](../../desperta/coletor/eventos.py#L103) função `_ids_para_recoletar(hoje_utc, ja_vistos, limite)`: Pauta pendente (nulo) e eventos recentes que ainda nao foram encerrados.
- [desperta/coletor/eventos.py:121](../../desperta/coletor/eventos.py#L121) função `coletar(cliente, inicio, fim, tipo, limite_pendentes)`
- [desperta/coletor/eventos.py:134](../../desperta/coletor/eventos.py#L134) função `coletar_pendentes(cliente, limite)`: Refaz as pautas pendentes, por exemplo depois de chegarem votacoes novas do evento.

### `desperta/coletor/execucao.py` (287 linhas)
- [desperta/coletor/execucao.py:25](../../desperta/coletor/execucao.py#L25) classe `Execucao`
- [desperta/coletor/execucao.py:26](../../desperta/coletor/execucao.py#L26) função `Execucao.__init__(self, cliente, recurso, tipo, endpoint, parametros, data_inicio_ref, data_fim_ref)`
- [desperta/coletor/execucao.py:50](../../desperta/coletor/execucao.py#L50) função `Execucao.__enter__(self)`
- [desperta/coletor/execucao.py:53](../../desperta/coletor/execucao.py#L53) função `Execucao.__exit__(self, tipo_erro, erro, rastro)`
- [desperta/coletor/execucao.py:74](../../desperta/coletor/execucao.py#L74) função `Execucao._proteger(self, modelo, chave, gravar)`: Cada registro em begin_nested: se falhar, desfaz so ele, registra e segue (decisao 10.2).
- [desperta/coletor/execucao.py:83](../../desperta/coletor/execucao.py#L83) função `Execucao.registrar_falha(self, tabela, chave, erro)`
- [desperta/coletor/execucao.py:88](../../desperta/coletor/execucao.py#L88) função `Execucao.principal(self, modelo, chave, valores, ajustar)`: Upsert de registro principal pelo hash_origem: novo conta em itens_novos, hash diferente em itens_atualizados, igual so marca sincronizado_em. ajustar(regist...
- [desperta/coletor/execucao.py:107](../../desperta/coletor/execucao.py#L107) função `Execucao._upsert_principal(self, modelo, chave, valores, ajustar)`
- [desperta/coletor/execucao.py:134](../../desperta/coletor/execucao.py#L134) função `Execucao.vinculo(self, modelo, chave, valores)`: Upsert de linha filha ou associativa; devolve True se gravou.
- [desperta/coletor/execucao.py:146](../../desperta/coletor/execucao.py#L146) função `Execucao._upsert_vinculo(self, modelo, chave, valores)`
- [desperta/coletor/execucao.py:161](../../desperta/coletor/execucao.py#L161) função `Execucao.remover_sumidos(self, modelo, *filtros)`: Apaga as linhas daquele pai que nao vieram nesta coleta (sincronizado_em anterior ao inicio).
- [desperta/coletor/execucao.py:168](../../desperta/coletor/execucao.py#L168) função `Execucao.log(self, nivel, acao, descricao, entidade, entidade_id)`
- [desperta/coletor/execucao.py:183](../../desperta/coletor/execucao.py#L183) função `Execucao.processar(self, tabela, chave, funcao)`: Processa um item pai: erro de API desse item nao derruba a coleta, mas varias falhas seguidas indicam que a API caiu, e a coleta para. Item que a Camara nao ...
- [desperta/coletor/execucao.py:214](../../desperta/coletor/execucao.py#L214) função `Execucao._ausentes_desde_ha_pouco(self, tabela)`: Ids desta tabela que deram 404 dentro do prazo; lido uma vez por coleta.
- [desperta/coletor/execucao.py:233](../../desperta/coletor/execucao.py#L233) função `Execucao._registrar_ausente(self, tabela, chave, erro)`
- [desperta/coletor/execucao.py:240](../../desperta/coletor/execucao.py#L240) função `Execucao.concluir_item(self)`: Fecha a transacao a cada item, para nao segurar o SQLite durante as chamadas HTTP.
- [desperta/coletor/execucao.py:245](../../desperta/coletor/execucao.py#L245) função `Execucao.atualizar_contadores(self)`
- [desperta/coletor/execucao.py:249](../../desperta/coletor/execucao.py#L249) função `Execucao.finalizar(self, status, mensagem)`
- [desperta/coletor/execucao.py:271](../../desperta/coletor/execucao.py#L271) função `_item_nao_existe(erro, chave)`: 404 no detalhe do proprio item (a URL termina no id), e nao num filho como /pauta ou /votos.
- [desperta/coletor/execucao.py:280](../../desperta/coletor/execucao.py#L280) função `_id_texto(chave)`

### `desperta/coletor/frentes.py` (51 linhas)
- [desperta/coletor/frentes.py:8](../../desperta/coletor/frentes.py#L8) função `_coletar_uma(execucao, referencias, id_frente)`
- [desperta/coletor/frentes.py:46](../../desperta/coletor/frentes.py#L46) função `coletar(cliente, id_legislatura)`

### `desperta/coletor/janelas.py` (35 linhas)
- [desperta/coletor/janelas.py:11](../../desperta/coletor/janelas.py#L11) função `janela_incremental(recurso, hoje)`: A proxima janela comeca na ultima janela ok do recurso, com 1 dia de sobreposicao.
- [desperta/coletor/janelas.py:25](../../desperta/coletor/janelas.py#L25) função `dividir_janela(inicio, fim)`: /proposicoes e /votacoes recusam (HTTP 400) janelas maiores que 3 meses; /votacoes tambem exige dataInicio e dataFim no mesmo ano.

### `desperta/coletor/legislaturas.py` (26 linhas)
- [desperta/coletor/legislaturas.py:9](../../desperta/coletor/legislaturas.py#L9) função `coletar(cliente)`
- [desperta/coletor/legislaturas.py:24](../../desperta/coletor/legislaturas.py#L24) função `id_atual(cliente, hoje)`

### `desperta/coletor/liderancas.py` (33 linhas)
- [desperta/coletor/liderancas.py:8](../../desperta/coletor/liderancas.py#L8) função `coletar(cliente, id_legislatura)`

### `desperta/coletor/normalizacao.py` (72 linhas)
- [desperta/coletor/normalizacao.py:7](../../desperta/coletor/normalizacao.py#L7) função `agora_utc()`: Colunas tecnicas ficam em UTC, sem fuso (ver desperta/ext/db/mixins.py).
- [desperta/coletor/normalizacao.py:12](../../desperta/coletor/normalizacao.py#L12) função `id_da_uri(uri, recurso)`: Extrai o id final de uma uri; com recurso, so aceita uri daquele recurso (ex.: deputados).
- [desperta/coletor/normalizacao.py:21](../../desperta/coletor/normalizacao.py#L21) função `id_texto_da_uri(uri)`: Id de votacao e texto, ex.: .../votacoes/2310837-8.
- [desperta/coletor/normalizacao.py:28](../../desperta/coletor/normalizacao.py#L28) função `opcional(valor)`: Coluna de texto opcional: vazio vira None.
- [desperta/coletor/normalizacao.py:35](../../desperta/coletor/normalizacao.py#L35) função `para_int(valor)`: Ids e codigos que a API manda como texto.
- [desperta/coletor/normalizacao.py:42](../../desperta/coletor/normalizacao.py#L42) função `para_texto(valor)`: Codigos que vem como numero ou texto (cod_titulo, por exemplo) ficam em texto.
- [desperta/coletor/normalizacao.py:47](../../desperta/coletor/normalizacao.py#L47) função `para_bool(valor)`: Campos 0/1 ou booleanos da API; ausente continua None.
- [desperta/coletor/normalizacao.py:56](../../desperta/coletor/normalizacao.py#L56) função `para_data_hora(valor)`: Datas da Camara: horario de Brasilia, sem fuso, como a API manda.
- [desperta/coletor/normalizacao.py:63](../../desperta/coletor/normalizacao.py#L63) função `para_data(valor)`
- [desperta/coletor/normalizacao.py:69](../../desperta/coletor/normalizacao.py#L69) função `calcular_hash(valores)`: SHA-256 dos valores que vao para as colunas do modelo, com chaves ordenadas.

### `desperta/coletor/orgaos.py` (93 linhas)
- [desperta/coletor/orgaos.py:11](../../desperta/coletor/orgaos.py#L11) função `gravar_orgao(execucao, item)`: Serve para /orgaos, /orgaos/{id} e para a lista orgaos[] de /eventos (D5).
- [desperta/coletor/orgaos.py:27](../../desperta/coletor/orgaos.py#L27) função `coletar(cliente)`
- [desperta/coletor/orgaos.py:34](../../desperta/coletor/orgaos.py#L34) função `_gravar_membro(execucao, referencias, id_orgao, item)`: Devolve True se a linha foi gravada.
- [desperta/coletor/orgaos.py:54](../../desperta/coletor/orgaos.py#L54) função `_coletar_membros_do_orgao(execucao, referencias, orgao)`: Vinculos que sumiram da API saem do banco; se alguma linha falhou, nada e apagado.
- [desperta/coletor/orgaos.py:64](../../desperta/coletor/orgaos.py#L64) função `coletar_membros(cliente, limite, ids)`: Pendentes (nulo) primeiro, depois os sincronizados ha mais tempo.
- [desperta/coletor/orgaos.py:83](../../desperta/coletor/orgaos.py#L83) função `coletar_mesa(cliente, id_legislatura)`: A Mesa e o orgao 4, com membros vindos de /legislaturas/{id}/mesa.

### `desperta/coletor/partidos.py` (29 linhas)
- [desperta/coletor/partidos.py:7](../../desperta/coletor/partidos.py#L7) função `gravar_partido(execucao, item)`: Recebe o item de /partidos/{id}, que traz urlLogo.
- [desperta/coletor/partidos.py:21](../../desperta/coletor/partidos.py#L21) função `coletar(cliente, id_legislatura)`

### `desperta/coletor/persistencia.py` (300 linhas)
- [desperta/coletor/persistencia.py:32](../../desperta/coletor/persistencia.py#L32) classe `ClienteSemRede`: A Execucao conta as requisicoes do cliente; aqui nenhuma chamada a API e feita.
- [desperta/coletor/persistencia.py:39](../../desperta/coletor/persistencia.py#L39) função `_proposicao_de_teste(id_, **campos)`
- [desperta/coletor/persistencia.py:60](../../desperta/coletor/persistencia.py#L60) função `_valores_do_registro(registro)`
- [desperta/coletor/persistencia.py:68](../../desperta/coletor/persistencia.py#L68) função `_ida_e_volta(caminho)`: Grava, fecha a conexao, abre de novo e compara: texto, datas, nulos, booleano, texto como id e bytes.
- [desperta/coletor/persistencia.py:135](../../desperta/coletor/persistencia.py#L135) função `_upsert_sem_duplicar()`: Regravar registros reais iguais nao cria linha nova nem marca como atualizado (RNF06).
- [desperta/coletor/persistencia.py:159](../../desperta/coletor/persistencia.py#L159) função `_atualizacao()`: Conteudo mudado: a linha e atualizada no lugar, com hash e atualizado_em novos.
- [desperta/coletor/persistencia.py:180](../../desperta/coletor/persistencia.py#L180) função `_isolamento_de_erro()`: Um registro com campo obrigatorio vazio nao derruba os outros (decisao 10.2).
- [desperta/coletor/persistencia.py:200](../../desperta/coletor/persistencia.py#L200) função `_restricoes()`
- [desperta/coletor/persistencia.py:239](../../desperta/coletor/persistencia.py#L239) função `_tema()`
- [desperta/coletor/persistencia.py:243](../../desperta/coletor/persistencia.py#L243) função `_cascata()`
- [desperta/coletor/persistencia.py:278](../../desperta/coletor/persistencia.py#L278) função `testar_persistencia(caminho)`: Roda os casos em ordem; caminho e o arquivo da copia, ja ligado a db.session.

### `desperta/coletor/proposicoes.py` (204 linhas)
- [desperta/coletor/proposicoes.py:14](../../desperta/coletor/proposicoes.py#L14) função `gravar_proposicao(execucao, item, referencias)`: Recebe o item de /proposicoes/{id}, com statusProposicao achatado.
- [desperta/coletor/proposicoes.py:41](../../desperta/coletor/proposicoes.py#L41) função `_gravar_autores(execucao, referencias, id_proposicao, itens)`
- [desperta/coletor/proposicoes.py:60](../../desperta/coletor/proposicoes.py#L60) função `_gravar_temas(execucao, id_proposicao, itens)`
- [desperta/coletor/proposicoes.py:83](../../desperta/coletor/proposicoes.py#L83) função `_gravar_tramitacoes(execucao, referencias, id_proposicao, itens)`
- [desperta/coletor/proposicoes.py:108](../../desperta/coletor/proposicoes.py#L108) função `_precisa_dos_filhos(id_proposicao, item)`: Decisao 12.1: filhos so para proposicao nova, pendente ou com data_status diferente.
- [desperta/coletor/proposicoes.py:116](../../desperta/coletor/proposicoes.py#L116) função `_coletar_uma(execucao, referencias, id_proposicao)`: Grava a proposicao so depois do detalhe; a listagem serve apenas para descobrir ids.
- [desperta/coletor/proposicoes.py:144](../../desperta/coletor/proposicoes.py#L144) função `_ids_pendentes(limite, tipos, ja_vistos)`: So dos tipos acompanhados: os demais entram sem filhos, citados por votacao ou pauta.
- [desperta/coletor/proposicoes.py:159](../../desperta/coletor/proposicoes.py#L159) função `_ja_conferidas(ids, intervalo)`: Decisao 14.2: conferidas ha pouco. Pendente nao entra: ainda faltam os filhos dela.
- [desperta/coletor/proposicoes.py:170](../../desperta/coletor/proposicoes.py#L170) função `coletar(cliente, inicio, fim, sigla_tipo, tipo, limite_pendentes, pular_conferidas_ha)`

### `desperta/coletor/referencias.py` (72 linhas)
- [desperta/coletor/referencias.py:10](../../desperta/coletor/referencias.py#L10) classe `Referencias`
- [desperta/coletor/referencias.py:11](../../desperta/coletor/referencias.py#L11) função `Referencias.__init__(self, execucao)`
- [desperta/coletor/referencias.py:17](../../desperta/coletor/referencias.py#L17) função `Referencias._garantir(self, modelo, id_registro, caminho, gravar)`: Devolve o id se o registro existe ou se conseguiu trazer da API; senao, None.
- [desperta/coletor/referencias.py:45](../../desperta/coletor/referencias.py#L45) função `Referencias.deputado(self, id_deputado)`
- [desperta/coletor/referencias.py:50](../../desperta/coletor/referencias.py#L50) função `Referencias.orgao(self, id_orgao)`
- [desperta/coletor/referencias.py:55](../../desperta/coletor/referencias.py#L55) função `Referencias.partido(self, id_partido)`
- [desperta/coletor/referencias.py:60](../../desperta/coletor/referencias.py#L60) função `Referencias.proposicao(self, id_proposicao)`: So o registro principal: filhos_sincronizados_em fica nulo e entra nos pendentes.
- [desperta/coletor/referencias.py:68](../../desperta/coletor/referencias.py#L68) função `Referencias.evento(self, id_evento)`: So o registro principal: a pauta entra nos pendentes.

### `desperta/coletor/relatorio.py` (124 linhas)
- [desperta/coletor/relatorio.py:16](../../desperta/coletor/relatorio.py#L16) função `_eh_falha_da_api(descricao)`
- [desperta/coletor/relatorio.py:20](../../desperta/coletor/relatorio.py#L20) função `falhas_por_coluna()`: Para a carga de validacao: colunas que falharam e quantas vezes (decisao 10.2).
- [desperta/coletor/relatorio.py:34](../../desperta/coletor/relatorio.py#L34) função `textos_vazios_obrigatorios()`: Decisao 14.1: a API manda '' em colunas obrigatorias e isso nao falha no NOT NULL. Fica gravado como veio; aqui so conta, por coluna, para aparecer no relato...
- [desperta/coletor/relatorio.py:50](../../desperta/coletor/relatorio.py#L50) função `falhas_da_api()`: Falhas que nao dizem nada sobre as colunas: a API nao respondeu, por endpoint e motivo.
- [desperta/coletor/relatorio.py:61](../../desperta/coletor/relatorio.py#L61) função `proposicoes_pendentes()`: Decisao 13.5: proposicoes dos tipos acompanhados sem filhos, e quantas delas tiveram falha em mais de uma coleta. Uma falha repetida nao se resolve sozinha.
- [desperta/coletor/relatorio.py:89](../../desperta/coletor/relatorio.py#L89) função `resumo_por_recurso()`: Requisicoes, erros HTTP e itens por recurso, em todas as coletas.
- [desperta/coletor/relatorio.py:105](../../desperta/coletor/relatorio.py#L105) função `blocos_com_id_errado()`: Decisao 12.3: blocos com id errado em /blocos/{id}/partidos e siglas que nao ligaram.
- [desperta/coletor/relatorio.py:117](../../desperta/coletor/relatorio.py#L117) função `avisos_por_tipo()`: Avisos do coletor, como referencia ausente e item de pauta repetido.

### `desperta/coletor/rotinas.py` (76 linhas)
- [desperta/coletor/rotinas.py:26](../../desperta/coletor/rotinas.py#L26) função `base(cliente, id_legislatura)`: Tabelas de apoio, na ordem das FKs.
- [desperta/coletor/rotinas.py:37](../../desperta/coletor/rotinas.py#L37) função `horaria(cliente, hoje)`: Votacoes e eventos de ontem e hoje; por ultimo, proposicoes dos tipos acompanhados com janela de 1 dia. Ao fim do orcamento, a coleta em andamento e as segui...
- [desperta/coletor/rotinas.py:55](../../desperta/coletor/rotinas.py#L55) função `diaria(cliente, hoje)`: Proposicoes dos ultimos 3 dias, pautas pendentes e votacoes pendentes.
- [desperta/coletor/rotinas.py:63](../../desperta/coletor/rotinas.py#L63) função `semanal(cliente, hoje)`: Varredura de 30 dias, cargos em orgaos, Mesa, liderancas e blocos.
- [desperta/coletor/rotinas.py:74](../../desperta/coletor/rotinas.py#L74) função `mensal(cliente)`: Frentes.

### `desperta/coletor/temas.py` (22 linhas)
- [desperta/coletor/temas.py:9](../../desperta/coletor/temas.py#L9) função `coletar(cliente)`

### `desperta/coletor/trava.py` (80 linhas)
- [desperta/coletor/trava.py:10](../../desperta/coletor/trava.py#L10) função `_agora()`
- [desperta/coletor/trava.py:14](../../desperta/coletor/trava.py#L14) função `_processo_existe(pid)`
- [desperta/coletor/trava.py:25](../../desperta/coletor/trava.py#L25) função `_motivo_abandono(caminho, agora)`: Devolve por que a trava esta abandonada, ou None se ela ainda vale.
- [desperta/coletor/trava.py:42](../../desperta/coletor/trava.py#L42) função `adquirir(caminho, agora, ao_abandonar)`: Cria a trava em arquivo; devolve False se outra coleta esta rodando. ao_abandonar(motivo) e chamada quando uma trava abandonada e removida.
- [desperta/coletor/trava.py:67](../../desperta/coletor/trava.py#L67) função `liberar(caminho)`
- [desperta/coletor/trava.py:74](../../desperta/coletor/trava.py#L74) função `_encerrar(numero, quadro)`
- [desperta/coletor/trava.py:78](../../desperta/coletor/trava.py#L78) função `sair_limpo_em_sigterm()`: Com SIGTERM (timeout, kill), a coleta fecha o registro e libera a trava antes de sair.

### `desperta/coletor/votacoes.py` (140 linhas)
- [desperta/coletor/votacoes.py:14](../../desperta/coletor/votacoes.py#L14) função `_gravar_votacao(execucao, referencias, item)`
- [desperta/coletor/votacoes.py:35](../../desperta/coletor/votacoes.py#L35) função `_gravar_votos(execucao, referencias, id_votacao)`
- [desperta/coletor/votacoes.py:55](../../desperta/coletor/votacoes.py#L55) função `_gravar_orientacoes(execucao, id_votacao)`
- [desperta/coletor/votacoes.py:76](../../desperta/coletor/votacoes.py#L76) função `_gravar_afetadas(execucao, referencias, votacao, afetadas)`
- [desperta/coletor/votacoes.py:93](../../desperta/coletor/votacoes.py#L93) função `_coletar_uma(execucao, referencias, item)`
- [desperta/coletor/votacoes.py:113](../../desperta/coletor/votacoes.py#L113) função `coletar(cliente, inicio, fim, tipo)`
- [desperta/coletor/votacoes.py:124](../../desperta/coletor/votacoes.py#L124) função `coletar_pendentes(cliente, limite)`: Votacoes sem votos e orientacoes, por exemplo depois de uma falha da API.

### `desperta/ext/__init__.py` (0 linhas)

### `desperta/ext/api/__init__.py` (120 linhas)
Auxiliares HTTP comuns as rotas: corpo JSON, parametros da URL, paginas e datas.
- [desperta/ext/api/__init__.py:19](../../desperta/ext/api/__init__.py#L19) função `corpo_json(obrigatorio)`: Corpo da requisicao como dicionario. Exigir JSON tambem protege as rotas que mudam dados: um formulario de outro site nao consegue mandar application/json se...
- [desperta/ext/api/__init__.py:34](../../desperta/ext/api/__init__.py#L34) função `parametro_int(nome, padrao, minimo, maximo)`
- [desperta/ext/api/__init__.py:47](../../desperta/ext/api/__init__.py#L47) função `parametro_texto(nome, tamanho)`
- [desperta/ext/api/__init__.py:54](../../desperta/ext/api/__init__.py#L54) função `pagina()`: (pagina, por_pagina) a partir de ?pagina= e ?por_pagina=.
- [desperta/ext/api/__init__.py:62](../../desperta/ext/api/__init__.py#L62) função `paginado(itens, total, pagina_atual, por_pagina)`
- [desperta/ext/api/__init__.py:72](../../desperta/ext/api/__init__.py#L72) função `iso(valor)`: Datas do portal (noticia, coleta, log, equipe): gravadas em UTC, saem com o 'Z'.
- [desperta/ext/api/__init__.py:83](../../desperta/ext/api/__init__.py#L83) função `iso_camara(valor)`: Datas da Camara (proposicao, tramitacao, votacao): gravadas no horario de Brasilia, saem com -03:00.
- [desperta/ext/api/__init__.py:90](../../desperta/ext/api/__init__.py#L90) função `periodo_em_utc(dia, mes, ano)`: Filtro por dia, mes e ano em horario de Brasilia, convertido para UTC (Fase 4): publicado_em esta em UTC, e sem a conversao uma noticia publicada a noite cai...
- [desperta/ext/api/__init__.py:119](../../desperta/ext/api/__init__.py#L119) função `url_camara(caminho)`

### `desperta/ext/cli/__init__.py` (126 linhas)
- [desperta/ext/cli/__init__.py:20](../../desperta/ext/cli/__init__.py#L20) função `_mostrar(resultados, titulo, relatorio, banco_usado)`: Mostra no terminal e, se pedido, grava um relatorio em Markdown; devolve quantas falharam.
- [desperta/ext/cli/__init__.py:52](../../desperta/ext/cli/__init__.py#L52) função `verificar(relatorio)`: Confere estrutura, integridade e coerencia dos dados, sem gravar nada.
- [desperta/ext/cli/__init__.py:60](../../desperta/ext/cli/__init__.py#L60) função `_copiar(origem, destino)`: Copia pelo backup do SQLite: inclui o que ainda esta no arquivo WAL.
- [desperta/ext/cli/__init__.py:76](../../desperta/ext/cli/__init__.py#L76) função `testar_persistencia(relatorio, manter_copia)`: Grava, rele, atualiza e apaga dados de teste numa COPIA do banco; o banco original nao muda.
- [desperta/ext/cli/__init__.py:106](../../desperta/ext/cli/__init__.py#L106) função `init_app(app)`

### `desperta/ext/cors/__init__.py` (13 linhas)
- [desperta/ext/cors/__init__.py:6](../../desperta/ext/cors/__init__.py#L6) função `init_app(app)`

### `desperta/ext/db/__init__.py` (60 linhas)
- [desperta/ext/db/__init__.py:25](../../desperta/ext/db/__init__.py#L25) função `init_app(app)`
- [desperta/ext/db/__init__.py:35](../../desperta/ext/db/__init__.py#L35) função `_configurar_sqlite(dbapi_connection, connection_record)`
- [desperta/ext/db/__init__.py:47](../../desperta/ext/db/__init__.py#L47) função `register_models()`: Importa todos os modulos que definem modelos para que sejam registrados no metadata do SQLAlchemy.

### `desperta/ext/db/busca.py` (200 linhas)
- [desperta/ext/db/busca.py:19](../../desperta/ext/db/busca.py#L19) função `_stemmer()`
- [desperta/ext/db/busca.py:28](../../desperta/ext/db/busca.py#L28) função `_sem_acento(texto)`
- [desperta/ext/db/busca.py:33](../../desperta/ext/db/busca.py#L33) função `_raizes_da_palavra(palavra)`: A raiz da palavra como foi escrita e a raiz dela sem acento, quando sao diferentes. O Snowball depende do acento ("vacinação" vira "vacin", mas "vacinacao" v...
- [desperta/ext/db/busca.py:45](../../desperta/ext/db/busca.py#L45) função `grupos_de_raizes(consulta)`: Uma tupla de raizes para cada palavra diferente da consulta, na ordem em que aparecem.
- [desperta/ext/db/busca.py:51](../../desperta/ext/db/busca.py#L51) função `raiz(texto)`: O texto em minusculas, com cada palavra trocada pelas suas raizes, sem acento (e o que o indice guarda).
- [desperta/ext/db/busca.py:58](../../desperta/ext/db/busca.py#L58) função `raizes_da_consulta(consulta)`: Todas as raizes das palavras da consulta, sem repetir.
- [desperta/ext/db/busca.py:63](../../desperta/ext/db/busca.py#L63) função `registrar_funcoes(conexao_dbapi)`: raiz() dentro do SQL serve so para refazer um indice inteiro (INSERT ... SELECT raiz(texto)).
- [desperta/ext/db/busca.py:68](../../desperta/ext/db/busca.py#L68) função `acompanhar_pela_raiz(modelo, tabela, colunas)`: Mantem o indice das raizes a cada gravacao do modelo feita pelo ORM. De proposito nao ha gatilho no banco chamando raiz(): com gatilho, uma versao do codigo ...
- [desperta/ext/db/busca.py:160](../../desperta/ext/db/busca.py#L160) função `criar_busca_texto(conexao)`
- [desperta/ext/db/busca.py:165](../../desperta/ext/db/busca.py#L165) função `remover_busca_texto(conexao)`
- [desperta/ext/db/busca.py:170](../../desperta/ext/db/busca.py#L170) função `preencher_busca_raiz(conexao)`: Refaz o indice das raizes a partir das noticias (para banco que ja tinha noticias).
- [desperta/ext/db/busca.py:181](../../desperta/ext/db/busca.py#L181) função `conferir_busca_raiz(conexao)`: Rede de seguranca: se o indice das raizes nao tem uma linha por noticia (noticias gravadas por uma versao do codigo que nao o mantinha), refaz o indice. Devo...
- [desperta/ext/db/busca.py:198](../../desperta/ext/db/busca.py#L198) função `remover_busca_raiz(conexao)`

### `desperta/ext/db/mixins.py` (35 linhas)
- [desperta/ext/db/mixins.py:20](../../desperta/ext/db/mixins.py#L20) classe `SincronizacaoMixin`
- [desperta/ext/db/mixins.py:34](../../desperta/ext/db/mixins.py#L34) classe `VinculoSincronizadoMixin`

### `desperta/ext/db/verificacao.py` (343 linhas)
- [desperta/ext/db/verificacao.py:53](../../desperta/ext/db/verificacao.py#L53) classe `Resultado`
- [desperta/ext/db/verificacao.py:60](../../desperta/ext/db/verificacao.py#L60) função `_valor(sql, **params)`
- [desperta/ext/db/verificacao.py:64](../../desperta/ext/db/verificacao.py#L64) função `_tabelas_do_banco()`
- [desperta/ext/db/verificacao.py:68](../../desperta/ext/db/verificacao.py#L68) função `_colunas(tabela)`
- [desperta/ext/db/verificacao.py:72](../../desperta/ext/db/verificacao.py#L72) função `_versao_mais_nova()`: A ultima migracao da pasta migrations do proprio projeto, e nao da pasta em que o comando roda.
- [desperta/ext/db/verificacao.py:88](../../desperta/ext/db/verificacao.py#L88) função `_estrutura()`
- [desperta/ext/db/verificacao.py:124](../../desperta/ext/db/verificacao.py#L124) função `_placares()`: Os votos gravados batem com o placar que a Camara escreve na descricao da votacao.
- [desperta/ext/db/verificacao.py:159](../../desperta/ext/db/verificacao.py#L159) função `_referencias_sem_fk()`
- [desperta/ext/db/verificacao.py:188](../../desperta/ext/db/verificacao.py#L188) função `_indices_de_busca()`
- [desperta/ext/db/verificacao.py:224](../../desperta/ext/db/verificacao.py#L224) função `_embeddings()`
- [desperta/ext/db/verificacao.py:235](../../desperta/ext/db/verificacao.py#L235) função `_periodos()`
- [desperta/ext/db/verificacao.py:246](../../desperta/ext/db/verificacao.py#L246) função `_sincronizacao()`
- [desperta/ext/db/verificacao.py:270](../../desperta/ext/db/verificacao.py#L270) função `_coletas()`
- [desperta/ext/db/verificacao.py:306](../../desperta/ext/db/verificacao.py#L306) função `_informacoes()`
- [desperta/ext/db/verificacao.py:332](../../desperta/ext/db/verificacao.py#L332) função `verificar_banco()`: Devolve a lista de resultados; nada e gravado.

### `desperta/ext/erros/__init__.py` (59 linhas)
Erros de regra de negocio que viram resposta HTTP com JSON (decisao 10.4).
- [desperta/ext/erros/__init__.py:10](../../desperta/ext/erros/__init__.py#L10) classe `ErroDoPortal`
- [desperta/ext/erros/__init__.py:13](../../desperta/ext/erros/__init__.py#L13) função `ErroDoPortal.__init__(self, mensagem)`
- [desperta/ext/erros/__init__.py:19](../../desperta/ext/erros/__init__.py#L19) classe `DadosInvalidos`
- [desperta/ext/erros/__init__.py:24](../../desperta/ext/erros/__init__.py#L24) classe `NaoAutenticado`
- [desperta/ext/erros/__init__.py:29](../../desperta/ext/erros/__init__.py#L29) classe `AcessoNegado`
- [desperta/ext/erros/__init__.py:34](../../desperta/ext/erros/__init__.py#L34) classe `NaoEncontrado`
- [desperta/ext/erros/__init__.py:39](../../desperta/ext/erros/__init__.py#L39) classe `Conflito`
- [desperta/ext/erros/__init__.py:44](../../desperta/ext/erros/__init__.py#L44) classe `MuitasTentativas`
- [desperta/ext/erros/__init__.py:47](../../desperta/ext/erros/__init__.py#L47) função `MuitasTentativas.__init__(self, mensagem, esperar_s)`
- [desperta/ext/erros/__init__.py:53](../../desperta/ext/erros/__init__.py#L53) função `init_app(app)`

### `desperta/ext/limite/__init__.py` (84 linhas)
Limite de requisicoes nas rotas da API (RNF10, decisao 25.4).
- [desperta/ext/limite/__init__.py:28](../../desperta/ext/limite/__init__.py#L28) classe `Contador`
- [desperta/ext/limite/__init__.py:29](../../desperta/ext/limite/__init__.py#L29) função `Contador.__init__(self)`
- [desperta/ext/limite/__init__.py:34](../../desperta/ext/limite/__init__.py#L34) função `Contador.passar(self, chave, limite, janela_s, agora)`: Anota a requisicao e devolve 0; acima do limite nao anota e devolve os segundos de espera.
- [desperta/ext/limite/__init__.py:48](../../desperta/ext/limite/__init__.py#L48) função `Contador._limpar(self, janela_s, agora)`
- [desperta/ext/limite/__init__.py:52](../../desperta/ext/limite/__init__.py#L52) função `Contador.zerar(self)`
- [desperta/ext/limite/__init__.py:57](../../desperta/ext/limite/__init__.py#L57) função `_da_equipe()`: Quem esta logado na area da equipe nao entra no limite; o cookie de sessao e assinado.
- [desperta/ext/limite/__init__.py:65](../../desperta/ext/limite/__init__.py#L65) função `_conferir()`
- [desperta/ext/limite/__init__.py:81](../../desperta/ext/limite/__init__.py#L81) função `init_app(app)`

### `desperta/ia/__init__.py` (7 linhas)
- [desperta/ia/__init__.py:5](../../desperta/ia/__init__.py#L5) função `init_app(app)`

### `desperta/ia/automatico.py` (298 linhas)
Item 4 da decisao 22.10: depois de cada coleta, os fatos novos viram rascunho sozinhos.
- [desperta/ia/automatico.py:39](../../desperta/ia/automatico.py#L39) classe `Resumo`
- [desperta/ia/automatico.py:56](../../desperta/ia/automatico.py#L56) função `Resumo.em_texto(self)`
- [desperta/ia/automatico.py:69](../../desperta/ia/automatico.py#L69) função `_acompanhadas()`
- [desperta/ia/automatico.py:73](../../desperta/ia/automatico.py#L73) função `_votacoes(inicio)`: Votacoes da janela que afetam uma proposicao acompanhada, no Plenario ou em comissao.
- [desperta/ia/automatico.py:87](../../desperta/ia/automatico.py#L87) função `_proposicoes(inicio)`: Situacao que mudou de verdade (25.1) depois do dia da apresentacao, e proposicao apresentada na janela.
- [desperta/ia/automatico.py:120](../../desperta/ia/automatico.py#L120) função `fatos_da_janela(inicio)`: (caso, ref, pendente) em ordem: votacoes primeiro, como na coleta (decisao 15.2).
- [desperta/ia/automatico.py:132](../../desperta/ia/automatico.py#L132) função `_entradas_feitas(refazer_erros)`: Fato que ja tem geracao nao e gerado de novo, nem quando a equipe rejeitou a noticia (o comando flask ia gerar continua podendo refazer a rejeitada, a mao).
- [desperta/ia/automatico.py:144](../../desperta/ia/automatico.py#L144) função `_tem_tema(proposicao_id)`
- [desperta/ia/automatico.py:148](../../desperta/ia/automatico.py#L148) função `atualizar_temas()`: Decisao 25.6: noticia no tema especial cuja proposicao ja ganhou tema da Camara passa para o tema principal (25.2). O texto nao muda: ele diz que, quando foi...
- [desperta/ia/automatico.py:191](../../desperta/ia/automatico.py#L191) função `gerar_novos(modelo, dias, limite, simular, refazer_erros, hoje)`: Gera os rascunhos dos fatos da janela. modelo None: so busca por palavras (21.3). simular=True nao grava nada: so diz o que seria gerado.
- [desperta/ia/automatico.py:264](../../desperta/ia/automatico.py#L264) função `carregar_modelo_ou_nada(qual)`: Decisao 21.3: sem o modelo (pendrive fora, no caso da RoBERTaLexPT), sem a placa pedida ou sem o PyTorch, devolve None e deixa um aviso no log; a geracao seg...
- [desperta/ia/automatico.py:285](../../desperta/ia/automatico.py#L285) função `depois_da_coleta()`: Secao 6.1 e decisao 23.2: indexa o que e novo ou mudou e escreve os rascunhos dos fatos novos. Decisao 25.10: cada modelo indexa os seus trechos; sem um dele...

### `desperta/ia/boletim.py` (433 linhas)
Boletins do dia (decisao 25.13, item 4; registro em 25.17).
- [desperta/ia/boletim.py:80](../../desperta/ia/boletim.py#L80) classe `Classificacao`
- [desperta/ia/boletim.py:86](../../desperta/ia/boletim.py#L86) função `_falha_grave(proposicao, votacao)`: Decisao 25.13: lacuna de nivel 1 ou 2 (contradicao ou ocultacao) sempre vira noticia propria.
- [desperta/ia/boletim.py:97](../../desperta/ia/boletim.py#L97) função `classificar(caso, proposicao, votacao)`: Regra provisoria ate o filtro calibrado (item 6): pelo codigo da Camara sempre que da. Na duvida, noticia propria, com aviso no log: o erro possivel e uma no...
- [desperta/ia/boletim.py:138](../../desperta/ia/boletim.py#L138) função `tem_noticia_viva(proposicao_id)`: A proposicao ja tem noticia da IA aberta ou publicada (25.16).
- [desperta/ia/boletim.py:151](../../desperta/ia/boletim.py#L151) classe `Item`
- [desperta/ia/boletim.py:162](../../desperta/ia/boletim.py#L162) classe `DadosDoDia`
- [desperta/ia/boletim.py:167](../../desperta/ia/boletim.py#L167) função `DadosDoDia.total(self)`
- [desperta/ia/boletim.py:171](../../desperta/ia/boletim.py#L171) função `_identificacao(proposicao)`
- [desperta/ia/boletim.py:175](../../desperta/ia/boletim.py#L175) função `_ementa(proposicao)`
- [desperta/ia/boletim.py:179](../../desperta/ia/boletim.py#L179) função `_nome_do_orgao(votacao)`: Nome da comissao com a sigla, que sozinha o leitor nao conhece (decisao 14.1: sigla vazia mostra o nome).
- [desperta/ia/boletim.py:188](../../desperta/ia/boletim.py#L188) função `_item_da_votacao(votacao, proposicao, categoria)`
- [desperta/ia/boletim.py:205](../../desperta/ia/boletim.py#L205) função `ler_dia(dia, tipos)`: Os fatos pequenos do dia, por categoria (mesmos fatos que o gerar-novos considera, 23.2 e 25.1).
- [desperta/ia/boletim.py:280](../../desperta/ia/boletim.py#L280) função `_n(numero, singular, plural)`
- [desperta/ia/boletim.py:284](../../desperta/ia/boletim.py#L284) função `_linha(item)`: Cada fato com o seu link: a pagina da proposicao no site da Camara.
- [desperta/ia/boletim.py:289](../../desperta/ia/boletim.py#L289) função `_por_grupo(itens)`
- [desperta/ia/boletim.py:296](../../desperta/ia/boletim.py#L296) função `_fecho(dados)`
- [desperta/ia/boletim.py:311](../../desperta/ia/boletim.py#L311) função `_resumo(categoria, dia, itens)`
- [desperta/ia/boletim.py:330](../../desperta/ia/boletim.py#L330) função `escrever(categoria, dados)`: (titulo, resumo, corpo) do boletim de uma categoria.
- [desperta/ia/boletim.py:351](../../desperta/ia/boletim.py#L351) função `_entrada(dia, categoria)`
- [desperta/ia/boletim.py:355](../../desperta/ia/boletim.py#L355) função `_tema()`
- [desperta/ia/boletim.py:363](../../desperta/ia/boletim.py#L363) função `gerar_boletins(dia, hoje, simular)`: Os boletins de um dia (padrao: ontem), um por categoria com fatos. O mesmo dia e a mesma categoria nao geram dois boletins (so se o primeiro foi rejeitado). ...
- [desperta/ia/boletim.py:422](../../desperta/ia/boletim.py#L422) função `em_texto(dia, resultado)`

### `desperta/ia/cli.py` (273 linhas)
- [desperta/ia/cli.py:17](../../desperta/ia/cli.py#L17) função `_modelo(qual)`
- [desperta/ia/cli.py:24](../../desperta/ia/cli.py#L24) função `_qual_padrao()`
- [desperta/ia/cli.py:37](../../desperta/ia/cli.py#L37) função `_conferir_arquivos(pasta, modelo)`: Mostra a lista da decisao 21.2 e confere se o modelo carregou de verdade.
- [desperta/ia/cli.py:46](../../desperta/ia/cli.py#L46) função `_carregar_da_pasta(pasta, qual)`
- [desperta/ia/cli.py:54](../../desperta/ia/cli.py#L54) função `baixar_modelo(qual)`: Baixa a RoBERTaLexPT (para ROBERTA_DIR) ou o e5 (para E5_DIR) uma vez e confere se carrega.
- [desperta/ia/cli.py:78](../../desperta/ia/cli.py#L78) função `mover_roberta(destino)`: Copia a RoBERTaLexPT para outra pasta e confere; a copia antiga nao e apagada.
- [desperta/ia/cli.py:93](../../desperta/ia/cli.py#L93) função `_data(ctx, param, valor)`
- [desperta/ia/cli.py:110](../../desperta/ia/cli.py#L110) função `indexar(tipos, limite, quais)`: Cria os trechos e os embeddings do que e novo ou mudou, para cada modelo (decisao 25.10).
- [desperta/ia/cli.py:139](../../desperta/ia/cli.py#L139) função `buscar(consulta, tipos, k, inicio, fim, modo, qual)`: Mostra os trechos mais parecidos com a consulta.
- [desperta/ia/cli.py:152](../../desperta/ia/cli.py#L152) função `medir_busca(arquivo, qual)`: Quantas das proposicoes esperadas aparecem nos 8 primeiros, em cada modo (decisoes 16.2 e 19.2).
- [desperta/ia/cli.py:164](../../desperta/ia/cli.py#L164) função `_modelo_ou_palavras()`: O modelo da escrita dos rascunhos (RAG_MODELO, decisao 25.10).
- [desperta/ia/cli.py:179](../../desperta/ia/cli.py#L179) função `gerar(caso, ref)`: Escreve um rascunho: nova ou situacao recebem o id da proposicao; votacao, o id da votacao.
- [desperta/ia/cli.py:198](../../desperta/ia/cli.py#L198) função `gerar_novos(dias, limite, simular, refazer_erros)`: Rascunho de cada votacao, mudanca de situacao e proposicao nova dos ultimos dias.
- [desperta/ia/cli.py:212](../../desperta/ia/cli.py#L212) função `relatorio_semanal(ate, simular)`: RF07: relatorio dos sete dias ate a data, como rascunho do tipo relatorio.
- [desperta/ia/cli.py:233](../../desperta/ia/cli.py#L233) função `boletins(dia, simular)`: Decisao 25.17: os boletins do dia (fatos pequenos), um por tipo de fato, como rascunhos.
- [desperta/ia/cli.py:257](../../desperta/ia/cli.py#L257) função `publicar_automaticas(modo)`: Decisao 25.18: confere os rascunhos na planta da noticia e publica (ligada) ou so conta (ensaio).
- [desperta/ia/cli.py:265](../../desperta/ia/cli.py#L265) função `reconstruir()`: Refaz os indices vetoriais (um por modelo) e os de palavras a partir de trecho_rag, sem gerar embeddings.
- [desperta/ia/cli.py:272](../../desperta/ia/cli.py#L272) função `init_app(app)`

### `desperta/ia/embeddings.py` (203 linhas)
- [desperta/ia/embeddings.py:15](../../desperta/ia/embeddings.py#L15) classe `ModeloAusente`: A pasta de um modelo de embeddings nao existe ou esta incompleta.
- [desperta/ia/embeddings.py:19](../../desperta/ia/embeddings.py#L19) classe `RobertaAusente`: A pasta da RoBERTaLexPT nao existe ou esta incompleta (decisao 21.3).
- [desperta/ia/embeddings.py:23](../../desperta/ia/embeddings.py#L23) classe `E5Ausente`: A pasta do e5 nao existe ou esta incompleta (decisao 25.10).
- [desperta/ia/embeddings.py:27](../../desperta/ia/embeddings.py#L27) classe `DispositivoIndisponivel`: IA_DISPOSITIVO=cuda, mas a placa nao aparece (decisao 20.2).
- [desperta/ia/embeddings.py:31](../../desperta/ia/embeddings.py#L31) função `caminho_no_projeto(app, caminho)`: Caminho relativo vale a partir da raiz do projeto; nenhum caminho do PC fica no codigo (21.4).
- [desperta/ia/embeddings.py:36](../../desperta/ia/embeddings.py#L36) função `preparar_ambiente(app, offline)`: Vale antes de importar o transformers, que le esta variavel ao carregar.
- [desperta/ia/embeddings.py:41](../../desperta/ia/embeddings.py#L41) função `arquivos_faltando(pasta)`: Vazio se a pasta tem o modelo inteiro, com pesos, configuracao e tokenizador.
- [desperta/ia/embeddings.py:49](../../desperta/ia/embeddings.py#L49) função `tamanho_em_mb(pasta)`
- [desperta/ia/embeddings.py:54](../../desperta/ia/embeddings.py#L54) função `salvar_modelo(nome, pasta, cache_dir, com_cabeca)`: Salva em pasta simples, sem os links do cache do Hugging Face, que pendrive em exFAT ou FAT32 nao aceita. com_cabeca: a RoBERTaLexPT guarda tambem a cabeca d...
- [desperta/ia/embeddings.py:71](../../desperta/ia/embeddings.py#L71) função `_hash_do_arquivo(caminho)`
- [desperta/ia/embeddings.py:79](../../desperta/ia/embeddings.py#L79) função `copiar_modelo(origem, destino)`: Copia e confere byte a byte; a origem nao e apagada: isso e decisao do Lucas (21.2).
- [desperta/ia/embeddings.py:93](../../desperta/ia/embeddings.py#L93) função `escolher_dispositivo(preferencia)`: Decisao 20.2: auto usa a placa se existir; cuda exige a placa; cpu nunca a usa.
- [desperta/ia/embeddings.py:109](../../desperta/ia/embeddings.py#L109) função `nome_do_dispositivo(dispositivo)`
- [desperta/ia/embeddings.py:119](../../desperta/ia/embeddings.py#L119) classe `ModeloEmbedding`: Carregado uma vez pelo modulo de IA, em segundo plano. torch e transformers ficam dentro dos metodos: a API Flask nao carrega o modelo. Os prefixos sao do e5...
- [desperta/ia/embeddings.py:126](../../desperta/ia/embeddings.py#L126) função `ModeloEmbedding.__init__(self, nome, pasta, tokenizador, modelo, dispositivo, prefixo_documento, prefixo_consulta)`
- [desperta/ia/embeddings.py:146](../../desperta/ia/embeddings.py#L146) função `ModeloEmbedding._carregar(self)`
- [desperta/ia/embeddings.py:156](../../desperta/ia/embeddings.py#L156) função `ModeloEmbedding.dividir(self, texto, max_tokens, sobreposicao)`: Devolve (texto, tokens) de cada trecho; texto curto fica num trecho so.
- [desperta/ia/embeddings.py:171](../../desperta/ia/embeddings.py#L171) função `ModeloEmbedding.embutir(self, textos)`: Devolve um embedding por trecho, na mesma ordem: 768 float32 = 3.072 bytes.
- [desperta/ia/embeddings.py:175](../../desperta/ia/embeddings.py#L175) função `ModeloEmbedding.embutir_consulta(self, consulta)`: O embedding da consulta da busca.
- [desperta/ia/embeddings.py:179](../../desperta/ia/embeddings.py#L179) função `ModeloEmbedding._embutir(self, textos)`
- [desperta/ia/embeddings.py:191](../../desperta/ia/embeddings.py#L191) função `ModeloEmbedding._embutir_lote(self, textos)`

### `desperta/ia/geracao.py` (387 linhas)
- [desperta/ia/geracao.py:39](../../desperta/ia/geracao.py#L39) classe `ErroDeGeracao`: O registro nao permite escrever a noticia; vira geracao_ia com status erro.
- [desperta/ia/geracao.py:43](../../desperta/ia/geracao.py#L43) função `_nome_do_orgao(orgao_id, sigla)`: Decisao 14.1: sigla vazia e "sem valor"; mostra o nome.
- [desperta/ia/geracao.py:51](../../desperta/ia/geracao.py#L51) função `_dados_da_proposicao(proposicao)`
- [desperta/ia/geracao.py:72](../../desperta/ia/geracao.py#L72) função `_avisar_situacao_desconhecida(proposicao)`: Decisao 25.13: codigo fora do dicionario mostra so o nome da Camara e avisa a equipe.
- [desperta/ia/geracao.py:91](../../desperta/ia/geracao.py#L91) função `_lacunas(fontes)`: Decisao 25.13: so as falhas da Camara entram na secao; a pratica normal ja esta no resultado.
- [desperta/ia/geracao.py:100](../../desperta/ia/geracao.py#L100) função `_tramitacoes(proposicao_id)`
- [desperta/ia/geracao.py:118](../../desperta/ia/geracao.py#L118) função `_proposicao_da_votacao(votacao)`: A proposicao objeto pode ser um requerimento: prefere a afetada de um tipo acompanhado.
- [desperta/ia/geracao.py:131](../../desperta/ia/geracao.py#L131) função `_dados_da_votacao(votacao)`
- [desperta/ia/geracao.py:148](../../desperta/ia/geracao.py#L148) função `_ler_origem(caso, ref)`: Devolve (proposicao, votacao ou None); caso que nao existe para em erro, antes de escrever.
- [desperta/ia/geracao.py:161](../../desperta/ia/geracao.py#L161) função `_entrada(caso, proposicao, votacao)`: Os ids usados; data_status separa duas mudancas de situacao da mesma proposicao.
- [desperta/ia/geracao.py:175](../../desperta/ia/geracao.py#L175) função `chave_do_fato(entrada)`: O que identifica o fato (25.16). A entrada gravada traz tambem a data da situacao da proposicao, que muda a cada passo do andamento: comparar a entrada intei...
- [desperta/ia/geracao.py:202](../../desperta/ia/geracao.py#L202) função `_geracao_existente(entrada)`: Gerar de novo o mesmo fato nao duplica a noticia; so a rejeitada pode ser refeita.
- [desperta/ia/geracao.py:228](../../desperta/ia/geracao.py#L228) função `_fontes(proposicao, votacao)`: A primeira gera o link da fonte oficial.
- [desperta/ia/geracao.py:239](../../desperta/ia/geracao.py#L239) função `_data_do_fato(caso, proposicao, votacao)`
- [desperta/ia/geracao.py:247](../../desperta/ia/geracao.py#L247) função `_fato(caso, proposicao, votacao, texto, fontes)`: Decisao 25.16: o fato novo como atualizacao da noticia viva (titulo, paragrafo e o placar ou a situacao).
- [desperta/ia/geracao.py:264](../../desperta/ia/geracao.py#L264) função `_modelo_da_busca(modelo)`: Decisao 25.10 e transparencia (22.5): o modelo que fez a busca de verdade, ou que foi so por palavras.
- [desperta/ia/geracao.py:269](../../desperta/ia/geracao.py#L269) função `_registrar_erro(caso, ref, consulta, entrada, gerador_nome, versao, erro, inicio, modelo_embedding)`
- [desperta/ia/geracao.py:297](../../desperta/ia/geracao.py#L297) função `gerar_noticia(modelo, caso, ref, gerador)`: Secao 6: toda execucao grava geracao_ia, mesmo com erro; a noticia entra como rascunho (RF06). modelo e o de RAG_MODELO (25.10); None: sem ele (21.3), busca ...

### `desperta/ia/gerador.py` (520 linhas)
- [desperta/ia/gerador.py:114](../../desperta/ia/gerador.py#L114) classe `TextoGerado`
- [desperta/ia/gerador.py:123](../../desperta/ia/gerador.py#L123) classe `DadosTramitacao`
- [desperta/ia/gerador.py:131](../../desperta/ia/gerador.py#L131) classe `DadosVotacao`
- [desperta/ia/gerador.py:146](../../desperta/ia/gerador.py#L146) classe `DadosProposicao`
- [desperta/ia/gerador.py:164](../../desperta/ia/gerador.py#L164) classe `DadosLacuna`: Lacuna da Camara ja em texto (desperta/sistema/lacunas.py): o que falta e a prova.
- [desperta/ia/gerador.py:172](../../desperta/ia/gerador.py#L172) classe `DadosNoticia`: Os registros de origem, ja lidos do banco: e daqui que sai todo fato do texto.
- [desperta/ia/gerador.py:185](../../desperta/ia/gerador.py#L185) classe `Gerador`
- [desperta/ia/gerador.py:189](../../desperta/ia/gerador.py#L189) função `Gerador.escrever(self, consulta, trechos, dados)`: Recebe a consulta, os textos recuperados pelo RAG e os registros de origem; devolve um TextoGerado.
- [desperta/ia/gerador.py:195](../../desperta/ia/gerador.py#L195) classe `GeradorFalso`
- [desperta/ia/gerador.py:199](../../desperta/ia/gerador.py#L199) função `GeradorFalso.escrever(self, consulta, trechos, dados)`
- [desperta/ia/gerador.py:210](../../desperta/ia/gerador.py#L210) função `_cortar(texto, limite)`: Corta entre palavras, para nao partir um numero ou um nome no meio.
- [desperta/ia/gerador.py:217](../../desperta/ia/gerador.py#L217) função `_limpar_ementa(ementa)`: A API traz aspas de abertura, "NOVA EMENTA:" e espacos sobrando.
- [desperta/ia/gerador.py:224](../../desperta/ia/gerador.py#L224) função `_minuscula_inicial(texto)`
- [desperta/ia/gerador.py:228](../../desperta/ia/gerador.py#L228) função `simplificar_ementa(ementa)`: So com regras, sem IA, e sem acrescentar nenhum fato: tira o que e formula e devolve (forma, texto). Forma: "finalidade" comeca no infinitivo ("prever..."), ...
- [desperta/ia/gerador.py:245](../../desperta/ia/gerador.py#L245) função `_identificacao(proposicao)`
- [desperta/ia/gerador.py:249](../../desperta/ia/gerador.py#L249) função `_tipo(proposicao)`
- [desperta/ia/gerador.py:253](../../desperta/ia/gerador.py#L253) função `_nome_com_artigo(proposicao)`: "O PL 1/2024"; tipos fora dos acompanhados vem de "A proposicao REQ 1/2024".
- [desperta/ia/gerador.py:260](../../desperta/ia/gerador.py#L260) função `_explicado(proposicao, maiuscula)`: Planta da noticia (25.18): a sigla explicada na primeira vez, para o brasileiro comum: "o projeto de lei PL 1/2024", "a proposta de emenda à Constituição PEC...
- [desperta/ia/gerador.py:273](../../desperta/ia/gerador.py#L273) função `_de_explicado(proposicao)`: "do projeto de lei PL 1/2024", "da proposta de emenda à Constituição PEC 2/2023".
- [desperta/ia/gerador.py:294](../../desperta/ia/gerador.py#L294) função `_de_autor(autor)`
- [desperta/ia/gerador.py:299](../../desperta/ia/gerador.py#L299) função `_de_nome(proposicao)`: "do PL 1/2024", "da PEC 2/2023"; fora dos tipos acompanhados, "da proposicao REQ 1/2024".
- [desperta/ia/gerador.py:306](../../desperta/ia/gerador.py#L306) função `_no_dia(data)`: A noticia pode sair dias depois: nada de "nesta terca-feira", que ficaria errado.
- [desperta/ia/gerador.py:312](../../desperta/ia/gerador.py#L312) função `_frase(texto)`
- [desperta/ia/gerador.py:316](../../desperta/ia/gerador.py#L316) função `_quem_votou(votacao)`
- [desperta/ia/gerador.py:320](../../desperta/ia/gerador.py#L320) função `_titulo_da_votacao(votacao)`
- [desperta/ia/gerador.py:324](../../desperta/ia/gerador.py#L324) função `_placar(votacao)`
- [desperta/ia/gerador.py:337](../../desperta/ia/gerador.py#L337) função `_descricao_da_votacao(votacao)`
- [desperta/ia/gerador.py:341](../../desperta/ia/gerador.py#L341) função `_tramitacao_em_frase(tramitacao)`
- [desperta/ia/gerador.py:347](../../desperta/ia/gerador.py#L347) classe `GeradorFrases`
- [desperta/ia/gerador.py:354](../../desperta/ia/gerador.py#L354) função `GeradorFrases.escrever(self, consulta, trechos, dados)`
- [desperta/ia/gerador.py:373](../../desperta/ia/gerador.py#L373) função `GeradorFrases._nova(self, dados)`
- [desperta/ia/gerador.py:393](../../desperta/ia/gerador.py#L393) função `GeradorFrases._situacao(self, dados)`
- [desperta/ia/gerador.py:408](../../desperta/ia/gerador.py#L408) função `GeradorFrases._votacao(self, dados)`
- [desperta/ia/gerador.py:429](../../desperta/ia/gerador.py#L429) função `GeradorFrases._o_que_foi_votado(self, proposicao)`: 25.18: a sigla no titulo ("Camara aprova PL 1/2024, que institui ...").
- [desperta/ia/gerador.py:439](../../desperta/ia/gerador.py#L439) função `GeradorFrases._autoria(self, proposicao)`
- [desperta/ia/gerador.py:442](../../desperta/ia/gerador.py#L442) função `GeradorFrases._sem_situacao(self, dados)`: Decisao 25.1: quando a Camara nao informa a situacao, a noticia conta o ultimo passo do andamento; a descricao do passo nunca e apresentada como se fosse a s...
- [desperta/ia/gerador.py:456](../../desperta/ia/gerador.py#L456) função `GeradorFrases._corpo(self, dados)`: Decisao 25.13: secoes na ordem; cada uma comeca com "## " e o titulo.
- [desperta/ia/gerador.py:466](../../desperta/ia/gerador.py#L466) função `GeradorFrases._o_que_propoe(self, dados)`
- [desperta/ia/gerador.py:473](../../desperta/ia/gerador.py#L473) função `GeradorFrases._resultado(self, votacao)`
- [desperta/ia/gerador.py:484](../../desperta/ia/gerador.py#L484) função `GeradorFrases._onde_esta(self, dados)`
- [desperta/ia/gerador.py:503](../../desperta/ia/gerador.py#L503) função `GeradorFrases._lacunas(self, dados)`: A introducao mantem o texto verdadeiro mesmo depois que a Camara corrigir os dados.
- [desperta/ia/gerador.py:512](../../desperta/ia/gerador.py#L512) função `criar_gerador(nome)`: Decisao 17.2: a troca de quem escreve e so de configuracao (GERADOR).

### `desperta/ia/models.py` (170 linhas)
- [desperta/ia/models.py:17](../../desperta/ia/models.py#L17) classe `GeracaoIA`
- [desperta/ia/models.py:75](../../desperta/ia/models.py#L75) função `GeracaoIA.__repr__(self)`
- [desperta/ia/models.py:83](../../desperta/ia/models.py#L83) classe `TrechoRAG`
- [desperta/ia/models.py:123](../../desperta/ia/models.py#L123) função `TrechoRAG.__repr__(self)`
- [desperta/ia/models.py:131](../../desperta/ia/models.py#L131) classe `GeracaoTrecho`
- [desperta/ia/models.py:160](../../desperta/ia/models.py#L160) função `GeracaoTrecho.__repr__(self)`

### `desperta/ia/palavras.py` (134 linhas)
- [desperta/ia/palavras.py:57](../../desperta/ia/palavras.py#L57) função `_existe(tabela)`
- [desperta/ia/palavras.py:63](../../desperta/ia/palavras.py#L63) função `criar_indice()`: Trechos gravados antes de os indices existirem entram aqui; os seguintes, pelos gatilhos (trecho_fts) e pelo ORM (trecho_fts_raiz). Se o indice das raizes na...
- [desperta/ia/palavras.py:79](../../desperta/ia/palavras.py#L79) função `remover(trecho_id)`: Para exclusao em lote, que nao passa pelo ORM (o indice trecho_fts tem gatilho proprio).
- [desperta/ia/palavras.py:85](../../desperta/ia/palavras.py#L85) função `_reconstruir_palavras()`
- [desperta/ia/palavras.py:89](../../desperta/ia/palavras.py#L89) função `_reconstruir_raizes()`
- [desperta/ia/palavras.py:94](../../desperta/ia/palavras.py#L94) função `reconstruir()`
- [desperta/ia/palavras.py:99](../../desperta/ia/palavras.py#L99) função `remover_indice()`
- [desperta/ia/palavras.py:104](../../desperta/ia/palavras.py#L104) função `_para_match(consulta)`: Qualquer palavra serve, e o bm25 favorece as raras; as aspas evitam quebrar a sintaxe do MATCH. Decisao 25.3: a comparacao e pelas raizes das palavras.
- [desperta/ia/palavras.py:118](../../desperta/ia/palavras.py#L118) função `buscar(consulta, k, candidatos, modelo)`: Devolve os ids dos trechos, do mais relevante ao menos; candidatos e um select de ids. modelo: so os trechos desse modelo de embeddings (trecho_rag.modelo_em...

### `desperta/ia/relatorio.py` (477 linhas)
RF07 (decisao 25.5): relatorio da semana na Camara.
- [desperta/ia/relatorio.py:78](../../desperta/ia/relatorio.py#L78) classe `VotacaoDaSemana`
- [desperta/ia/relatorio.py:90](../../desperta/ia/relatorio.py#L90) classe `Avanco`
- [desperta/ia/relatorio.py:100](../../desperta/ia/relatorio.py#L100) classe `DadosDaSemana`
- [desperta/ia/relatorio.py:113](../../desperta/ia/relatorio.py#L113) função `DadosDaSemana.vazia(self)`
- [desperta/ia/relatorio.py:120](../../desperta/ia/relatorio.py#L120) função `semana_ate(fim)`: Os sete dias que terminam em fim.
- [desperta/ia/relatorio.py:125](../../desperta/ia/relatorio.py#L125) função `semana_passada(hoje)`: Os sete dias que terminam ontem: a rotina semanal roda no domingo de madrugada.
- [desperta/ia/relatorio.py:130](../../desperta/ia/relatorio.py#L130) função `periodo_em_texto(inicio, fim)`
- [desperta/ia/relatorio.py:144](../../desperta/ia/relatorio.py#L144) função `_identificacao(proposicao)`
- [desperta/ia/relatorio.py:148](../../desperta/ia/relatorio.py#L148) função `_ementa(proposicao)`
- [desperta/ia/relatorio.py:152](../../desperta/ia/relatorio.py#L152) função `_votacoes(dados, tipos)`
- [desperta/ia/relatorio.py:186](../../desperta/ia/relatorio.py#L186) função `_proposicoes(dados, tipos)`
- [desperta/ia/relatorio.py:232](../../desperta/ia/relatorio.py#L232) função `ler_semana(inicio, fim)`
- [desperta/ia/relatorio.py:243](../../desperta/ia/relatorio.py#L243) função `_n(numero, singular, plural)`
- [desperta/ia/relatorio.py:247](../../desperta/ia/relatorio.py#L247) função `_lista(partes)`
- [desperta/ia/relatorio.py:251](../../desperta/ia/relatorio.py#L251) função `_novas_em_texto(novas)`
- [desperta/ia/relatorio.py:255](../../desperta/ia/relatorio.py#L255) função `_abertura(dados)`
- [desperta/ia/relatorio.py:272](../../desperta/ia/relatorio.py#L272) função `_secao_de_votacoes(dados)`
- [desperta/ia/relatorio.py:296](../../desperta/ia/relatorio.py#L296) função `_secao_de_avancos(dados)`
- [desperta/ia/relatorio.py:312](../../desperta/ia/relatorio.py#L312) função `_secao_de_temas(dados)`
- [desperta/ia/relatorio.py:324](../../desperta/ia/relatorio.py#L324) função `_fecho(dados)`
- [desperta/ia/relatorio.py:339](../../desperta/ia/relatorio.py#L339) função `_resumo(dados)`
- [desperta/ia/relatorio.py:367](../../desperta/ia/relatorio.py#L367) função `escrever(dados)`: Devolve (titulo, resumo, corpo) do relatorio.
- [desperta/ia/relatorio.py:378](../../desperta/ia/relatorio.py#L378) função `_entrada(inicio, fim)`
- [desperta/ia/relatorio.py:382](../../desperta/ia/relatorio.py#L382) função `_tema()`: A noticia precisa de um tema (RF05): o relatorio fala do trabalho da Camara como um todo.
- [desperta/ia/relatorio.py:389](../../desperta/ia/relatorio.py#L389) função `_fontes(dados)`: Votacoes e proposicoes citadas pelo nome no texto; a primeira e a fonte principal.
- [desperta/ia/relatorio.py:397](../../desperta/ia/relatorio.py#L397) função `previa(fim, hoje)`: O relatorio da semana sem gravar nada: (dados, titulo, resumo, corpo).
- [desperta/ia/relatorio.py:404](../../desperta/ia/relatorio.py#L404) função `gerar_relatorio_semanal(fim, hoje)`: Grava o relatorio da semana como rascunho do tipo "relatorio" e registra a geracao_ia. Devolve (geracao, novo). A mesma semana nao gera dois relatorios (so s...
- [desperta/ia/relatorio.py:469](../../desperta/ia/relatorio.py#L469) função `em_texto(geracao, novo)`: Uma linha para o terminal e para o agendador.log.

### `desperta/ia/routes.py` (4 linhas)

### `desperta/ia/services.py` (334 linhas)
- [desperta/ia/services.py:24](../../desperta/ia/services.py#L24) classe `ResultadoBusca`
- [desperta/ia/services.py:30](../../desperta/ia/services.py#L30) função `_hash(texto)`
- [desperta/ia/services.py:34](../../desperta/ia/services.py#L34) função `nome_do_modelo(qual)`: roberta ou e5 -> o nome gravado em trecho_rag.modelo_embedding.
- [desperta/ia/services.py:41](../../desperta/ia/services.py#L41) função `_existentes(nome_modelo, tipos)`
- [desperta/ia/services.py:50](../../desperta/ia/services.py#L50) função `_gravar_lote(modelo, lote, existentes)`: Gera os embeddings fora da transacao, grava e confirma: parar no meio nao perde o que ja foi feito.
- [desperta/ia/services.py:70](../../desperta/ia/services.py#L70) função `_remover_sobras(sobras)`: Registro ou parte que sumiu da origem; o trecho usado por uma geracao fica, para o historico.
- [desperta/ia/services.py:85](../../desperta/ia/services.py#L85) função `indexar(modelo, tipos, limite)`: Secao 6.1: so registro novo ou com hash_texto diferente recebe embedding. limite e o maximo de trechos com embedding novo nesta execucao; o resto fica para a...
- [desperta/ia/services.py:155](../../desperta/ia/services.py#L155) função `reconstruir_indice(nome_modelo)`: Refaz o indice vetorial do modelo e os de palavras a partir de trecho_rag, sem gerar embeddings.
- [desperta/ia/services.py:172](../../desperta/ia/services.py#L172) função `_ligado(tipo, ref_id)`
- [desperta/ia/services.py:176](../../desperta/ia/services.py#L176) função `_ids_no_periodo(inicio, fim, tipos)`: Trechos cujo registro de origem e do periodo; a data de cada tipo esta na sua tabela.
- [desperta/ia/services.py:205](../../desperta/ia/services.py#L205) função `_juntar_por_rrf(listas)`: Reciprocal Rank Fusion: cada lista, com o seu peso, soma peso / (constante + posicao) ao trecho.
- [desperta/ia/services.py:215](../../desperta/ia/services.py#L215) função `buscar(modelo, consulta, top_k, tipos, inicio, fim, modo, nome_modelo)`: Decisao 16.1: os melhores de cada indice, juntos pelo RRF; os filtros valem para os dois. Em similaridade vai a nota do RRF; no modo vetorial, que so serve p...
- [desperta/ia/services.py:260](../../desperta/ia/services.py#L260) função `_proposicao_do_trecho(trecho)`: Tramitacao tambem conta como achar a proposicao; o ref_id dela e "proposicao/sequencia".
- [desperta/ia/services.py:269](../../desperta/ia/services.py#L269) função `medir_busca(modelo, consultas, modos, k)`: Decisao 16.2: quantas das proposicoes esperadas aparecem nos k primeiros, em cada modo. Decisao 19.2: tambem quantas das marcadas a mao em "fora_do_assunto" ...
- [desperta/ia/services.py:294](../../desperta/ia/services.py#L294) função `carregar_modelo(qual)`: Decisao 21.3: confere a pasta antes de importar o torch e, sem ela, para com aviso no log. Decisao 20.2: registra o dispositivo de cada execucao. Decisao 25....

### `desperta/ia/trechos.py` (122 linhas)
- [desperta/ia/trechos.py:14](../../desperta/ia/trechos.py#L14) função `_juntar(*partes)`
- [desperta/ia/trechos.py:18](../../desperta/ia/trechos.py#L18) função `_proposicoes()`
- [desperta/ia/trechos.py:32](../../desperta/ia/trechos.py#L32) função `_tramitacoes()`: Decisao 16.3: so as recentes, comecando pela proposicao; um despacho sozinho nao diz de que projeto se trata.
- [desperta/ia/trechos.py:75](../../desperta/ia/trechos.py#L75) função `_votacoes()`: Transparencia: o trecho diz se a votacao foi nominal, so com o placar, simbolica ou pendente.
- [desperta/ia/trechos.py:96](../../desperta/ia/trechos.py#L96) função `_eventos()`
- [desperta/ia/trechos.py:102](../../desperta/ia/trechos.py#L102) função `_itens_de_pauta()`
- [desperta/ia/trechos.py:118](../../desperta/ia/trechos.py#L118) função `textos_de_origem(tipos)`: Devolve (tipo, ref_id, texto) de cada registro que vira trecho (secao 6.1).

### `desperta/ia/vetores.py` (117 linhas)
- [desperta/ia/vetores.py:18](../../desperta/ia/vetores.py#L18) função `tabela(nome_modelo)`
- [desperta/ia/vetores.py:22](../../desperta/ia/vetores.py#L22) função `_criar(nome_tabela)`
- [desperta/ia/vetores.py:29](../../desperta/ia/vetores.py#L29) função `_indice(nome_tabela)`
- [desperta/ia/vetores.py:33](../../desperta/ia/vetores.py#L33) função `_conexao()`: A conexao da sessao, com a extensao carregada: cada conexao do pool carrega uma vez.
- [desperta/ia/vetores.py:47](../../desperta/ia/vetores.py#L47) função `_existe(nome_tabela)`
- [desperta/ia/vetores.py:53](../../desperta/ia/vetores.py#L53) função `criar_indice(nome_modelo)`
- [desperta/ia/vetores.py:57](../../desperta/ia/vetores.py#L57) função `gravar(nome_modelo, trecho_id, embedding)`
- [desperta/ia/vetores.py:68](../../desperta/ia/vetores.py#L68) função `remover(trecho_id)`: O trecho so esta no indice do seu modelo; apagar dos dois e mais simples e nao custa nada.
- [desperta/ia/vetores.py:75](../../desperta/ia/vetores.py#L75) função `reconstruir(nome_modelo)`: Refaz o indice do modelo a partir de trecho_rag. Devolve o total de trechos.
- [desperta/ia/vetores.py:101](../../desperta/ia/vetores.py#L101) função `remover_indice()`: Para o drop-db: so carrega a extensao se algum indice existir (dropar exige o modulo vec0).
- [desperta/ia/vetores.py:108](../../desperta/ia/vetores.py#L108) função `buscar(nome_modelo, embedding, k, candidatos)`: Devolve (trecho_id, distancia), do mais parecido ao menos; candidatos e um select de ids.

### `desperta/noticias/__init__.py` (5 linhas)
- [desperta/noticias/__init__.py:4](../../desperta/noticias/__init__.py#L4) função `init_app(app)`

### `desperta/noticias/models.py` (183 linhas)
- [desperta/noticias/models.py:22](../../desperta/noticias/models.py#L22) classe `Noticia`
- [desperta/noticias/models.py:98](../../desperta/noticias/models.py#L98) função `Noticia.__repr__(self)`
- [desperta/noticias/models.py:106](../../desperta/noticias/models.py#L106) classe `NoticiaFonte`
- [desperta/noticias/models.py:131](../../desperta/noticias/models.py#L131) função `NoticiaFonte.__repr__(self)`
- [desperta/noticias/models.py:139](../../desperta/noticias/models.py#L139) classe `NoticiaRevisao`
- [desperta/noticias/models.py:173](../../desperta/noticias/models.py#L173) função `NoticiaRevisao.__repr__(self)`

### `desperta/noticias/planta.py` (321 linhas)
Planta da noticia e publicacao automatica (decisao 25.18; texto em docs/PLANTA_DA_NOTICIA.md).
- [desperta/noticias/planta.py:83](../../desperta/noticias/planta.py#L83) classe `Conferencia`
- [desperta/noticias/planta.py:88](../../desperta/noticias/planta.py#L88) função `Conferencia.passou(self)`
- [desperta/noticias/planta.py:91](../../desperta/noticias/planta.py#L91) função `Conferencia.como_dict(self)`
- [desperta/noticias/planta.py:95](../../desperta/noticias/planta.py#L95) função `frases(texto)`
- [desperta/noticias/planta.py:99](../../desperta/noticias/planta.py#L99) função `_palavras(texto)`
- [desperta/noticias/planta.py:106](../../desperta/noticias/planta.py#L106) função `conferir_texto(titulo, resumo, corpo, caso, tipo, atualizacao)`: As regras da planta que dependem so do texto. Devolve Conferencia.
- [desperta/noticias/planta.py:164](../../desperta/noticias/planta.py#L164) função `_geracoes(noticia)`
- [desperta/noticias/planta.py:172](../../desperta/noticias/planta.py#L172) função `_caso(geracao)`
- [desperta/noticias/planta.py:181](../../desperta/noticias/planta.py#L181) função `conferir(noticia)`: A planta e a confianca juntas: passou = pode sair sozinha.
- [desperta/noticias/planta.py:230](../../desperta/noticias/planta.py#L230) função `_id_do_sistema()`
- [desperta/noticias/planta.py:236](../../desperta/noticias/planta.py#L236) função `usuario_do_sistema()`: Quem assina a publicacao automatica no historico (noticia_revisao pede alguem da equipe): um cadastro tecnico, desativado e sem senha conhecida, entao ningue...
- [desperta/noticias/planta.py:252](../../desperta/noticias/planta.py#L252) função `publicada_pelo_sistema(noticia)`: A ultima publicacao foi automatica? (transparencia em "como foi feita").
- [desperta/noticias/planta.py:267](../../desperta/noticias/planta.py#L267) classe `ResultadoDaPublicacao`
- [desperta/noticias/planta.py:274](../../desperta/noticias/planta.py#L274) função `ResultadoDaPublicacao.em_texto(self)`
- [desperta/noticias/planta.py:282](../../desperta/noticias/planta.py#L282) função `candidatas()`: Rascunhos da IA escritos na planta (frases-v3 ou boletim), sem revisao da equipe.
- [desperta/noticias/planta.py:294](../../desperta/noticias/planta.py#L294) função `publicar_automaticas(modo)`: Confere os rascunhos na planta e, no modo ligada, publica os que passam (pelo service, com historico).

### `desperta/noticias/prioridade.py` (173 linhas)
- [desperta/noticias/prioridade.py:27](../../desperta/noticias/prioridade.py#L27) classe `Prioridade`
- [desperta/noticias/prioridade.py:31](../../desperta/noticias/prioridade.py#L31) função `Prioridade.como_dict(self)`
- [desperta/noticias/prioridade.py:35](../../desperta/noticias/prioridade.py#L35) função `_casos(ids)`: {noticia_id: [entradas das geracoes ok, da mais antiga para a mais nova]} (25.16: a noticia viva tem varias).
- [desperta/noticias/prioridade.py:52](../../desperta/noticias/prioridade.py#L52) função `_fontes(ids)`
- [desperta/noticias/prioridade.py:63](../../desperta/noticias/prioridade.py#L63) função `_da_votacao(votacao, proposicao)`
- [desperta/noticias/prioridade.py:77](../../desperta/noticias/prioridade.py#L77) função `_da_situacao(proposicao, entrada)`
- [desperta/noticias/prioridade.py:89](../../desperta/noticias/prioridade.py#L89) função `_da_nova(proposicao)`
- [desperta/noticias/prioridade.py:99](../../desperta/noticias/prioridade.py#L99) função `calcular(noticias)`: {noticia_id: Prioridade} para varias noticias de uma vez (poucas consultas). noticias: objetos ou linhas com id, origem e tipo. Regras: o fato decide o nivel...

### `desperta/noticias/routes.py` (139 linhas)
- [desperta/noticias/routes.py:15](../../desperta/noticias/routes.py#L15) função `listar()`: RF11: noticias publicadas, de todos os temas ou de um (?tema=).
- [desperta/noticias/routes.py:23](../../desperta/noticias/routes.py#L23) função `principal()`: RF10: as principais de cada tema (?por_tema=, padrao 3).
- [desperta/noticias/routes.py:29](../../desperta/noticias/routes.py#L29) função `busca()`: RF12: ?q= com ?dia=, ?mes= e ?ano= em horario de Brasilia, e ?tema=.
- [desperta/noticias/routes.py:44](../../desperta/noticias/routes.py#L44) função `detalhe(slug)`: RF18: a noticia pelo endereco proprio; cada abertura conta uma visualizacao.
- [desperta/noticias/routes.py:56](../../desperta/noticias/routes.py#L56) função `fila()`: Fila da equipe: ?status=, ?tema=, ?caso= (votacao, situacao, nova, relatorio_semanal), ?origem= (ia, equipe), ?prioridade= (alta, media, baixa) e ?ordem= (pr...
- [desperta/noticias/routes.py:84](../../desperta/noticias/routes.py#L84) função `criar()`
- [desperta/noticias/routes.py:100](../../desperta/noticias/routes.py#L100) função `lote()`
- [desperta/noticias/routes.py:110](../../desperta/noticias/routes.py#L110) função `detalhe_para_revisao(noticia_id)`
- [desperta/noticias/routes.py:116](../../desperta/noticias/routes.py#L116) função `editar(noticia_id)`
- [desperta/noticias/routes.py:126](../../desperta/noticias/routes.py#L126) função `mudar_status(noticia_id, acao)`: acao = aprovar, publicar, rejeitar (com comentario) ou arquivar.
- [desperta/noticias/routes.py:136](../../desperta/noticias/routes.py#L136) função `excluir(noticia_id)`: Decisao 10.4: so rascunho ou rejeitada, e so o admin; o normal e arquivar.

### `desperta/noticias/services.py` (711 linhas)
- [desperta/noticias/services.py:43](../../desperta/noticias/services.py#L43) função `gerar_slug(titulo)`: Sem acento, minusculo e unico; depois de publicada, a noticia nao muda de slug.
- [desperta/noticias/services.py:58](../../desperta/noticias/services.py#L58) função `criar_rascunho(titulo, resumo, corpo, cod_tema, fontes, origem)`: RF06: toda noticia gerada entra como rascunho; fontes sao (tipo, ref_id), a primeira e a principal.
- [desperta/noticias/services.py:78](../../desperta/noticias/services.py#L78) função `excluir_noticia(noticia, admin)`: Apaga um rascunho ou uma noticia rejeitada (decisao 10.4). Fontes e revisoes vao junto (cascade do ORM); as geracoes da IA ficam, com noticia_id nulo, para o...
- [desperta/noticias/services.py:113](../../desperta/noticias/services.py#L113) função `_termo_para_match(termo)`: Decisao 25.3: a busca compara raizes ("professores" acha "professor" e "professora"). Todas as palavras precisam aparecer, cada uma por qualquer das suas rai...
- [desperta/noticias/services.py:123](../../desperta/noticias/services.py#L123) função `buscar_noticias(termo, inicio, fim, cod_tema)`: Busca nas noticias publicadas, por relevancia e depois pela mais recente. inicio e fim comparam com publicado_em (UTC); fim sem hora inclui o dia inteiro.
- [desperta/noticias/services.py:171](../../desperta/noticias/services.py#L171) função `_ia()`
- [desperta/noticias/services.py:177](../../desperta/noticias/services.py#L177) função `_tema_dict(tema)`
- [desperta/noticias/services.py:181](../../desperta/noticias/services.py#L181) função `como_cartao(noticia)`: O que aparece na lista e na pagina principal.
- [desperta/noticias/services.py:203](../../desperta/noticias/services.py#L203) função `fontes_com_links(noticia)`: Fontes na ordem; a primeira e a fonte oficial principal (RF18).
- [desperta/noticias/services.py:221](../../desperta/noticias/services.py#L221) função `como_foi_feita(noticia)`: Transparencia (22.5): quem escreveu, quem revisou e publicou.
- [desperta/noticias/services.py:252](../../desperta/noticias/services.py#L252) função `secoes_do_corpo(corpo)`: Separa o corpo nas secoes "## " (decisao 25.13): [{"titulo", "texto"}]. Texto antes da primeira secao (ou noticia antiga, sem secoes) vem com titulo None.
- [desperta/noticias/services.py:275](../../desperta/noticias/services.py#L275) função `_proposicao_principal(noticia)`
- [desperta/noticias/services.py:282](../../desperta/noticias/services.py#L282) função `transparencia(noticia, interna)`: Decisao 25.13: a situacao da proposicao em linguagem popular e as lacunas da Camara, calculadas na hora a partir das fontes (o texto da noticia guarda como e...
- [desperta/noticias/services.py:303](../../desperta/noticias/services.py#L303) função `como_completa(noticia)`
- [desperta/noticias/services.py:319](../../desperta/noticias/services.py#L319) função `_lista_de_atualizacoes(noticia)`
- [desperta/noticias/services.py:325](../../desperta/noticias/services.py#L325) função `_publicadas()`
- [desperta/noticias/services.py:329](../../desperta/noticias/services.py#L329) função `listar_publicadas(cod_tema, pagina, por_pagina)`: RF11: por tema, da mais recente para a mais antiga.
- [desperta/noticias/services.py:343](../../desperta/noticias/services.py#L343) função `pagina_principal(por_tema)`: RF10: as principais de cada tema, com o tema da publicacao mais recente primeiro. A ordem pelos temas que o visitante mais le entra com o cookie (RF13, RF17).
- [desperta/noticias/services.py:364](../../desperta/noticias/services.py#L364) função `buscar_publicadas(termo, inicio, fim, cod_tema, pagina, por_pagina)`: RF12: busca por palavras com periodo (inicio incluso, fim exclusivo, em UTC).
- [desperta/noticias/services.py:374](../../desperta/noticias/services.py#L374) função `publicada_pelo_slug(slug)`
- [desperta/noticias/services.py:381](../../desperta/noticias/services.py#L381) função `contar_visualizacao(noticia)`: RF18: +1 direto no banco, sem mexer em alterado_em.
- [desperta/noticias/services.py:409](../../desperta/noticias/services.py#L409) função `_agora()`
- [desperta/noticias/services.py:413](../../desperta/noticias/services.py#L413) função `_texto(valor, nome, tamanho)`
- [desperta/noticias/services.py:422](../../desperta/noticias/services.py#L422) função `_comentario(valor, obrigatorio)`
- [desperta/noticias/services.py:432](../../desperta/noticias/services.py#L432) função `_tema_valido(cod_tema)`
- [desperta/noticias/services.py:438](../../desperta/noticias/services.py#L438) função `_revisao(noticia, admin, acao, comentario)`
- [desperta/noticias/services.py:442](../../desperta/noticias/services.py#L442) função `buscar_para_revisao(noticia_id)`
- [desperta/noticias/services.py:452](../../desperta/noticias/services.py#L452) função `listar_para_revisao(status, cod_tema, caso, origem, pagina, por_pagina, prioridade, ordem)`: Fila da equipe; caso = votacao, situacao, nova ou relatorio_semanal. Decisao 25.15: por padrao, as de prioridade alta primeiro e, dentro de cada nivel, as ma...
- [desperta/noticias/services.py:511](../../desperta/noticias/services.py#L511) função `conferencias(noticias)`: {noticia_id: {"passou", "falhas", "avisos"}} da planta da noticia (25.18); so a equipe ve.
- [desperta/noticias/services.py:518](../../desperta/noticias/services.py#L518) função `prioridades(noticias)`: {noticia_id: {"nivel", "motivos"}} (interno, so a equipe ve; 25.15).
- [desperta/noticias/services.py:525](../../desperta/noticias/services.py#L525) função `como_item_de_revisao(noticia, prioridade, conferencia)`
- [desperta/noticias/services.py:535](../../desperta/noticias/services.py#L535) função `como_detalhe_de_revisao(noticia)`: Tudo o que a equipe precisa para revisar: texto, fontes, historico e o que a IA usou.
- [desperta/noticias/services.py:601](../../desperta/noticias/services.py#L601) função `criar_pela_equipe(admin, titulo, resumo, corpo, cod_tema, fontes, tipo)`: Noticia escrita pela equipe: entra como rascunho, como as da IA.
- [desperta/noticias/services.py:629](../../desperta/noticias/services.py#L629) função `_fonte_existe(tipo, ref_id)`: noticia_fonte nao tem FK (5.1): o back-end confere se o registro existe.
- [desperta/noticias/services.py:645](../../desperta/noticias/services.py#L645) função `editar_noticia(noticia, admin, titulo, resumo, corpo, cod_tema)`: Muda o texto; alterado_em so muda se algo mudou. O slug acompanha o titulo ate publicar.
- [desperta/noticias/services.py:672](../../desperta/noticias/services.py#L672) função `mudar_status(noticia, admin, acao, comentario)`: Fluxo: rascunho -> em_revisao -> publicada, ou rejeitada / arquivada (RF16).
- [desperta/noticias/services.py:697](../../desperta/noticias/services.py#L697) função `mudar_status_em_lote(ids, admin, acao, comentario)`: A mesma acao em varias noticias; cada uma e independente: as que nao podem ficam listadas com o motivo.

### `desperta/noticias/viva.py` (378 linhas)
- [desperta/noticias/viva.py:30](../../desperta/noticias/viva.py#L30) classe `Fato`: O fato novo ja escrito pelo gerador, pronto para virar uma atualizacao.
- [desperta/noticias/viva.py:41](../../desperta/noticias/viva.py#L41) função `_agora()`
- [desperta/noticias/viva.py:45](../../desperta/noticias/viva.py#L45) função `proposicao_da_noticia(noticia)`: A proposicao da noticia viva e a primeira fonte do tipo proposicao.
- [desperta/noticias/viva.py:56](../../desperta/noticias/viva.py#L56) função `_da_proposicao(proposicao_id)`
- [desperta/noticias/viva.py:69](../../desperta/noticias/viva.py#L69) função `aberta_da_proposicao(proposicao_id)`: A noticia da proposicao ainda em rascunho ou em revisao (a mais antiga, se houver mais de uma).
- [desperta/noticias/viva.py:79](../../desperta/noticias/viva.py#L79) função `publicada_da_proposicao(proposicao_id, antes_de)`: A noticia publicada mais recente da proposicao (publicada antes de `antes_de`, se informado).
- [desperta/noticias/viva.py:87](../../desperta/noticias/viva.py#L87) função `original_da_atualizacao(noticia)`: Se a noticia e um rascunho de atualizacao, a noticia publicada que ela atualiza; senao None. E atualizacao quando, ao ser criada, a proposicao ja tinha notic...
- [desperta/noticias/viva.py:102](../../desperta/noticias/viva.py#L102) função `texto_da_atualizacao(fato)`
- [desperta/noticias/viva.py:107](../../desperta/noticias/viva.py#L107) função `atualizacoes_do_corpo(corpo)`: As atualizacoes da noticia, para o leitor ver que ela foi atualizada (decisao 25.16): [{"data": "dd/mm/aaaa", "titulo", "texto"}], da mais recente para a mai...
- [desperta/noticias/viva.py:130](../../desperta/noticias/viva.py#L130) função `_inserir_na_secao(corpo, texto)`: Poe o texto logo abaixo do titulo "## Atualizacoes" (a mais recente primeiro); cria a secao se nao houver.
- [desperta/noticias/viva.py:141](../../desperta/noticias/viva.py#L141) função `_juntar_fontes(noticia, fontes)`
- [desperta/noticias/viva.py:152](../../desperta/noticias/viva.py#L152) função `acrescentar(noticia, fato)`: O fato entra na noticia aberta. Se ela e um rascunho de atualizacao, o corpo e a propria lista.
- [desperta/noticias/viva.py:174](../../desperta/noticias/viva.py#L174) função `criar_atualizacao(original, fato, cod_tema)`: Rascunho de atualizacao de uma noticia ja publicada; a equipe revisa antes de entrar.
- [desperta/noticias/viva.py:198](../../desperta/noticias/viva.py#L198) função `destino_do_fato(proposicao_id, fato, cod_tema, fontes, criar_nova)`: Para onde vai o fato: a noticia aberta da proposicao, um rascunho de atualizacao da publicada, ou uma noticia nova (criar_nova()). Devolve a noticia.
- [desperta/noticias/viva.py:212](../../desperta/noticias/viva.py#L212) função `publicar_atualizacao(rascunho, original, admin)`: Ao publicar o rascunho de atualizacao: o texto (talvez editado pela equipe) entra nas atualizacoes da original, que ganha as fontes e o alterado_em; o rascun...
- [desperta/noticias/viva.py:239](../../desperta/noticias/viva.py#L239) função `como_dict_da_original(noticia)`: Para a equipe: qual noticia publicada o rascunho atualiza.
- [desperta/noticias/viva.py:250](../../desperta/noticias/viva.py#L250) função `_data_do_fato_da_noticia(noticia)`: A data do fato que a noticia conta, pela entrada da geracao; sem ela, o dia em que foi criada.
- [desperta/noticias/viva.py:278](../../desperta/noticias/viva.py#L278) função `_fato_da_noticia(noticia)`
- [desperta/noticias/viva.py:291](../../desperta/noticias/viva.py#L291) função `grupos_para_juntar()`: {proposicao_id: [noticias abertas da IA, da mais antiga para a mais nova]}, so as proposicoes com mais de uma. Proposicao que ja tem noticia publicada fica d...
- [desperta/noticias/viva.py:318](../../desperta/noticias/viva.py#L318) função `juntar(noticias, admin)`: A mais antiga vira a noticia viva (o fato dela fica no topo); as outras entram como atualizacoes, na ordem das datas dos fatos, com as fontes; as geracoes pa...

### `desperta/orgaos/__init__.py` (5 linhas)
- [desperta/orgaos/__init__.py:4](../../desperta/orgaos/__init__.py#L4) função `init_app(app)`

### `desperta/orgaos/models.py` (232 linhas)
- [desperta/orgaos/models.py:16](../../desperta/orgaos/models.py#L16) classe `Orgao`
- [desperta/orgaos/models.py:66](../../desperta/orgaos/models.py#L66) função `Orgao.__repr__(self)`
- [desperta/orgaos/models.py:74](../../desperta/orgaos/models.py#L74) classe `DeputadoOrgao`
- [desperta/orgaos/models.py:105](../../desperta/orgaos/models.py#L105) função `DeputadoOrgao.__repr__(self)`
- [desperta/orgaos/models.py:113](../../desperta/orgaos/models.py#L113) classe `Evento`
- [desperta/orgaos/models.py:165](../../desperta/orgaos/models.py#L165) função `Evento.__repr__(self)`
- [desperta/orgaos/models.py:173](../../desperta/orgaos/models.py#L173) classe `PautaItem`
- [desperta/orgaos/models.py:228](../../desperta/orgaos/models.py#L228) função `PautaItem.__repr__(self)`

### `desperta/orgaos/routes.py` (4 linhas)

### `desperta/orgaos/services.py` (1 linhas)

### `desperta/parlamentares/__init__.py` (5 linhas)
- [desperta/parlamentares/__init__.py:4](../../desperta/parlamentares/__init__.py#L4) função `init_app(app)`

### `desperta/parlamentares/models.py` (396 linhas)
- [desperta/parlamentares/models.py:18](../../desperta/parlamentares/models.py#L18) classe `Deputado`
- [desperta/parlamentares/models.py:113](../../desperta/parlamentares/models.py#L113) função `Deputado.__repr__(self)`
- [desperta/parlamentares/models.py:121](../../desperta/parlamentares/models.py#L121) classe `Partido`
- [desperta/parlamentares/models.py:156](../../desperta/parlamentares/models.py#L156) função `Partido.__repr__(self)`
- [desperta/parlamentares/models.py:164](../../desperta/parlamentares/models.py#L164) classe `Legislatura`
- [desperta/parlamentares/models.py:198](../../desperta/parlamentares/models.py#L198) função `Legislatura.__repr__(self)`
- [desperta/parlamentares/models.py:206](../../desperta/parlamentares/models.py#L206) classe `Lideranca`
- [desperta/parlamentares/models.py:239](../../desperta/parlamentares/models.py#L239) função `Lideranca.__repr__(self)`
- [desperta/parlamentares/models.py:247](../../desperta/parlamentares/models.py#L247) classe `Bloco`
- [desperta/parlamentares/models.py:280](../../desperta/parlamentares/models.py#L280) função `Bloco.__repr__(self)`
- [desperta/parlamentares/models.py:288](../../desperta/parlamentares/models.py#L288) classe `BlocoPartido`
- [desperta/parlamentares/models.py:313](../../desperta/parlamentares/models.py#L313) função `BlocoPartido.__repr__(self)`
- [desperta/parlamentares/models.py:321](../../desperta/parlamentares/models.py#L321) classe `Frente`
- [desperta/parlamentares/models.py:354](../../desperta/parlamentares/models.py#L354) função `Frente.__repr__(self)`
- [desperta/parlamentares/models.py:362](../../desperta/parlamentares/models.py#L362) classe `FrenteMembro`
- [desperta/parlamentares/models.py:392](../../desperta/parlamentares/models.py#L392) função `FrenteMembro.__repr__(self)`

### `desperta/parlamentares/routes.py` (4 linhas)

### `desperta/parlamentares/services.py` (1 linhas)

### `desperta/proposicoes/__init__.py` (5 linhas)
- [desperta/proposicoes/__init__.py:4](../../desperta/proposicoes/__init__.py#L4) função `init_app(app)`

### `desperta/proposicoes/models.py` (327 linhas)
- [desperta/proposicoes/models.py:61](../../desperta/proposicoes/models.py#L61) classe `Proposicao`
- [desperta/proposicoes/models.py:156](../../desperta/proposicoes/models.py#L156) função `Proposicao.__repr__(self)`
- [desperta/proposicoes/models.py:164](../../desperta/proposicoes/models.py#L164) classe `ProposicaoAutor`
- [desperta/proposicoes/models.py:197](../../desperta/proposicoes/models.py#L197) função `ProposicaoAutor.__repr__(self)`
- [desperta/proposicoes/models.py:205](../../desperta/proposicoes/models.py#L205) classe `ProposicaoTema`
- [desperta/proposicoes/models.py:231](../../desperta/proposicoes/models.py#L231) função `ProposicaoTema.__repr__(self)`
- [desperta/proposicoes/models.py:239](../../desperta/proposicoes/models.py#L239) classe `Tema`
- [desperta/proposicoes/models.py:274](../../desperta/proposicoes/models.py#L274) função `Tema.__repr__(self)`
- [desperta/proposicoes/models.py:282](../../desperta/proposicoes/models.py#L282) classe `Tramitacao`
- [desperta/proposicoes/models.py:323](../../desperta/proposicoes/models.py#L323) função `Tramitacao.__repr__(self)`

### `desperta/proposicoes/routes.py` (27 linhas)
- [desperta/proposicoes/routes.py:11](../../desperta/proposicoes/routes.py#L11) função `temas()`: Os temas oficiais da Camara, que sao as categorias do portal.
- [desperta/proposicoes/routes.py:17](../../desperta/proposicoes/routes.py#L17) função `detalhe(proposicao_id)`: RF09: situacao, autores, temas, andamento (as 20 mais recentes) e votacoes.
- [desperta/proposicoes/routes.py:23](../../desperta/proposicoes/routes.py#L23) função `tramitacoes(proposicao_id)`: O andamento completo, em paginas, da mais recente para a mais antiga.

### `desperta/proposicoes/services.py` (280 linhas)
- [desperta/proposicoes/services.py:30](../../desperta/proposicoes/services.py#L30) função `informado(valor)`: Devolve o valor sem espacos, ou None se a Camara nao informou.
- [desperta/proposicoes/services.py:38](../../desperta/proposicoes/services.py#L38) função `ou_nao_informado(valor, feminino)`
- [desperta/proposicoes/services.py:48](../../desperta/proposicoes/services.py#L48) função `situacao_mudou(proposicao_id, cod_situacao, data_status)`
- [desperta/proposicoes/services.py:73](../../desperta/proposicoes/services.py#L73) função `_taxa_de_tema_principal()`: Para cada tema, a parte das proposicoes ordenadas pela Camara em que ele e o principal. A suavizacao (+1 e +2) evita que um tema visto poucas vezes fique com...
- [desperta/proposicoes/services.py:91](../../desperta/proposicoes/services.py#L91) função `tema_principal(proposicao_id)`: O tema principal da proposicao, ou None se ela nao tem tema. Com a ordem da Camara, e o de relevancia 0. Sem ordem (todos em 0), vale o tema que a Camara mai...
- [desperta/proposicoes/services.py:126](../../desperta/proposicoes/services.py#L126) função `tema_sem_classificacao()`: O codigo do tema especial; cria a linha na primeira vez que for preciso.
- [desperta/proposicoes/services.py:141](../../desperta/proposicoes/services.py#L141) função `tema_da_noticia(proposicao_id)`: (cod_tema, a Camara informou?): o tema principal, ou o tema especial quando nao ha nenhum.
- [desperta/proposicoes/services.py:149](../../desperta/proposicoes/services.py#L149) função `sigla_completa(proposicao)`
- [desperta/proposicoes/services.py:153](../../desperta/proposicoes/services.py#L153) função `buscar_proposicao(proposicao_id)`
- [desperta/proposicoes/services.py:160](../../desperta/proposicoes/services.py#L160) função `como_resumo(proposicao)`
- [desperta/proposicoes/services.py:164](../../desperta/proposicoes/services.py#L164) função `como_tramitacao(tramitacao)`: Decisao 14.1: despacho vazio nao aparece, e orgao sem sigla mostra o nome.
- [desperta/proposicoes/services.py:179](../../desperta/proposicoes/services.py#L179) função `listar_tramitacoes(proposicao_id, pagina, por_pagina)`: Da mais recente para a mais antiga.
- [desperta/proposicoes/services.py:190](../../desperta/proposicoes/services.py#L190) função `como_dict(proposicao)`: Pagina da proposicao: situacao (ou o que a Camara nao informou), autores, temas, andamento e votacoes.
- [desperta/proposicoes/services.py:258](../../desperta/proposicoes/services.py#L258) função `listar_temas()`: Todos os temas oficiais, com quantas noticias publicadas cada um tem.
- [desperta/proposicoes/services.py:277](../../desperta/proposicoes/services.py#L277) função `proposicoes_do_tema(cod_tema)`

### `desperta/proposicoes/situacoes.py` (108 linhas)
- [desperta/proposicoes/situacoes.py:84](../../desperta/proposicoes/situacoes.py#L84) função `situacao_informada(cod_situacao, nome)`: A Camara informou a situacao? Codigo nulo, nome vazio ou "<Nao Definido>" contam como nao.
- [desperta/proposicoes/situacoes.py:91](../../desperta/proposicoes/situacoes.py#L91) função `explicar_situacao(cod_situacao, nome)`: Situacao publica (decisao 25.13): o nome exato da Camara e, se o codigo estiver no dicionario, a explicacao popular. conhecida=False pede um aviso no log.
- [desperta/proposicoes/situacoes.py:106](../../desperta/proposicoes/situacoes.py#L106) função `situacao_conhecida(cod_situacao, nome)`: False so quando a Camara informou um codigo que o dicionario nao tem.

### `desperta/sistema/__init__.py` (5 linhas)
- [desperta/sistema/__init__.py:4](../../desperta/sistema/__init__.py#L4) função `init_app(app)`

### `desperta/sistema/lacunas.py` (463 linhas)
- [desperta/sistema/lacunas.py:46](../../desperta/sistema/lacunas.py#L46) classe `Prova`
- [desperta/sistema/lacunas.py:54](../../desperta/sistema/lacunas.py#L54) função `Prova.como_dict(self)`
- [desperta/sistema/lacunas.py:62](../../desperta/sistema/lacunas.py#L62) função `Prova.em_texto(self)`
- [desperta/sistema/lacunas.py:68](../../desperta/sistema/lacunas.py#L68) classe `Lacuna`
- [desperta/sistema/lacunas.py:77](../../desperta/sistema/lacunas.py#L77) função `Lacuna.falha_da_camara(self)`
- [desperta/sistema/lacunas.py:81](../../desperta/sistema/lacunas.py#L81) função `Lacuna.url_mais_informacoes(self)`
- [desperta/sistema/lacunas.py:84](../../desperta/sistema/lacunas.py#L84) função `Lacuna.publica(self)`: O que o leitor ve: sem o nivel (interno).
- [desperta/sistema/lacunas.py:95](../../desperta/sistema/lacunas.py#L95) função `Lacuna.interna(self)`: Area da equipe: com o nivel.
- [desperta/sistema/lacunas.py:102](../../desperta/sistema/lacunas.py#L102) função `horario_de_brasilia(momento)`: Data do banco (UTC) em texto, no horario de Brasilia: "17/11/2026 às 03:31".
- [desperta/sistema/lacunas.py:108](../../desperta/sistema/lacunas.py#L108) função `valor_como_veio(valor)`: Mostra o valor exatamente como a API mandou, com um nome para o leitor entender.
- [desperta/sistema/lacunas.py:126](../../desperta/sistema/lacunas.py#L126) função `_agora()`
- [desperta/sistema/lacunas.py:130](../../desperta/sistema/lacunas.py#L130) função `_ausente_na_camara(tabela, ref_id, desde)`: Decisao 25.8: o ultimo aviso de 404 do detalhe, se for depois da ultima vez que o registro apareceu na API (senao a Camara ja voltou a mandar o registro).
- [desperta/sistema/lacunas.py:146](../../desperta/sistema/lacunas.py#L146) função `_lacuna_404(tabela, ref_id, caminho, nome, proposicao_id, sincronizado_em, aviso)`
- [desperta/sistema/lacunas.py:169](../../desperta/sistema/lacunas.py#L169) função `lacunas_da_proposicao(proposicao, agora, tem_tema, aviso_404)`: tem_tema e aviso_404 vem prontos no calculo em lote (lacunas_em_lote); sozinha, consulta o banco.
- [desperta/sistema/lacunas.py:272](../../desperta/sistema/lacunas.py#L272) função `lacunas_da_votacao(votacao, proposicao_id, votos, aviso_404)`: Pendente e erro na coleta sao do portal, nao da Camara: nao viram lacuna (a explicacao ja diz). votos (Counter por tipo) e aviso_404 vem prontos no calculo e...
- [desperta/sistema/lacunas.py:392](../../desperta/sistema/lacunas.py#L392) função `lacunas_das_fontes(fontes)`: fontes: (tipo, ref_id) na ordem da noticia. Mais graves primeiro; sem repetir.
- [desperta/sistema/lacunas.py:414](../../desperta/sistema/lacunas.py#L414) função `_avisos_404(tabela, ids)`: {id em texto: ultimo aviso de 404} numa consulta so.
- [desperta/sistema/lacunas.py:432](../../desperta/sistema/lacunas.py#L432) função `lacunas_em_lote(proposicoes, votacoes, agora)`: As mesmas lacunas de lacunas_da_proposicao e lacunas_da_votacao, para muitos registros com poucas consultas: ({proposicao_id: [Lacuna]}, {votacao_id: [Lacuna...

### `desperta/sistema/models.py` (126 linhas)
- [desperta/sistema/models.py:18](../../desperta/sistema/models.py#L18) classe `LogSistema`
- [desperta/sistema/models.py:66](../../desperta/sistema/models.py#L66) função `LogSistema.__repr__(self)`
- [desperta/sistema/models.py:74](../../desperta/sistema/models.py#L74) classe `Coleta`
- [desperta/sistema/models.py:122](../../desperta/sistema/models.py#L122) função `Coleta.__repr__(self)`

### `desperta/sistema/routes.py` (36 linhas)
- [desperta/sistema/routes.py:12](../../desperta/sistema/routes.py#L12) função `situacao()`: RNF05 (publica): ultima coleta concluida e aviso de dados desatualizados.
- [desperta/sistema/routes.py:19](../../desperta/sistema/routes.py#L19) função `coletas()`: ?status= (ok, parcial, erro) e ?recurso= (proposicoes, votacoes...).
- [desperta/sistema/routes.py:30](../../desperta/sistema/routes.py#L30) função `log()`: ?nivel= (info, aviso, erro), ?modulo= (coletor, IA, admin) e ?coleta=.

### `desperta/sistema/services.py` (101 linhas)
- [desperta/sistema/services.py:12](../../desperta/sistema/services.py#L12) função `ultima_coleta_concluida(recurso)`: Data da ultima coleta com status ok (RNF05), geral ou de um recurso; None se nao houver.
- [desperta/sistema/services.py:20](../../desperta/sistema/services.py#L20) função `situacao_dos_dados(agora)`: RNF05: data da ultima coleta concluida e se o portal deve avisar que os dados podem estar desatualizados.
- [desperta/sistema/services.py:38](../../desperta/sistema/services.py#L38) função `_conferir(valor, permitidos, nome)`
- [desperta/sistema/services.py:44](../../desperta/sistema/services.py#L44) função `_paginar(consulta, ordem, pagina, por_pagina)`
- [desperta/sistema/services.py:50](../../desperta/sistema/services.py#L50) função `listar_coletas(status, recurso, pagina, por_pagina)`
- [desperta/sistema/services.py:59](../../desperta/sistema/services.py#L59) função `como_coleta(coleta)`
- [desperta/sistema/services.py:78](../../desperta/sistema/services.py#L78) função `listar_log(nivel, modulo, coleta_id, pagina, por_pagina)`
- [desperta/sistema/services.py:89](../../desperta/sistema/services.py#L89) função `como_log(registro)`

### `desperta/visitantes/__init__.py` (5 linhas)
- [desperta/visitantes/__init__.py:4](../../desperta/visitantes/__init__.py#L4) função `init_app(app)`

### `desperta/visitantes/models.py` (78 linhas)
- [desperta/visitantes/models.py:13](../../desperta/visitantes/models.py#L13) classe `Visitante`
- [desperta/visitantes/models.py:40](../../desperta/visitantes/models.py#L40) função `Visitante.__repr__(self)`
- [desperta/visitantes/models.py:48](../../desperta/visitantes/models.py#L48) classe `VisitanteTema`
- [desperta/visitantes/models.py:74](../../desperta/visitantes/models.py#L74) função `VisitanteTema.__repr__(self)`

### `desperta/visitantes/routes.py` (4 linhas)

### `desperta/visitantes/services.py` (1 linhas)

### `desperta/votacoes/__init__.py` (5 linhas)
- [desperta/votacoes/__init__.py:4](../../desperta/votacoes/__init__.py#L4) função `init_app(app)`

### `desperta/votacoes/models.py` (224 linhas)
- [desperta/votacoes/models.py:18](../../desperta/votacoes/models.py#L18) classe `Votacao`
- [desperta/votacoes/models.py:106](../../desperta/votacoes/models.py#L106) função `Votacao.__repr__(self)`
- [desperta/votacoes/models.py:114](../../desperta/votacoes/models.py#L114) classe `Voto`
- [desperta/votacoes/models.py:144](../../desperta/votacoes/models.py#L144) função `Voto.__repr__(self)`
- [desperta/votacoes/models.py:152](../../desperta/votacoes/models.py#L152) classe `Orientacao`
- [desperta/votacoes/models.py:187](../../desperta/votacoes/models.py#L187) função `Orientacao.__repr__(self)`
- [desperta/votacoes/models.py:195](../../desperta/votacoes/models.py#L195) classe `VotacaoProposicao`
- [desperta/votacoes/models.py:220](../../desperta/votacoes/models.py#L220) função `VotacaoProposicao.__repr__(self)`

### `desperta/votacoes/routes.py` (11 linhas)
- [desperta/votacoes/routes.py:9](../../desperta/votacoes/routes.py#L9) função `detalhe(votacao_id)`: RF09: resultado, situacao dos votos, voto de cada deputado e orientacoes (id no formato 2310837-8).

### `desperta/votacoes/services.py` (243 linhas)
- [desperta/votacoes/services.py:37](../../desperta/votacoes/services.py#L37) classe `SituacaoDosVotos`
- [desperta/votacoes/services.py:46](../../desperta/votacoes/services.py#L46) função `placar_da_camara(descricao)`
- [desperta/votacoes/services.py:50](../../desperta/votacoes/services.py#L50) função `placar_em_frase(placar)`: {"Sim": 404, "Nao": 61, "Abstencao": 1} -> "404 a favor, 61 contra e 1 abstenção".
- [desperta/votacoes/services.py:65](../../desperta/votacoes/services.py#L65) função `_teve_erro_na_coleta(id_votacao)`
- [desperta/votacoes/services.py:80](../../desperta/votacoes/services.py#L80) função `e_votacao_de_merito(descricao)`: A votacao decidiu o proprio projeto (aprovou ou rejeitou), e nao um requerimento ou um destaque.
- [desperta/votacoes/services.py:85](../../desperta/votacoes/services.py#L85) função `classificar_votos(votacao, votos)`: So para votacao com os votos ja coletados (filhos_sincronizados_em preenchido): simbolica, so o placar, inconsistente ou nominal. votos: Counter por tipo (No...
- [desperta/votacoes/services.py:118](../../desperta/votacoes/services.py#L118) função `contar_votos(votacao_ids)`: {votacao_id: Counter por tipo} de varias votacoes numa consulta so.
- [desperta/votacoes/services.py:132](../../desperta/votacoes/services.py#L132) função `situacao_dos_votos(votacao)`: Classifica os votos da votacao: pendente, erro na coleta, so o placar, simbolica, nominal ou inconsistente.
- [desperta/votacoes/services.py:153](../../desperta/votacoes/services.py#L153) função `buscar_votacao(votacao_id)`
- [desperta/votacoes/services.py:160](../../desperta/votacoes/services.py#L160) função `_resultado(aprovacao)`
- [desperta/votacoes/services.py:166](../../desperta/votacoes/services.py#L166) função `orientacoes_em_grupos(votacao_id)`
- [desperta/votacoes/services.py:182](../../desperta/votacoes/services.py#L182) função `como_dict(votacao)`: Resultado, situacao dos votos (22.5), voto de cada deputado e orientacoes (RF09).
