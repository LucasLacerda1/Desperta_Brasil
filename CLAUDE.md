# Desperta Brasil — guia do projeto para o Claude Code

> Coloque este arquivo na **raiz do repositório** com o nome `CLAUDE.md`. O Claude Code lê esse arquivo sozinho no início de cada sessão.
> Última atualização: 30/10/2026 (Fases 1 e 1.5 concluídas; decisões nas seções 10 e 11; ajuste físico do banco em `docs/AJUSTE_BANCO_SISTEMA.md`).

## 0. Como trabalhar neste projeto (leia primeiro)

- **Idioma:** responda, comente o código e escreva mensagens de commit em **português do Brasil**.
- **Padrão obrigatório:** o código segue a estrutura do projeto **TaskFlow**, usado como exemplo pelo professor da disciplina (Programação Web Avançada, UVV). A seção 3 descreve esse padrão. Não invente outra organização, não troque o Flask-SQLAlchemy por outro ORM e não use outro estilo de modelo.
- **Ordem do trabalho:** o projeto é construído por fases (seção 7). **As Fases 1 (banco) e 1.5 (ajuste físico do banco, `docs/AJUSTE_BANCO_SISTEMA.md`) estão concluídas. A fase atual é a Fase 2: coletor.** Não comece o coletor, a IA, as rotas da API ou o front-end antes da fase anterior estar pronta e testada, a não ser que o grupo peça. Antes de mudar código, leia as seções 10 e 11 (decisões tomadas depois das Fases 1 e 1.5).
- **Git:** a `main` no GitHub é a versão estável. Cada fase é feita numa branch própria (`fase-2-coletor`, `fase-3-ia`…), com commits pequenos ao fim de cada passo e mensagem em português; ao terminar a fase, abrir um pull request para a `main`, para o grupo revisar. Não fazer push direto na `main`. Nunca versione `.venv/`, `instance/`, `.env` nem arquivos `*.db`, `*.db-wal`, `*.db-shm`.
- **O modelo do banco já foi decidido pelo grupo** (32 tabelas, seção 5). Não acrescente, remova nem renomeie tabelas ou colunas por conta própria. A única exceção são as colunas técnicas, índices e configurações listados em `docs/AJUSTE_BANCO_SISTEMA.md` (camada física: controle de sincronização, índices, FTS5, migrações), que não mudam o modelo lógico. Se achar um problema no modelo, aponte e pergunte antes de mudar.
- **Ao terminar cada passo:** rode os testes (`invoke test`) e mostre o resultado.

---

## 1. O projeto

**Desperta Brasil** é um portal de notícias que acompanha a atividade da **Câmara dos Deputados**. Um coletor busca proposições (projetos de lei, PECs), tramitações, votações, deputados e eventos na API de Dados Abertos da Câmara, e uma IA transforma esses dados em notícias em linguagem simples, no formato de newsletter, organizadas por tema e sempre com link para a fonte oficial. Cada notícia é revisada pela equipe antes de ser publicada.

- **Grupo:** Lucas Lacerda Freire, Rhuan Santos Wolfgramm e Caio Henrique de Oliveira.
- **Escopo do MVP:** só a Câmara dos Deputados. Senado, STF e assembleias ficam para depois.
- **Público:** cidadãos sem conhecimento técnico; também jornalistas, estudantes e pesquisadores.
- **Visitantes:** sem login e sem propaganda, identificados por cookie anônimo (com aceite de cookies, LGPD).
- **Equipe:** login só para a equipe, com dois papéis: `editor` (revisa, corrige, aprova, rejeita, publica e arquiva) e `admin` (também gerencia a equipe e acompanha coletas e log).

### 1.1 Funcionalidades do MVP (em ordem de prioridade)

Essenciais:
1. Coleta automática dos dados da Câmara (RF01 a RF04).
2. Geração de notícias pela IA, com RAG (RF05, RF06, RF08, RF15).
3. Revisão e publicação na área administrativa (RF16).
4. Página principal e navegação por tema (RF10, RF11).
5. Busca por palavras (digitada ou por voz) e filtro por dia, mês e ano (RF12).
6. Página da notícia, com fonte oficial, inteiro teor, tramitações e resultado da votação com votos e orientações (RF09, RF18).

Complementares:
7. Página principal personalizada pelos temas mais lidos pelo visitante (RF13, RF17).
8. Acessibilidade: botão "Ouvir" (Piper) e busca por voz (Whisper) (RF14).
9. Relatórios da IA que conectam os dados, por exemplo por legislatura (RF07).

### 1.2 Requisitos funcionais

| Código | Requisito |
|---|---|
| RF01 | Consumir a API v2 da Câmara: proposições (autores, temas, tramitações), votações (votos, orientações, proposições afetadas), deputados, partidos, legislaturas, órgãos (membros e Mesa), eventos (pauta), lideranças, blocos, frentes e a lista de temas. |
| RF02 | Coleta agendada (revisto em 30/10/2026, ver 12.1): votações e eventos a cada hora; proposições dos tipos acompanhados a cada hora (janela curta) e numa revisão diária dos últimos dias; varredura de 30 dias uma vez por semana; cargos em órgãos e blocos semanalmente; frentes mensalmente. |
| RF03 | Guardar os dados num modelo relacional que espelha a API, com os mesmos ids, atualizando (upsert) em vez de duplicar. |
| RF04 | Registrar cada coleta (endpoint, parâmetros, início, fim, total, novos, atualizados, status, erro) e guardar o link do inteiro teor. |
| RF05 | Classificar proposições e notícias pelos temas oficiais da Câmara (proposições recebem os temas da API; cada notícia tem um tema principal). |
| RF06 | Gerar notícias (título, resumo, texto) com RAG, registrando as fontes. Toda notícia gerada entra como `rascunho`. |
| RF07 | Relatórios por evento, período ou legislatura, gerados em segundo plano e publicados como notícia do tipo `relatorio`, após revisão. |
| RF08 | Destacar a relevância dos itens (votações em Plenário, PECs, aprovadas, muitas tramitações recentes). |
| RF09 | Mostrar o andamento da proposição (tramitações) e o resultado da votação, com voto de cada deputado e orientação de partidos e blocos. |
| RF10 | Página principal com as principais notícias de cada tema, ordenada pelos temas que o visitante mais acessa. |
| RF11 | Listar notícias por tema, com data e hora de publicação e de alteração. |
| RF12 | Busca por palavras, digitada ou por voz (Whisper), e filtro por período. |
| RF13 | Acesso sem login e sem propaganda; visitante identificado por cookie anônimo, com aceite de cookies. |
| RF14 | Acessibilidade: leitura das notícias em voz alta (Piper) e busca por voz (Whisper). |
| RF15 | Log do sistema (coletor, IA, administradores) e registro de cada execução da IA (modelos, consulta, trechos, prompt, tokens, duração, resultado). |
| RF16 | Área administrativa com login só para a equipe, papéis `editor` e `admin`, histórico e comentários de revisão. |
| RF17 | Contar acessos do visitante por tema, só com aceite de cookies. |
| RF18 | Página de cada notícia com endereço próprio (slug), texto, fonte oficial, inteiro teor e contador de visualizações. |

### 1.3 Requisitos não funcionais

| Código | Requisito |
|---|---|
| RNF01 | Página principal em menos de 2 s, servida do banco (nunca chama a API da Câmara nem a IA durante a visita). |
| RNF02 | Coleta resiliente: paginação, novas tentativas e backoff exponencial. |
| RNF03 | Picos de acesso servidos do banco e de cache. Se for preciso mais concorrência, migrar do SQLite para PostgreSQL: os modelos e os services continuam iguais, mas a busca de texto (FTS5) e o índice vetorial (sqlite-vec) precisam ser refeitos (ver 11.1). |
| RNF04 | Disponibilidade alvo de 99%. |
| RNF05 | Se a API da Câmara cair, o portal mostra os dados guardados com aviso de "dados desatualizados" e a data da última coleta concluída. |
| RNF06 | Ingestão idempotente: reprocessar o mesmo período não duplica registros. |
| RNF07 | Interface simples e responsiva, estilo Material Design, sem propaganda. |
| RNF08 | Acessibilidade: contraste, navegação por teclado, leitores de tela, leitor de texto por IA. |
| RNF09 | LGPD: cookie anônimo; preferências só com aceite; visitantes sem acesso há 12 meses são apagados. |
| RNF10 | Segurança: HTTPS, senha com hash, área administrativa por papel, validação no Flask antes de gravar (inclusive tamanho dos campos), proteção contra injeção e excesso de requisições. |

---

## 2. Arquitetura e tecnologias

Aplicação cliente-servidor. O back-end tem três partes (coletor, módulo de IA e API REST) e o banco funciona como cache: o portal nunca depende da API da Câmara ou da IA em tempo real.

| Camada | Tecnologia |
|---|---|
| Front-end (portal e área administrativa) | Vue 3 + Vite + Axios, visual Material Design, ícones Material Symbols |
| Back-end / API | Python + Flask (API REST), padrão Application Factory, Blueprints |
| Banco | SQLite com Flask-SQLAlchemy (ORM). Migrações com Flask-Migrate quando o esquema estabilizar |
| Coletor | Python, rotina agendada, `requests` |
| IA (RAG) | **RoBERTaLexPT** (`eduagarcia/RoBERTaLexPT-base`) para embeddings e busca + um modelo de linguagem generativo para escrever (**ainda a definir pelo grupo**) |
| Busca vetorial | **sqlite-vec** no próprio SQLite; PyTorch + Hugging Face Transformers |
| Voz | **Whisper** (`faster-whisper`, modelo `small`, idioma `pt`) **só na busca por voz**; o áudio não é guardado. **Piper** (voz pt-BR) para ler as notícias; o áudio é gerado na publicação e salvo em arquivo pelo slug. Alternativa: Web Speech API do navegador |
| Fonte de dados | API de Dados Abertos da Câmara v2: `https://dadosabertos.camara.leg.br/api/v2` (REST, gratuita, sem chave, JSON, **sem CORS**: só o back-end chama) |

Decisões que **não** devem ser mudadas sem o grupo:
- **Sem Redis no MVP.** (Fica como evolução, para fila de gerações ou cache.)
- O Whisper **não lê texto**: só transcreve a busca por voz. A leitura é do Piper.
- Voz não cria tabela nova.
- A RoBERTaLexPT **não gera texto**: só faz embeddings e busca.
- A API Flask não carrega a RoBERTaLexPT; o modelo roda no módulo de IA, em segundo plano, depois de cada coleta.

---

## 3. Padrão de código do TaskFlow (obrigatório)

O TaskFlow é uma plataforma simplificada de gestão de projetos (estilo Taiga) feita na disciplina com Flask (API) e Vue 3. Siga a versão da Unidade 06 (camada de persistência). Resumo do que ela faz e como o Desperta Brasil deve repetir:

### 3.1 Estrutura de pastas do TaskFlow (referência)

```
TASKFLOW/
    frontend/            # app Vue 3 separada
    taskflow/
        __init__.py      # create_app()
        config.py        # class Config
        ext/
            cli/
            config/
                __init__.py
            db/
                __init__.py   # db = SQLAlchemy(), init_app, register_models
            debugtoolbar/
        auth/
            __init__.py  # init_app()
            models.py
        projects/
            __init__.py  # init_app() registra o blueprint
            models.py
            routes.py
            services.py
        tasks/
            __init__.py
            models.py
            routes.py
            services.py
    instance/            # o SQLite fica aqui (sqlite:///taskflow.db)
    tests/
    app.py
    tasks.py             # invoke
    pyproject.toml
    README.md
```

### 3.2 Regras do padrão

1. **Application Factory.** `create_app(config_class=Config)` em `pacote/__init__.py`: cria o `Flask`, chama `app.config.from_object(config_class)`, inicia as extensões, chama `register_models()` e registra os módulos de domínio. Nada de `app` global dentro do pacote.
2. **Extensões desacopladas em `ext/`.** Cada extensão é criada sem app (`db = SQLAlchemy()`) e ligada depois com `init_app(app)`.
3. **`register_models()`** em `ext/db/__init__.py`, com os `import` de cada `models.py` **dentro da função** (import tardio, evita import circular e garante que todas as tabelas entram no `metadata`).
4. **Um pacote por domínio**, cada um com `__init__.py` (função `init_app(app)` que registra o blueprint com `url_prefix="/api/..."`), `models.py`, `routes.py` (só HTTP) e `services.py` (regras de negócio e acesso ao banco). Rotas não fazem consulta direta: chamam o service.
5. **Config por classe** em `config.py`, lendo variáveis de ambiente com `os.getenv(...)` e valor padrão para desenvolvimento (12-Factor). `SQLALCHEMY_TRACK_MODIFICATIONS = False`.
6. **Modelos no estilo SQLAlchemy 2.0 tipado**, exatamente como no TaskFlow:
   - `from sqlalchemy.orm import Mapped, mapped_column, relationship` e `from <pacote>.ext.db import db`;
   - colunas com `Mapped[...]` e `mapped_column(db.Tipo, ...)`; campo opcional usa `Mapped[Optional[...]]` e `nullable=True`;
   - `__tablename__` explícito; restrições em `__table_args__` com nome (`UniqueConstraint(..., name="uq_<tabela>_<campos>")`);
   - FKs com `db.ForeignKey("tabela.coluna")` e `index=True`;
   - relacionamentos com `relationship("Classe", back_populates="...")`, nomes de classe como **string**; `foreign_keys=[...]` quando houver mais de uma FK para a mesma tabela; `cascade="all, delete-orphan"` no lado pai quando o filho não existe sem ele;
   - imports de outros domínios só dentro de `if TYPE_CHECKING:`;
   - comentário de cabeçalho `# === Classe (descricao) ===` antes de cada classe; blocos de colunas e de relacionamentos separados por comentários `# ----` / `# ====` com o nome do grupo em maiúsculas; método `__repr__` no fim, em bloco `# REPRESENTACAO`;
   - comentários em português, sem acento (como no TaskFlow).
   - Não copie o erro de digitação do TaskFlow (`create_at`): use os nomes do modelo do Desperta.
7. **Empacotamento** com `pyproject.toml` (PEP 621, setuptools) e instalação editável: `pip install -e ".[dev,test]"`.
8. **Automação com Invoke** em `tasks.py` (`invoke install`, `run`, `test`, `lint`, `format`).
9. **Testes com pytest + pytest-flask + pytest-cov**, em `tests/`, com `conftest.py` e fixture `app` que chama `create_app()`.
10. **Validação no `flask shell`:** depois de criar os modelos, testar no shell com banco em memória (`sqlite:///:memory:`), `db.create_all()`, inserir, consultar com `db.session.scalar(db.select(...))` e conferir restrições (tentativa de duplicar e `rollback()`).
11. **Front-end separado** em `frontend/` (Vue 3 + Vite, `src/services/api.js` com Axios, proxy `/api` → `http://localhost:5000` no `vite.config.js`).

### 3.3 Código de referência do TaskFlow

`taskflow/ext/db/__init__.py`:
```python
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_app(app):
    db.init_app(app)


def register_models():
    """
    Importa todos os modulos que definem modelos para que
    sejam registrados no metadata do SQLAlchemy.
    """
    import taskflow.auth.models
    import taskflow.projects.models
    import taskflow.tasks.models
```

`taskflow/__init__.py`:
```python
from flask import Flask

from .config import Config
from .ext.db import init_app as init_db
from .ext.db import register_models

# ==========================================================
# CARREGAMENTO CENTRALIZADO DE AMBIENTE
# ==========================================================
def create_app(config_class=Config):
    app = Flask(__name__)

    app.config.from_object(config_class)

    # ----------------------------------------------------------
    # Inicializacao do banco de dados
    # ----------------------------------------------------------
    init_db(app)

    # ----------------------------------------------------------
    # Registro dos modelos no metadata do SQLAlchemy
    # ----------------------------------------------------------
    register_models()

    return app
```

Modelo do TaskFlow (trecho de `taskflow/tasks/models.py`):
```python
# === Task (tarefas) ===
class Task(db.Model):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(db.String(255), nullable=False)
    assigned_to_id: Mapped[Optional[int]] = mapped_column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_by_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now())

    # ------------------------------------------------------
    # PROJETO
    # ------------------------------------------------------
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="tasks"
    )

    # ------------------------------------------------------
    # USUARIO
    # ------------------------------------------------------
    created_by: Mapped["User"] = relationship(
        "User",
        back_populates="tasks_created",
        foreign_keys=[created_by_id]
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Task id={self.id} "
            f"title='{self.title}'>"
        )
```

`app.py` (raiz):
```python
from taskflow import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

---

## 4. Estrutura do Desperta Brasil

Mesmo desenho do TaskFlow, com o pacote `desperta` e um pacote por domínio. Os 32 modelos ficam divididos assim:

```
DESPERTA_BRASIL/
    CLAUDE.md
    README.md
    pyproject.toml
    tasks.py                 # invoke
    app.py                   # from desperta import create_app
    .flaskenv                # FLASK_APP=app.py
    .env.example             # SECRET_KEY, DATABASE_URL (nunca versionar o .env)
    instance/                # desperta.db (SQLite) - fora do git
    desperta/
        __init__.py          # create_app()
        config.py            # Config, TestConfig
        ext/
            db/__init__.py   # db, migrate, init_app, register_models, PRAGMA foreign_keys
            cli/__init__.py  # flask init-db, flask drop-db
            cors/__init__.py # Flask-CORS em /api/*
        auth/                # administrador (1 tabela)
        proposicoes/         # proposicao, proposicao_autor, proposicao_tema, tema, tramitacao (5)
        votacoes/            # votacao, voto, orientacao, votacao_proposicao (4)
        parlamentares/       # deputado, partido, legislatura, lideranca, bloco, bloco_partido, frente, frente_membro (8)
        orgaos/              # orgao, deputado_orgao, evento, pauta_item (4)
        noticias/            # noticia, noticia_fonte, noticia_revisao (3)
        ia/                  # geracao_ia, trecho_rag, geracao_trecho (3)
        sistema/             # log_sistema, coleta (2)
        visitantes/          # visitante, visitante_tema (2)
        coletor/             # Fase 2: cliente da API da Câmara (não é blueprint)
        voz/                 # Fase 5: rota de transcrição (Whisper) e geração de áudio (Piper)
    frontend/                # Fase 5: Vue 3 + Vite
    tests/
        conftest.py
        test_banco_*.py
```

Total: 21 tabelas da API (proposicoes 5 + votacoes 4 + parlamentares 8 + orgaos 4) e 11 do portal (auth 1 + noticias 3 + ia 3 + sistema 2 + visitantes 2) = **32**.

Cada pacote de domínio tem `__init__.py` (com `init_app(app)`), `models.py`, `routes.py` e `services.py`. Na Fase 1, `routes.py` e `services.py` podem ficar só com o blueprint vazio e um comentário, como no TaskFlow da Unidade 06.

### 4.1 Arquivos de base esperados (Fase 1)

`desperta/ext/db/__init__.py`, igual ao TaskFlow com duas adições: Flask-Migrate e chaves estrangeiras ligadas no SQLite (o SQLite **não confere FK** sem `PRAGMA foreign_keys=ON`):
```python
import sqlite3

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
migrate = Migrate()


def init_app(app):
    db.init_app(app)
    migrate.init_app(app, db)


# ----------------------------------------------------------
# SQLite so confere chave estrangeira com este PRAGMA
# ----------------------------------------------------------
@event.listens_for(Engine, "connect")
def _ativar_foreign_keys(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def register_models():
    """
    Importa todos os modulos que definem modelos para que
    sejam registrados no metadata do SQLAlchemy.
    """
    import desperta.auth.models
    import desperta.proposicoes.models
    import desperta.votacoes.models
    import desperta.parlamentares.models
    import desperta.orgaos.models
    import desperta.noticias.models
    import desperta.ia.models
    import desperta.sistema.models
    import desperta.visitantes.models
```

`desperta/config.py`:
```python
import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-desperta")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///desperta.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = True

    # Fases seguintes (ja deixar declarado)
    CAMARA_API_URL = os.getenv("CAMARA_API_URL", "https://dadosabertos.camara.leg.br/api/v2")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "eduagarcia/RoBERTaLexPT-base")
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "8"))
    RAG_TRECHO_TOKENS = 400
    RAG_TRECHO_SOBREPOSICAO = 50
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
    PIPER_VOICE = os.getenv("PIPER_VOICE", "pt_BR-faber-medium")
    AUDIO_DIR = os.getenv("AUDIO_DIR", "instance/audio")


class TestConfig(Config):
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
```

`desperta/__init__.py`: igual ao do TaskFlow, mais `init_cors(app)`, `init_cli(app)`, o `init_app` de cada domínio e a rota `GET /api/health` (`{"status": "ok", "message": "Desperta Brasil API is running"}`).

`pyproject.toml`: mesmo formato do TaskFlow (`[build-system]` setuptools, `[project]`, `[project.optional-dependencies]`, `[tool.pytest.ini_options]`, `[tool.setuptools.packages.find]`), com:
```toml
[project]
name = "desperta"
version = "0.1.0"
description = "Portal de noticias sobre a Camara dos Deputados com dados abertos e IA (Flask API + Vue 3)."
requires-python = ">=3.10"
dependencies = [
    "Flask>=3.0",
    "Flask-SQLAlchemy>=3.1",
    "Flask-Migrate>=4.0",
    "Flask-CORS>=4.0",
    "python-dotenv",
    "requests",
]

[project.optional-dependencies]
dev = ["ipython", "flask-shell-ipython", "Flask-DebugToolbar", "invoke", "black", "flake8"]
test = ["pytest >= 8.3", "pytest-cov >= 5.0", "pytest-flask"]
ia = ["torch", "transformers", "sqlite-vec"]
voz = ["faster-whisper", "piper-tts"]
```

`tasks.py` (Invoke), seguindo a Unidade 05:
```python
from invoke import task


@task
def install(c):
    """Instala o projeto em modo editavel com dependencias de desenvolvimento e teste."""
    c.run('pip install -e ".[dev,test]"', echo=True)


@task
def initdb(c):
    """Cria as 32 tabelas no SQLite (instance/desperta.db)."""
    c.run("flask --app app.py init-db", echo=True)


@task
def run(c):
    """Executa a aplicacao Flask."""
    c.run("flask --app app.py run --debug", pty=True)


@task
def test(c):
    """Executa os testes automatizados."""
    c.run("pytest tests -v --cov=desperta", echo=True)


@task
def lint(c):
    """Verificacao de estilo com flake8."""
    c.run("flake8 desperta tests", echo=True)


@task
def format(c):
    """Formata o codigo com o Black."""
    c.run("black desperta tests", echo=True)
```

---

## 5. Banco de dados (32 tabelas)

Fontes do modelo (no repositório do grupo, se forem copiadas): `desperta-modelo-relacional.pdf`, `desperta-diagrama-er.png`, `tamanhos-varchar.md`, `parametros-api-camara.md`. Este arquivo já traz tudo o que é preciso para criar os modelos.

### 5.1 Regras gerais

- **Ids da API:** as 21 tabelas espelhadas usam **os mesmos ids da API**. Nessas PKs inteiras use `autoincrement=False`. Reprocessar uma coleta faz upsert pelo id, sem duplicar.
- **Id de votação é texto**, no formato `"2310837-8"`. Toda FK para `votacao.id` também é texto.
- **Tipos (decisão V1):** tabelas da API usam `TEXT` para texto (o Swagger da API não define tamanho); tabelas do portal usam `VARCHAR(n)` com o tamanho do grupo. O SQLite não impõe o tamanho: o Flask e o coletor validam antes de gravar.
- **Mapeamento de tipos:** `INTEGER` → `db.Integer` · `TEXT` → `db.Text` · `VARCHAR(n)` → `db.String(n)` · `DATE` → `db.Date` · `DATETIME` → `db.DateTime` · `BOOLEAN` → `db.Boolean` · `REAL` → `db.Float` · `BLOB` → `db.LargeBinary`.
- **Datas** em ISO 8601, como a API.
- **Chaves compostas:** tabelas associativas e entidades fracas usam PK composta (várias colunas com `primary_key=True`).
- **Sem relacionamento 1:1.** São 42 relacionamentos 1:N e 10 N:N.
- **Sem atalhos em triângulo (regra T1):** se x → y → z, x não liga direto em z. Por isso `lideranca` não tem FK para legislatura nem partido, e `proposicao` não guarda o órgão atual (é o da última tramitação). **Exceções aceitas pelo grupo (28/10):** `votacao` → `orgao` e `votacao` → `evento` → `orgao`; `pauta_item` → `evento` e `pauta_item` → `votacao` → `evento`; e `votacao.proposicao_id` (D2). Elas ficam porque `evento_id` e `votacao_id` podem ser nulos; a consistência é regra do coletor (seção 6).
- **`partido.sigla` não é única.** Ligações sempre pelo id. Única exceção: `/blocos/{id}/partidos`, que devolve o id errado (ver 12.3).
- **`noticia_fonte` e `trecho_rag` não têm FK para as tabelas da API:** guardam `tipo` + `ref_id`, e o back-end confere se o registro existe.
- **Valores fixos** (status, tipo, papel etc.): declare as listas como constantes no `models.py` (ex.: `NOTICIA_STATUS = ("rascunho", "em_revisao", "publicada", "rejeitada", "arquivada")`) e use `CheckConstraint` com nome `ck_<tabela>_<campo>`. O service também valida.
- **Índice vetorial** (sqlite-vec) **não é uma das 32 tabelas** e não é modelo SQLAlchemy: é uma tabela virtual criada na Fase 3, reconstruível a partir de `trecho_rag`.

Legenda das tabelas abaixo: **PK** chave primária · **FK** chave estrangeira · **Nulo** = `nullable=True` (`Optional[...]`) · "não" = `nullable=False`.

### 5.2 Classificação

| Classificação | Tabelas |
|---|---|
| Entidades fortes (18) | proposicao, tema, votacao, deputado, partido, orgao, evento, legislatura, lideranca, bloco, frente, noticia, geracao_ia, trecho_rag, administrador, log_sistema, coleta, visitante |
| Associativas (10) | proposicao_autor, proposicao_tema, voto, deputado_orgao, bloco_partido, frente_membro, votacao_proposicao, noticia_revisao, geracao_trecho, visitante_tema |
| Entidades fracas (4) | tramitacao, orientacao, pauta_item, noticia_fonte |
| Abstratas | nenhuma (sem herança) |

### 5.3 Tabelas da API da Câmara (21)

#### Pacote `proposicoes`

**proposicao** (`Proposicao`) — projeto de lei, PEC ou outra proposta. Fonte: `/proposicoes/{id}`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| id | Integer | não | PK (id da API) | id |
| sigla_tipo | Text | não | | siglaTipo |
| cod_tipo | Integer | não | | codTipo |
| descricao_tipo | Text | não | | descricaoTipo |
| numero | Integer | não | | numero |
| ano | Integer | não | index | ano |
| ementa | Text | não | | ementa |
| ementa_detalhada | Text | sim | | ementaDetalhada |
| keywords | Text | sim | | keywords |
| data_apresentacao | DateTime | não | index | dataApresentacao |
| url_inteiro_teor | Text | não | | urlInteiroTeor |
| cod_situacao | Integer | sim | | statusProposicao.codSituacao |
| situacao | Text | sim | | statusProposicao.descricaoSituacao |
| data_status | DateTime | não | | statusProposicao.dataHora |
| regime | Text | não | | statusProposicao.regime |
| apreciacao | Text | não | | statusProposicao.apreciacao |

**proposicao_autor** (`ProposicaoAutor`, associativa) — quem assina. Fonte: `/proposicoes/{id}/autores`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| proposicao_id | Integer | não | PK, FK proposicao.id | id da rota |
| ordem | Integer | não | PK | ordemAssinatura |
| deputado_id | Integer | sim | FK deputado.id, index (nulo se o autor não é deputado) | extraído da uri |
| nome | Text | não | | nome |
| cod_tipo | Integer | não | | codTipo |
| tipo | Text | não | | tipo |
| proponente | Boolean | não | | proponente (0/1) |

**proposicao_tema** (`ProposicaoTema`, associativa). Fonte: `/proposicoes/{id}/temas`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| proposicao_id | Integer | não | PK, FK proposicao.id | id da rota |
| cod_tema | Integer | não | PK, FK tema.cod_tema | codTema |
| relevancia | Integer | não | | relevancia |

**tema** (`Tema`) — tema oficial, usado como categoria do portal. Fonte: `/referencias/proposicoes/codTema`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| cod_tema | Integer | não | PK (`autoincrement=False`) | cod (vem como texto, converter) |
| nome | Text | não | | nome |
| icone | Text | não | nome do ícone Material Symbols, definido pelo portal | — |

**tramitacao** (`Tramitacao`, entidade fraca) — cada passo do andamento. Fonte: `/proposicoes/{id}/tramitacoes`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| proposicao_id | Integer | não | PK, FK proposicao.id | id da rota |
| sequencia | Integer | não | PK | sequencia |
| data_hora | DateTime | não | | dataHora |
| orgao_id | Integer | não | FK orgao.id, index | extraído de uriOrgao |
| sigla_orgao | Text | não | | siglaOrgao |
| cod_tipo_tramitacao | Text | não | | codTipoTramitacao |
| descricao | Text | não | | descricaoTramitacao |
| cod_situacao | Integer | sim | | codSituacao |
| situacao | Text | sim | | descricaoSituacao |
| despacho | Text | não | | despacho |
| regime | Text | não | | regime |
| ambito | Text | não | | ambito |
| apreciacao | Text | não | | apreciacao |
| url | Text | sim | | url |

#### Pacote `votacoes`

**votacao** (`Votacao`) — deliberação em Plenário ou comissão. Fonte: `/votacoes`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| id | Text | não | PK, ex.: "2310837-8" | id |
| data | Date | não | index | data |
| data_hora_registro | DateTime | não | | dataHoraRegistro |
| evento_id | Integer | sim | FK evento.id, index | idEvento |
| orgao_id | Integer | não | FK orgao.id, index | idOrgao |
| sigla_orgao | Text | não | | siglaOrgao |
| proposicao_id | Integer | sim | FK proposicao.id, index (D2) | extraído de uriProposicaoObjeto |
| descricao | Text | não | | descricao |
| aprovacao | Boolean | sim | | aprovacao (1/0) |

**voto** (`Voto`, associativa) — voto nominal de cada deputado. Fonte: `/votacoes/{id}/votos`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| votacao_id | Text | não | PK, FK votacao.id | id da rota |
| deputado_id | Integer | não | PK, FK deputado.id | deputado_.id |
| tipo_voto | Text | não | Sim, Não, Abstenção, Obstrução… | tipoVoto |
| data_registro | DateTime | não | | dataRegistroVoto |
| sigla_partido | Text | não | partido no dia do voto (D4) | deputado_.siglaPartido |

**orientacao** (`Orientacao`, entidade fraca) — orientação de partido ou bloco (só Plenário). Fonte: `/votacoes/{id}/orientacoes`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| votacao_id | Text | não | PK, FK votacao.id | id da rota |
| partido_bloco | Text | não | PK | siglaPartidoBloco |
| tipo_lideranca | Text | não | P (partido) ou B (bloco) | codTipoLideranca |
| partido_id | Integer | sim | FK partido.id, index (bloco não tem id) | codPartidoBloco |
| orientacao | Text | não | | orientacaoVoto |

**votacao_proposicao** (`VotacaoProposicao`, associativa) — proposições afetadas. Fonte: `/votacoes/{id}` → `proposicoesAfetadas`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| votacao_id | Text | não | PK, FK votacao.id | id da rota |
| proposicao_id | Integer | não | PK, FK proposicao.id | proposicoesAfetadas[].id |

#### Pacote `parlamentares`

**deputado** (`Deputado`). Fonte: listagem `/deputados` (com `idLegislatura`).

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| id | Integer | não | PK | id |
| nome | Text | não | index | nome |
| sigla_uf | Text | não | | siglaUf |
| sexo | Text | não | M ou F (filtro siglaSexo da chamada) | — |
| email | Text | sim | | email |
| url_foto | Text | não | | urlFoto |
| id_legislatura | Integer | não | FK legislatura.id, index | idLegislatura |
| partido_id | Integer | sim | FK partido.id, index (D3) | extraído de uriPartido |
| sigla_partido | Text | não | sempre preenchida (D3) | siglaPartido |

**partido** (`Partido`). Fonte: `/partidos?idLegislatura=…`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| id | Integer | não | PK | id |
| sigla | Text | não | **sem UNIQUE** | sigla |
| nome | Text | não | | nome |
| url_logo | Text | sim | | /partidos/{id}: urlLogo |

**legislatura** (`Legislatura`). Fonte: `/legislaturas`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| id | Integer | não | PK | id |
| data_inicio | Date | não | | dataInicio |
| data_fim | Date | não | | dataFim |

**lideranca** (`Lideranca`) — líderes e vice-líderes das bancadas. Fonte: `/legislaturas/{id}/lideres`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| id | Integer | não | PK **gerada pelo banco** (autoincrement) | — |
| deputado_id | Integer | não | FK deputado.id, index | parlamentar.id |
| bancada_nome | Text | não | | bancada.nome |
| bancada_tipo | Text | não | partido, bloco, Governo, Oposição… | bancada.tipo |
| titulo | Text | não | Líder, Vice-líder… | titulo |
| data_inicio | Date | não | | dataInicio |
| data_fim | Date | sim | | dataFim |

**bloco** (`Bloco`). Fonte: `/blocos?idLegislatura=…`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| id | Integer | não | PK | id (texto, converter) |
| nome | Text | não | | nome |
| federacao | Boolean | não | | federacao |
| id_legislatura | Integer | não | FK legislatura.id, index | idLegislatura (texto, converter) |

**bloco_partido** (`BlocoPartido`, associativa) — composição atual. Fonte: `/blocos/{id}/partidos`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| bloco_id | Integer | não | PK, FK bloco.id | id da rota |
| partido_id | Integer | não | PK, FK partido.id | id |

**frente** (`Frente`). Fonte: `/frentes?idLegislatura=…` e `/frentes/{id}`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| id | Integer | não | PK | id |
| titulo | Text | não | | titulo |
| id_legislatura | Integer | não | FK legislatura.id, index | idLegislatura |
| keywords | Text | sim | | /frentes/{id}: keywords |

**frente_membro** (`FrenteMembro`, associativa). Fonte: `/frentes/{id}/membros`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| frente_id | Integer | não | PK, FK frente.id | id da rota |
| deputado_id | Integer | não | PK, FK deputado.id | id |
| cod_titulo | Text | não | | codTitulo |
| titulo | Text | não | Signatário, Coordenador, Presidente | titulo |
| data_inicio | Date | sim | | dataInicio |
| data_fim | Date | sim | | dataFim |

#### Pacote `orgaos`

**orgao** (`Orgao`) — Plenário, comissões, Mesa Diretora (id 4). Fonte: `/orgaos`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| id | Integer | não | PK | id |
| sigla | Text | não | | sigla |
| nome | Text | não | | nome |
| apelido | Text | não | | apelido |
| cod_tipo_orgao | Integer | não | | codTipoOrgao |
| tipo_orgao | Text | não | | tipoOrgao |

**deputado_orgao** (`DeputadoOrgao`, associativa) — cargos em órgãos. Fonte: `/orgaos/{id}/membros` e `/legislaturas/{id}/mesa`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| deputado_id | Integer | não | PK, FK deputado.id | id |
| orgao_id | Integer | não | PK, FK orgao.id | id da rota (Mesa = 4) |
| data_inicio | Date | não | PK | dataInicio |
| cod_titulo | Text | não | número ou texto: gravar como texto | codTitulo |
| titulo | Text | não | Presidente, Titular, Suplente… | titulo |
| data_fim | Date | sim | | dataFim |

**evento** (`Evento`) — sessão ou reunião. Fonte: `/eventos`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| id | Integer | não | PK | id |
| data_hora_inicio | DateTime | não | index | dataHoraInicio |
| data_hora_fim | DateTime | sim | | dataHoraFim |
| situacao | Text | não | | situacao |
| descricao_tipo | Text | não | | descricaoTipo |
| descricao | Text | não | | descricao |
| orgao_id | Integer | não | FK orgao.id, index (primeiro órgão da lista, D1) | orgaos[0].id |
| local | Text | sim | | localCamara.nome ou localExterno |
| url_registro | Text | sim | | urlRegistro |
| url_documento_pauta | Text | sim | | /eventos/{id}: urlDocumentoPauta |

**pauta_item** (`PautaItem`, entidade fraca). Fonte: `/eventos/{id}/pauta`.

| Coluna | Tipo | Nulo | Chave / regra | Campo na API |
|---|---|---|---|---|
| evento_id | Integer | não | PK, FK evento.id | id da rota |
| ordem | Integer | não | PK | ordem |
| proposicao_id | Integer | sim | FK proposicao.id, index | proposicao_.id |
| proposicao_relacionada_id | Integer | sim | **sem FK** | proposicaoRelacionada_.id |
| relator_id | Integer | sim | FK deputado.id, index | relator.id |
| regime | Text | sim | | regime |
| situacao_item | Text | sim | | situacaoItem |
| topico | Text | sim | | topico |
| texto_parecer | Text | sim | | textoParecer |
| votacao_id | Text | sim | FK votacao.id, index | extraído de uriVotacao |

### 5.4 Tabelas do portal (11)

#### Pacote `auth`

**administrador** (`Administrador`) — membro da equipe.

| Coluna | Tipo | Nulo | Chave / regra |
|---|---|---|---|
| id | Integer | não | PK (autoincrement) |
| nome | String(100) | não | |
| email | String(254) | não | UNIQUE, index |
| senha_hash | String(255) | não | `werkzeug.security.generate_password_hash` |
| papel | String(20) | não | admin, editor (default editor) |
| ativo | Boolean | não | default True |
| criado_em | DateTime | não | server_default now |
| ultimo_acesso | DateTime | sim | |

Métodos esperados: `set_senha(senha)` e `confere_senha(senha)` (Werkzeug). Nunca expor `senha_hash` em JSON.

#### Pacote `noticias`

**noticia** (`Noticia`) — notícia ou relatório escrito pela IA ou pela equipe.

| Coluna | Tipo | Nulo | Chave / regra |
|---|---|---|---|
| id | Integer | não | PK (autoincrement) |
| titulo | String(200) | não | |
| slug | String(220) | não | UNIQUE, index; gerado do título; não muda depois de publicado |
| resumo | String(500) | não | card da página inicial |
| corpo | Text | não | |
| tipo | String(20) | não | noticia, relatorio (default noticia) |
| origem | String(20) | não | ia, equipe |
| cod_tema | Integer | não | FK tema.cod_tema, index (tema principal) |
| status | String(20) | não | rascunho, em_revisao, publicada, rejeitada, arquivada (default rascunho), index |
| criado_em | DateTime | não | server_default now |
| publicado_em | DateTime | sim | index |
| alterado_em | DateTime | sim | preenchido pelo service quando o texto muda (**não** usar `onupdate`, senão somar visualização mudaria a data) |
| visualizacoes | Integer | não | default 0 |

Fluxo de status: `rascunho → em_revisao → publicada`, ou `rejeitada` / `arquivada`. Quem publicou e quando sai de `noticia_revisao` (última ação `publicou`).

**noticia_fonte** (`NoticiaFonte`, entidade fraca) — registros da API usados na notícia.

| Coluna | Tipo | Nulo | Chave / regra |
|---|---|---|---|
| noticia_id | Integer | não | PK, FK noticia.id |
| tipo | String(20) | não | PK; proposicao, votacao, deputado, evento, orgao, partido |
| ref_id | String(20) | não | PK; id do registro, **sem FK** (cabe id de votação) |
| ordem | Integer | não | 1 = fonte principal (gera o link da fonte oficial) |

**noticia_revisao** (`NoticiaRevisao`, associativa administrador ↔ noticia) — histórico de revisão.

| Coluna | Tipo | Nulo | Chave / regra |
|---|---|---|---|
| id | Integer | não | PK (autoincrement) |
| noticia_id | Integer | não | FK noticia.id, index |
| admin_id | Integer | não | FK administrador.id, index |
| acao | String(20) | não | editou, aprovou, rejeitou, publicou, arquivou |
| comentario | Text | sim | retorno para melhorar a IA |
| data_hora | DateTime | não | server_default now |

#### Pacote `ia`

**geracao_ia** (`GeracaoIA`) — cada execução da IA, mesmo com erro.

| Coluna | Tipo | Nulo | Chave / regra |
|---|---|---|---|
| id | Integer | não | PK (autoincrement) |
| noticia_id | Integer | sim | FK noticia.id, index (nulo se a geração falhou) |
| modelo_geracao | String(100) | não | modelo de linguagem que escreveu |
| modelo_embedding | String(100) | não | ex.: eduagarcia/RoBERTaLexPT-base |
| consulta | Text | não | texto usado na busca do RAG |
| top_k | Integer | não | default 8 |
| versao_prompt | String(50) | não | |
| entrada | Text | não | JSON com os ids usados |
| tokens_entrada | Integer | sim | |
| tokens_saida | Integer | sim | |
| duracao_ms | Integer | sim | |
| status | String(20) | não | ok, erro |
| erro | Text | sim | |
| criado_em | DateTime | não | server_default now |

**trecho_rag** (`TrechoRAG`) — pedaço de texto com embedding.

| Coluna | Tipo | Nulo | Chave / regra |
|---|---|---|---|
| id | Integer | não | PK (autoincrement); é o id usado na tabela virtual do sqlite-vec |
| tipo | String(20) | não | proposicao, tramitacao, votacao, evento, pauta_item |
| ref_id | String(20) | não | id do registro de origem, **sem FK** |
| parte | Integer | não | 1, 2, 3… quando o texto vira vários trechos |
| texto | Text | não | até 400 tokens |
| tokens | Integer | não | |
| embedding | LargeBinary | não | 768 float32 = 3.072 bytes (`numpy.float32(...).tobytes()`) |
| modelo_embedding | String(100) | não | |
| hash_texto | String(64) | não | SHA-256 em hexadecimal |
| criado_em | DateTime | não | server_default now |

Restrições: `UniqueConstraint("tipo", "ref_id", "parte", "modelo_embedding", name="uq_trecho_rag_tipo_ref_parte_modelo")` e índice em (`tipo`, `ref_id`).

**geracao_trecho** (`GeracaoTrecho`, associativa geracao_ia ↔ trecho_rag) — trechos recuperados em cada geração.

| Coluna | Tipo | Nulo | Chave / regra |
|---|---|---|---|
| geracao_id | Integer | não | PK, FK geracao_ia.id |
| trecho_id | Integer | não | PK, FK trecho_rag.id |
| posicao | Integer | não | 1 = mais parecido |
| similaridade | Float | não | cosseno |

#### Pacote `sistema`

**log_sistema** (`LogSistema`) — ações do coletor, da IA e dos administradores.

| Coluna | Tipo | Nulo | Chave / regra |
|---|---|---|---|
| id | Integer | não | PK (autoincrement) |
| data_hora | DateTime | não | server_default now, index |
| nivel | String(10) | não | info, aviso, erro |
| modulo | String(20) | não | coletor, IA, admin |
| acao | String(100) | não | |
| descricao | Text | não | |
| admin_id | Integer | sim | FK administrador.id, index |
| coleta_id | Integer | sim | FK coleta.id, index |
| entidade | String(50) | sim | nome da tabela |
| entidade_id | String(50) | sim | id da linha (número ou id de votação) |

**coleta** (`Coleta`) — cada chamada do coletor.

| Coluna | Tipo | Nulo | Chave / regra |
|---|---|---|---|
| id | Integer | não | PK (autoincrement) |
| endpoint | String(255) | não | |
| parametros | Text | sim | JSON |
| iniciado_em | DateTime | não | server_default now |
| finalizado_em | DateTime | sim | |
| total_itens | Integer | não | default 0 |
| itens_novos | Integer | não | default 0 |
| itens_atualizados | Integer | não | default 0 |
| status | String(20) | não | ok, parcial, erro |
| mensagem_erro | Text | sim | |

#### Pacote `visitantes`

**visitante** (`Visitante`) — visitante anônimo, identificado por cookie.

| Coluna | Tipo | Nulo | Chave / regra |
|---|---|---|---|
| id | String(36) | não | PK, UUID do cookie |
| preferencias | Text | sim | JSON |
| consentimento | Boolean | não | aceite de cookies (LGPD), default False |
| criado_em | DateTime | não | server_default now |
| ultimo_acesso | DateTime | não | server_default now; apagado após 12 meses sem acesso |

**visitante_tema** (`VisitanteTema`, associativa).

| Coluna | Tipo | Nulo | Chave / regra |
|---|---|---|---|
| visitante_id | String(36) | não | PK, FK visitante.id |
| cod_tema | Integer | não | PK, FK tema.cod_tema |
| acessos | Integer | não | default 0 |

### 5.5 Relacionamentos 1:N (42) e nomes dos atributos

Use estes nomes nos `relationship(..., back_populates=...)`. "Cascade" = `cascade="all, delete-orphan"` no lado pai.

| # | Pai | Filho (FK) | Card. | Atributo no pai | Atributo no filho | Cascade |
|---|---|---|---|---|---|---|
| 1 | proposicao | proposicao_autor (proposicao_id) | 1 : 1..N | autores | proposicao | sim |
| 2 | proposicao | tramitacao (proposicao_id) | 1 : 1..N | tramitacoes | proposicao | sim |
| 3 | proposicao | proposicao_tema (proposicao_id) | 1 : 0..N | temas | proposicao | sim |
| 4 | proposicao | votacao (proposicao_id) | 0..1 : 0..N | votacoes | proposicao | |
| 5 | tema | proposicao_tema (cod_tema) | 1 : 0..N | proposicoes | tema | |
| 6 | tema | noticia (cod_tema) | 1 : 0..N | noticias | tema | |
| 7 | tema | visitante_tema (cod_tema) | 1 : 0..N | visitantes | tema | |
| 8 | deputado | proposicao_autor (deputado_id) | 0..1 : 0..N | autorias | deputado | |
| 9 | deputado | voto (deputado_id) | 1 : 0..N | votos | deputado | |
| 10 | partido | deputado (partido_id) | 0..1 : 0..N | deputados | partido | |
| 11 | partido | orientacao (partido_id) | 0..1 : 0..N | orientacoes | partido | |
| 12 | legislatura | deputado (id_legislatura) | 1 : 0..N | deputados | legislatura | |
| 13 | votacao | voto (votacao_id) | 1 : 0..N | votos | votacao | sim |
| 14 | votacao | orientacao (votacao_id) | 1 : 0..N | orientacoes | votacao | sim |
| 15 | orgao | tramitacao (orgao_id) | 1 : 0..N | tramitacoes | orgao | |
| 16 | orgao | evento (orgao_id) | 1 : 0..N | eventos | orgao | |
| 17 | orgao | votacao (orgao_id) | 1 : 0..N | votacoes | orgao | |
| 18 | evento | votacao (evento_id) | 0..1 : 0..N | votacoes | evento | |
| 19 | visitante | visitante_tema (visitante_id) | 1 : 0..N | temas | visitante | sim |
| 20 | administrador | log_sistema (admin_id) | 0..1 : 0..N | logs | administrador | |
| 21 | coleta | log_sistema (coleta_id) | 0..1 : 0..N | logs | coleta | |
| 22 | noticia | noticia_fonte (noticia_id) | 1 : 0..N | fontes | noticia | sim |
| 23 | noticia | noticia_revisao (noticia_id) | 1 : 0..N | revisoes | noticia | sim |
| 24 | administrador | noticia_revisao (admin_id) | 1 : 0..N | revisoes | administrador | |
| 25 | noticia | geracao_ia (noticia_id) | 0..1 : 0..N | geracoes | noticia | |
| 26 | geracao_ia | geracao_trecho (geracao_id) | 1 : 0..N | trechos | geracao | sim |
| 27 | trecho_rag | geracao_trecho (trecho_id) | 1 : 0..N | geracoes | trecho | |
| 28 | deputado | lideranca (deputado_id) | 1 : 0..N | liderancas | deputado | |
| 29 | deputado | deputado_orgao (deputado_id) | 1 : 0..N | cargos | deputado | |
| 30 | orgao | deputado_orgao (orgao_id) | 1 : 0..N | membros | orgao | |
| 31 | legislatura | bloco (id_legislatura) | 1 : 0..N | blocos | legislatura | |
| 32 | bloco | bloco_partido (bloco_id) | 1 : 1..N | partidos | bloco | sim |
| 33 | partido | bloco_partido (partido_id) | 1 : 0..N | blocos | partido | |
| 34 | legislatura | frente (id_legislatura) | 1 : 0..N | frentes | legislatura | |
| 35 | frente | frente_membro (frente_id) | 1 : 0..N | membros | frente | sim |
| 36 | deputado | frente_membro (deputado_id) | 1 : 0..N | frentes | deputado | |
| 37 | evento | pauta_item (evento_id) | 1 : 0..N | pauta | evento | sim |
| 38 | proposicao | pauta_item (proposicao_id) | 0..1 : 0..N | pautas | proposicao | |
| 39 | deputado | pauta_item (relator_id) | 0..1 : 0..N | relatorias | relator | |
| 40 | votacao | pauta_item (votacao_id) | 0..1 : 0..N | itens_pauta | votacao | |
| 41 | votacao | votacao_proposicao (votacao_id) | 1 : 0..N | proposicoes_afetadas | votacao | sim |
| 42 | proposicao | votacao_proposicao (proposicao_id) | 1 : 0..N | votacoes_afetadas | proposicao | sim |

Observações:
- Os relacionamentos com tabelas de outro pacote usam o nome da classe em string e o import em `TYPE_CHECKING` (ex.: `Votacao.orgao` aponta para `"Orgao"` de `desperta.orgaos.models`).
- Em `PautaItem.relator` declare `foreign_keys=[relator_id]` (o nome do atributo é diferente do nome da tabela).
- Apagar um visitante (tarefa LGPD) deve apagar os seus `visitante_tema`: use o ORM (`db.session.delete(visitante)`) para o cascade funcionar.

### 5.6 Relacionamentos N:N (10)

| Relacionamento | Tabela associativa | Chave |
|---|---|---|
| proposicao ↔ tema | proposicao_tema | proposicao_id + cod_tema |
| proposicao ↔ deputado | proposicao_autor | proposicao_id + ordem |
| votacao ↔ deputado | voto | votacao_id + deputado_id |
| visitante ↔ tema | visitante_tema | visitante_id + cod_tema |
| administrador ↔ noticia | noticia_revisao | id (uma linha por ação) |
| deputado ↔ orgao | deputado_orgao | deputado_id + orgao_id + data_inicio |
| bloco ↔ partido | bloco_partido | bloco_id + partido_id |
| frente ↔ deputado | frente_membro | frente_id + deputado_id |
| votacao ↔ proposicao | votacao_proposicao | votacao_id + proposicao_id |
| geracao_ia ↔ trecho_rag | geracao_trecho | geracao_id + trecho_id |

### 5.7 Exemplo esperado de modelo do Desperta (estilo TaskFlow)

`desperta/proposicoes/models.py` (trecho):
```python
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from desperta.ext.db import db

if TYPE_CHECKING:
    from desperta.orgaos.models import Orgao, PautaItem
    from desperta.votacoes.models import Votacao, VotacaoProposicao


# === Proposicao (projeto de lei, PEC ou outra proposta) ===
class Proposicao(db.Model):
    __tablename__ = "proposicao"

    # ======================================================
    # IDENTIFICACAO (mesmo id da API da Camara)
    # ======================================================
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=False)
    sigla_tipo: Mapped[str] = mapped_column(db.Text, nullable=False)
    cod_tipo: Mapped[int] = mapped_column(db.Integer, nullable=False)
    descricao_tipo: Mapped[str] = mapped_column(db.Text, nullable=False)
    numero: Mapped[int] = mapped_column(db.Integer, nullable=False)
    ano: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)

    # ======================================================
    # CONTEUDO
    # ======================================================
    ementa: Mapped[str] = mapped_column(db.Text, nullable=False)
    ementa_detalhada: Mapped[Optional[str]] = mapped_column(db.Text)
    keywords: Mapped[Optional[str]] = mapped_column(db.Text)
    data_apresentacao: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, index=True)
    url_inteiro_teor: Mapped[str] = mapped_column(db.Text, nullable=False)

    # ======================================================
    # SITUACAO ATUAL (statusProposicao)
    # ======================================================
    cod_situacao: Mapped[Optional[int]] = mapped_column(db.Integer)
    situacao: Mapped[Optional[str]] = mapped_column(db.Text)
    data_status: Mapped[datetime] = mapped_column(db.DateTime, nullable=False)
    regime: Mapped[str] = mapped_column(db.Text, nullable=False)
    apreciacao: Mapped[str] = mapped_column(db.Text, nullable=False)

    # ------------------------------------------------------
    # AUTORES
    # ------------------------------------------------------
    autores: Mapped[List["ProposicaoAutor"]] = relationship(
        "ProposicaoAutor",
        back_populates="proposicao",
        cascade="all, delete-orphan"
    )

    # ------------------------------------------------------
    # TRAMITACOES
    # ------------------------------------------------------
    tramitacoes: Mapped[List["Tramitacao"]] = relationship(
        "Tramitacao",
        back_populates="proposicao",
        cascade="all, delete-orphan",
        order_by="Tramitacao.sequencia"
    )

    # ... temas, votacoes, pautas, votacoes_afetadas (ver tabela 5.5)

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Proposicao id={self.id} "
            f"{self.sigla_tipo} {self.numero}/{self.ano}>"
        )


# === Tramitacao (passo do andamento da proposicao) ===
class Tramitacao(db.Model):
    __tablename__ = "tramitacao"

    proposicao_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("proposicao.id"), primary_key=True)
    sequencia: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=False)
    data_hora: Mapped[datetime] = mapped_column(db.DateTime, nullable=False)
    orgao_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("orgao.id"), nullable=False, index=True)
    # ... demais colunas da secao 5.3

    # ------------------------------------------------------
    # PROPOSICAO
    # ------------------------------------------------------
    proposicao: Mapped["Proposicao"] = relationship(
        "Proposicao",
        back_populates="tramitacoes"
    )

    # ------------------------------------------------------
    # ORGAO
    # ------------------------------------------------------
    orgao: Mapped["Orgao"] = relationship(
        "Orgao",
        back_populates="tramitacoes"
    )
```

---

## 6. Regras do coletor e do back-end (para as fases seguintes)

Ficam no código, não no banco. Respeite estas regras quando chegar a hora:

- O envelope `dados`, os `links` de paginação, os campos `uri*` e os parâmetros de busca **não vão para o banco**. Das `uri` o coletor extrai ids (deputado, partido, órgão).
- **Ordem de gravação** (o SQLite confere FK): legislatura → partido → deputado → orgao → tema → proposicao (+ autores, temas, tramitações) → evento (+ pauta) → votacao (+ votos, orientações, votacao_proposicao) → lideranca, deputado_orgao, bloco/bloco_partido, frente/frente_membro.
- `/proposicoes`: listar com `dataInicio`/`dataFim` (padrão: últimos 30 dias) e, para cada id, chamar o detalhe, `/autores`, `/temas` e `/tramitacoes`. Achatar `statusProposicao`.
- `/eventos`: `localCamara`/`localExterno` viram `local`; o primeiro de `orgaos[]` vira `orgao_id` (D1), e cada órgão da lista é cadastrado (D5). Recoletar os últimos dias até o evento ficar encerrado.
- `/votacoes`: `dataInicio` e `dataFim` no mesmo ano; máximo 100 por página. Sem `uriProposicaoObjeto`, `proposicao_id` fica nulo. A proposição objeto também entra em `votacao_proposicao`. Votação simbólica tem `/votos` vazio; ausentes não aparecem; orientações só no Plenário.
- `/partidos`: usar `idLegislatura` para incluir antigos; `url_logo` de `/partidos/{id}`.
- `/deputados`: tudo da listagem; `sexo` vem chamando com `siglaSexo=M` e `siglaSexo=F`; upsert pelo id.
- `/legislaturas?data=<hoje>` para saber a legislatura atual.
- `pauta_item.votacao_id` só se a votação for do mesmo evento.
- Orientação: **não ligar ao bloco** (ver decisão 10.1). `partido_bloco` guarda o texto como a API manda; `partido_id` só é preenchido quando `tipo_lideranca = P` e o partido existe.
- Só `tema` vai para o banco das referências; tipos, situações e UF ficam em cache no back-end.
- Rede: paginação, novas tentativas e backoff exponencial (RNF02). Cada chamada grava uma `coleta` e linhas em `log_sistema`.
- Portal: slug gerado do título e fixo após publicar; `noticia_fonte.ref_id` conferido no back-end; `visualizacoes` +1 a cada abertura; sem consentimento não grava `visitante_tema`; tarefa diária apaga visitantes sem acesso há 12 meses.
- IA: cada execução grava `geracao_ia`, mesmo com erro (noticia_id nulo); os ids usados vão para `noticia_fonte`; prioriza o que veio em `itens_novos` da coleta.

### 6.1 RAG com a RoBERTaLexPT (Fase 3)

- Carregar com `AutoTokenizer` e `AutoModel` (`eduagarcia/RoBERTaLexPT-base`), `model.eval()` e `torch.no_grad()`, uma vez no início do módulo de IA; CPU.
- Limite de 512 tokens; trechos de até 400 tokens com 50 de sobreposição; textos curtos ficam num trecho só.
- Embedding: mean pooling com a máscara de atenção + normalização L2 (768 dimensões, float32).
- Índice: tabela virtual do sqlite-vec ligada a `trecho_rag.id`, por exemplo `CREATE VIRTUAL TABLE vec_trecho USING vec0(trecho_id INTEGER PRIMARY KEY, embedding float[768] distance_metric=cosine)`. Criada pelo módulo de IA (não pelo `create_all`) e reconstruível a partir de `trecho_rag`.
- Busca: 8 trechos mais parecidos, com filtro por tipo e data quando preciso; gravar em `geracao_trecho` com `posicao` e `similaridade`.
- Só registros novos ou com `hash_texto` diferente recebem embedding depois de cada coleta.
- O que vira trecho: proposição (sigla, número/ano, ementa, ementa detalhada, keywords); tramitação (data, órgão, situação, despacho); votação (descrição, órgão, data, resultado); evento e item de pauta (descrição, tópico, texto do parecer).
- Começar com o modelo original e medir a busca; fine-tuning com sentence-transformers só se precisar.
- **O modelo de linguagem que escreve ainda não foi escolhido.** Deixe uma interface (`ia/gerador.py`) com uma implementação falsa para teste até o grupo decidir.

### 6.2 Voz (Fase 5)

- `POST /api/voz/transcrever`: recebe o áudio gravado pelo navegador (MediaRecorder), transcreve com faster-whisper (`small`, `language="pt"`) e devolve o texto. **Não guardar o áudio.**
- Leitura: ao publicar (ou alterar) uma notícia, gerar o áudio com o Piper (voz pt-BR) em `AUDIO_DIR/<slug>.wav`; o botão "Ouvir" toca esse arquivo. Alternativa no front-end: Web Speech API.

---

## 7. Fases do desenvolvimento

### Fase 1 — Banco de dados (CONCLUÍDA em 30/10/2026)

Resultado: 32 tabelas, 42 relacionamentos, 126 testes passando, lint sem erros. Os passos e critérios abaixo ficam como registro.

Passos:
1. Criar a estrutura da seção 4: `pyproject.toml`, `tasks.py`, `app.py`, `.flaskenv`, `.env.example`, `.gitignore` (venv, instance, `.env`, `__pycache__`, `*.db`), `README.md` curto com como instalar e rodar.
2. Criar `desperta/__init__.py`, `config.py`, `ext/db`, `ext/cli` (comandos `flask init-db` = `db.create_all()` e `flask drop-db`) e `ext/cors`.
3. Criar os 9 pacotes de domínio com `__init__.py`, `routes.py` (blueprint vazio) e `services.py` (vazio).
4. Escrever os 32 modelos nos `models.py`, seguindo as seções 5.3 a 5.7.
5. Escrever os testes em `tests/` (fixture `app` com `TestConfig`, fixture `db` que faz `create_all()`/`drop_all()`).
6. Rodar `invoke install`, `invoke initdb` e `invoke test`, e mostrar o resultado.
7. Mostrar uma sessão de exemplo no `flask shell` (como na Unidade 06): criar legislatura, partido, deputado, órgão, proposição com tramitação, votação com voto; notícia com fonte e revisão; consultar os relacionamentos.

Critérios de pronto (os testes devem cobrir):
- `db.metadata.tables` tem **exatamente as 32 tabelas** com os nomes da seção 5.
- As PKs compostas estão certas (ex.: `deputado_orgao` = deputado_id + orgao_id + data_inicio).
- `votacao.id` aceita `"2310837-8"`.
- `noticia.slug`, `administrador.email` e o único de `trecho_rag` barram duplicatas (`IntegrityError` + `rollback()`).
- Duas linhas de `partido` com a mesma sigla são aceitas.
- FK é conferida no SQLite (inserir `voto` com deputado inexistente falha).
- Cascade: apagar `noticia` apaga fontes e revisões; apagar `visitante` apaga `visitante_tema`; apagar `proposicao` apaga autores, temas e tramitações.
- `embedding` grava e lê 3.072 bytes sem perda.
- `CheckConstraint` barra status inválido em `noticia`.
- `__repr__` de cada modelo funciona.
- `invoke lint` sem erros.

### Fase 1.5 — Ajuste físico do banco (CONCLUÍDA em 30/10/2026: 239 testes, `flask db check` sem diferenças)
Seguir `docs/AJUSTE_BANCO_SISTEMA.md`: convenção de nomes, Flask-Migrate com a migração inicial, SQLite em WAL, colunas de sincronização, campos novos em `coleta`, chave natural em `lideranca`, índices, busca FTS5 e os testes da seção 13 daquele arquivo. Continua com 32 tabelas e 42 FKs.

### Fase 2 — Coletor (ATUAL, na branch `fase-2-coletor`)
Pacote `desperta/coletor/` (cliente HTTP com backoff, um módulo por endpoint, upsert pelo id), comandos `flask coletar ...` e tarefas invoke. Registra `coleta` e `log_sistema`. Testes com respostas da API gravadas em arquivos JSON (sem chamar a API real nos testes).

Além da seção 6, a Fase 2 precisa:
- **Backoff de verdade (RNF02):** a API já devolveu HTTP 504 em `/legislaturas/57/lideres` e em `/deputados?siglaSexo=M`. Repetir em 429 e 5xx com espera exponencial (ex.: 2, 4, 8, 16 s, até 5 tentativas) e timeout por chamada.
- **Um registro ruim não derruba a coleta (decisão 10.2):** gravar cada registro com `db.session.begin_nested()`; se der `IntegrityError` (ex.: campo `NOT NULL` vazio), desfazer só ele, registrar em `log_sistema` (nível `erro`, `entidade` e `entidade_id` preenchidos, nome da coluna na descrição) e marcar a `coleta` como `parcial`.
- **Primeira carga de validação:** rodar uma carga real maior (pelo menos um ano de proposições de vários tipos, inclusive antigas, votações e eventos) e entregar ao grupo a lista de colunas que falharam e quantas vezes. **Não afrouxar `nullable` por conta própria.**
- **Orientações:** seguir a decisão 10.1.
- **Pedidos do relatório da Fase 1.5:** seguir a decisão 11.4 (contadores HTTP, endpoints com 504, `nullable` testado numa cópia do banco).
- **Decisões depois do relatório da Fase 2:** seguir a seção 12. O que falta para fechar a fase está em 12.7.

### Fase 2b — Ajustes de `nullable` (logo depois da carga de validação)
O Flask-Migrate já foi iniciado na Fase 1.5. Quando o grupo decidir os ajustes de `nullable` da carga de validação, aplicá-los como uma nova migração (`flask db migrate` + revisão + `flask db upgrade`). Toda mudança no esquema é migração, não `create_all()`.

### Fase 3 — IA e RAG
Trechos, embeddings, índice sqlite-vec, busca, geração de rascunhos com o gerador ainda a definir, registro em `geracao_ia`, `geracao_trecho` e `noticia_fonte`.

### Fase 4 — API REST e área administrativa
Blueprints em `/api/...`: notícias publicadas (lista, por tema, busca, filtro por dia/mês/ano, detalhe pelo slug), proposição (tramitações), votação (votos e orientações), temas; visitante (cookie, consentimento, contagem por tema); área administrativa com login (sessão Flask + `SECRET_KEY`), papéis `editor`/`admin`, fluxo de status, histórico, coletas e log. Rotas finas, regras nos services. Antes do login, aplicar as decisões 10.4 (exclusão de registros), 10.5 (CORS) e 11.3 (`administrador.atualizado_em`). Também:
- **Datas na busca:** o filtro por dia, mês e ano vem em horário de Brasília; converter o início e o fim do período para UTC antes de chamar `buscar_noticias`, porque `publicado_em` está em UTC (senão notícias publicadas à noite caem no dia seguinte).
- **Teste de carga (RNF01):** com o banco da carga de validação, medir a página principal, a página do tema e a busca; meta abaixo de 2 s. Se algum índice faltar, criar por migração.

### Fase 5 — Front-end Vue 3 e voz
`frontend/` como no TaskFlow (Vite, Axios, proxy `/api`), Material Design, Material Symbols, página principal por tema, página do tema, busca (texto e voz), página da notícia (fonte, tramitação, votação, botão "Ouvir"), aviso de cookies, área administrativa.

### Fase 6 — Complementares, testes e apresentação
Personalização por tema, relatórios da IA, aviso de "dados desatualizados" (RNF05), ajustes e apresentação do MVP.

---

## 8. Fora do MVP (não implementar)

- Senado, STF e assembleias; newsletter por e-mail; contas e comentários de visitantes; aplicativo mobile; painéis analíticos.
- Tabelas futuras: `visitante_noticia`, `evento_orgao`, `evento_presenca`, `proposicao_relacionada`, histórico de blocos, datas dos órgãos, despesas (cota parlamentar), discursos, `efeitosRegistrados`, grupos interparlamentares.
- Fine-tuning da RoBERTaLexPT para classificar temas.
- **Redis.**
- **PostgreSQL** (evolução futura; ver 11.1).
- Histórico de membros de órgãos (`deputado_orgao`) e de blocos; tipos de proposição além de PL, PLP, PEC, MPV e PDL.

## 9. Em aberto (perguntar ao grupo antes de decidir)

- Qual modelo de linguagem generativo vai escrever as notícias.
- Voz exata do Piper em pt-BR (o valor em `Config` é só um padrão).
- Onde o projeto será publicado (servidor, HTTPS).
- Versão do Python para as fases 3 e 5: o projeto roda em Python 3.14. Se `pip install -e ".[ia]"` ou `".[voz]"` falhar por falta de pacote para essa versão (PyTorch, faster-whisper/CTranslate2, Piper), avisar o grupo e propor um ambiente com Python 3.12, sem trocar de biblioteca.

---

## 10. Decisões tomadas depois da Fase 1 (30/10/2026)

Respostas às pendências da seção 5 do relatório da Fase 1. Nenhuma delas muda tabela ou coluna.

### 10.1 Orientação e bloco: não ligar pelo nome
A API abrevia e corta o nome do bloco em `siglaPartidoBloco` (ex.: `Bl UniPpFdrPsdbCid...`), e `Governo`, `Maioria`, `Minoria` e `Oposição` também vêm com `codTipoLideranca = B`. Ligar pelo nome daria resultado errado.
- Decisão: a regra "orientação de bloco liga-se ao bloco pelo nome" **sai**. A orientação de bloco fica só com o texto de `partido_bloco`, exatamente como a API manda.
- `partido_id` continua preenchido para `tipo_lideranca = P`.
- Na exibição (Fase 4/5), o back-end separa três grupos: partidos (`P`), lideranças `Governo`, `Maioria`, `Minoria` e `Oposição` (`B` com esses nomes) e blocos (os demais `B`). Os nomes ficam numa constante no service.
- Ligar a orientação a `bloco` fica como evolução (por exemplo, comparando a composição em `bloco_partido`), fora do MVP.

### 10.2 Campos NOT NULL ainda não conferidos na API
O modelo continua como está. O coletor não pode cair por causa de um registro (Fase 2): cada registro em `begin_nested()`, erro vai para `log_sistema`, a coleta fica `parcial`. Depois da carga de validação, o grupo decide quais colunas viram opcionais, e isso entra como uma nova migração (Fase 2b).

### 10.3 Exceções à regra T1
Já eram decisão do grupo (28/10) e agora estão escritas na seção 5.1. Nada muda no código.

### 10.4 Apagar registro em uso (AssertionError do ORM)
- **Tabelas da API nunca são apagadas** pelo portal nem pelo coletor: o coletor só faz upsert. Não criar rota de exclusão para elas.
- **administrador** não é apagado: vira `ativo = False`, para manter o histórico de `noticia_revisao` e `log_sistema`.
- **noticia:** o fluxo normal é `arquivada`. Exclusão de verdade só para `rascunho` ou `rejeitada` e só por `admin`; antes, o service apaga ou desliga as `geracao_ia` ligadas (deixando `noticia_id` nulo).
- **tema:** não é apagado (vem da API).
- **visitante:** a tarefa LGPD apaga pelo ORM (`db.session.delete`), um a um ou em lotes, para o cascade levar `visitante_tema`.
- Regra geral nos services: antes de apagar, conferir se há filhos; se houver, não apagar e responder **HTTP 409** com mensagem clara. Capturar também `IntegrityError` e `AssertionError` no service e transformar em 409, para nunca virar erro 500.

### 10.5 CORS
- Em desenvolvimento, o front-end usa o proxy do Vite (`/api` → `http://localhost:5000`), então o CORS nem é usado.
- Na Fase 4, antes do login: `CORS_ORIGINS` em `Config`, lido de variável de ambiente (padrão `http://localhost:5173`), CORS só para essas origens em `/api/*`, com `supports_credentials=True`. Cookie de sessão com `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = "Lax"` e `SESSION_COOKIE_SECURE = True` em produção.

---

## 11. Decisões tomadas depois da Fase 1.5 (30/10/2026)

### 11.1 RNF03 e PostgreSQL
O texto antigo ("só trocar `DATABASE_URL`") deixou de ser verdade: a busca usa FTS5, `bm25` e gatilhos do SQLite, e o RAG vai usar o sqlite-vec. Decisão: o MVP fica no SQLite; o **PostgreSQL é evolução futura**, fora do MVP, e não deve ser preparado agora. Se um dia migrar, os modelos, as migrações e os services sem SQL próprio continuam iguais, e só é preciso refazer `desperta/ext/db/busca.py` (PostgreSQL: `tsvector` com `unaccent`) e o índice vetorial (pgvector). Por isso todo SQL específico do SQLite fica isolado em `desperta/ext/db/` (busca) e no módulo de vetores da Fase 3, nunca espalhado pelos services.

### 11.2 Nome `sqlite_autoindex`
O SQLite também gera esse nome para restrições `UNIQUE`, não só para PKs. O texto de `docs/AJUSTE_BANCO_SISTEMA.md` foi corrigido para aceitar PK e `UNIQUE`, como o teste já faz. Nada muda no código.

### 11.3 `administrador.atualizado_em`
Significa **só edição de cadastro** (nome, e-mail, papel, ativo, senha). Para seguir o mesmo padrão de `noticia.alterado_em` e do `SincronizacaoMixin`, tirar o `onupdate` dessa coluna e preenchê-la no service que edita o cadastro. O login grava só `ultimo_acesso`. Não precisa de migração (o `onupdate` é só do Python). Ajustar o teste da Fase 1.5 que espera a mudança automática: ele passa a testar o service. Fazer no começo da Fase 4.

### 11.4 Fase 2: pedidos do relatório da Fase 1.5
- O cliente HTTP conta `requisicoes` e `erros_http` em `coleta` desde a primeira versão, para a carga de validação já medir a instabilidade da API.
- A carga de validação inclui logo `/legislaturas/57/lideres` e `/deputados?siglaSexo=M`, que deram 504 na Fase 1 e ainda não foram avaliados.
- Toda mudança de `nullable` (Fase 2b) é migração, testada antes numa cópia do banco com os dados da carga (`cp instance/desperta.db /tmp/teste.db` e `DATABASE_URL=sqlite:////tmp/teste.db flask db upgrade`).

### 11.5 Manutenção
O aviso de depreciação de `get_engine` no `migrations/env.py` não afeta nada hoje. Ao atualizar o Flask-SQLAlchemy, simplificar esse trecho.

---

## 12. Decisões tomadas depois do relatório da Fase 2 (30/10/2026)

### 12.1 Volume da API e RF02
A API tem muito mais proposições do que o previsto (cerca de 13 mil só em março de 2025), e cada uma pede pelo menos 4 chamadas. Do jeito que estava, a rotina diária não terminaria em um dia. Decisões:
- **Não buscar de novo o que não mudou:** só chamar `/autores`, `/temas` e `/tramitacoes` quando a proposição é nova ou quando `statusProposicao.dataHora` (`data_status`) mudou. Se não mudou, os filhos não são buscados; a linha da proposição ainda é atualizada se o hash mudou (ex.: ementa corrigida), senão só `sincronizado_em` (ver 13.4).
- **Tipos acompanhados no MVP:** `PL`, `PLP`, `PEC`, `MPV` e `PDL`, numa constante `TIPOS_ACOMPANHADOS` em `Config` (lida de variável de ambiente). Outros tipos (`REQ`, `INC`, etc.) só entram quando são citados por uma votação ou um item de pauta, pelo `referencias.py`.
- **Novo calendário (substitui o RF02 antigo):**
  - `horaria`: votações e eventos do dia anterior e de hoje; proposições dos tipos acompanhados com janela de 1 dia.
  - `diaria` (madrugada): proposições dos tipos acompanhados dos últimos 3 dias; eventos pendentes (pauta); votações pendentes (votos e orientações).
  - `semanal` (domingo de madrugada): varredura de 30 dias das proposições; membros de órgãos, Mesa, lideranças e blocos.
  - `mensal`: frentes.
- **Meta de tempo:** `horaria` em menos de 20 minutos e `diaria` em menos de 3 horas. O Claude Code mede com dados reais e, se passar, avisa o grupo antes de mudar mais coisas.
- **Uma coleta por vez:** criar uma trava em arquivo (`instance/coletor.lock`, com o PID e a hora de início). Se uma rotina encontrar a trava, ela não roda, e grava um aviso em `log_sistema`. Trava com mais de 6 horas é considerada abandonada e pode ser removida.
- O grupo deve atualizar o RF02 no documento do MVP com este calendário.

### 12.2 Carga de validação
Não rodar um ano inteiro agora. Rodar uma **amostra** que cubra os casos diferentes:
- proposições dos 5 tipos acompanhados, em janelas curtas de 2005, 2015 e 2025 (antigas e novas);
- votações e eventos de 2 ou 3 dias com sessão no Plenário;
- membros de órgãos, Mesa, lideranças (`/legislaturas/57/lideres`), blocos, frentes e `/deputados?siglaSexo=M` e `F` (decisão 11.4).

Rodar com `nohup` (ou `tmux`) para não morrer se a sessão fechar, e terminar com `flask coletar relatorio`. O resultado é a lista de colunas que falharam e quantas vezes, que abre a Fase 2b. A carga maior (os últimos 3 meses, para o portal ter conteúdo) roda depois, já com as economias de 12.1. Um ano inteiro fica para quando o portal estiver no ar.

### 12.3 `/blocos/{id}/partidos` com id errado
A API devolve o id do bloco no lugar do id do partido. **Exceção aceita:** quando isso acontece, o coletor procura o partido pela sigla **entre os partidos da mesma legislatura do bloco**; se achar exatamente um, liga; se achar zero ou mais de um, não liga e grava um aviso em `log_sistema`. O `relatorio` mostra quantos blocos tiveram esse problema.

### 12.4 `pauta_item` com linhas repetidas
**Aceito no MVP:** uma linha por item de pauta, com a primeira votação válida em `votacao_id`, e aviso no log. A PK não muda. Para mostrar todas as votações de um item, a página usa as votações do mesmo evento (`votacao.evento_id`) que afetam a proposição do item (`votacao_proposicao`), sem precisar de `pauta_item.votacao_id`.

### 12.5 Histórico de membros de órgãos
**MVP guarda só a composição atual** em `deputado_orgao`, como em `bloco_partido`. Quem saiu é removido pela regra de vínculos que sumiram. `data_fim` fica como a API mandar. Guardar o histórico fica como evolução (entra na lista da seção 8).

### 12.6 Problemas técnicos registrados
- `/deputados` e `/frentes/{id}/membros` com 504: não bloqueiam o fechamento da fase. Os deputados vêm por `/deputados/{id}`. Os JSON escritos à mão nos testes devem ser trocados por respostas reais assim que a API responder; até lá ficam marcados no nome do arquivo (`*_manual.json`).
- `pytest --cov=desperta.coletor` falha dentro do SQLAlchemy, mas o comando oficial (`--cov=desperta`) funciona. Não investigar agora; anotar como problema conhecido no README.

### 12.7 O que falta para fechar a Fase 2
1. Implementar 12.1 (não buscar de novo, tipos acompanhados, novo calendário, trava) com testes.
2. Testes das rotinas `base`, `diaria`, `semanal` e `mensal` e de pelo menos um comando `flask coletar` de verdade (com respostas gravadas).
3. Rodar a amostra de 12.2 com `nohup` e entregar o `relatorio`.
4. Medir o tempo da `horaria` e da `diaria` com dados reais.
5. Commit, push e pull request para a `main` (12.8).

### 12.8 GitHub
A `main` do GitHub é criada a partir do commit `e7f6d2c` (fim da Fase 1.5). A branch `fase-2-coletor` sobe junto, e o pull request é aberto como **rascunho** já agora, para o grupo acompanhar. Ele vira pronto para revisão quando os itens de 12.7 terminarem. Se o `gh` não estiver instalado, o pull request é aberto pelo site do GitHub.

---

## 13. Decisões tomadas depois da parte 2 da Fase 2 (30/10/2026)

Respostas aos 7 pontos do relatório da parte 2. Todas aceitas como o Claude Code fez, com um acréscimo na trava (13.6).

### 13.1 Tabelas de apoio na `semanal`
Aceito. Legislaturas, partidos, deputados, órgãos e temas são atualizados na rotina `semanal`.

### 13.2 `horaria` só com o dia de hoje
Aceito. O que mudar no fim da noite entra na `diaria` da madrugada, que cobre 3 dias.

### 13.3 `horaria` sem pendentes de proposições e com no máximo 20 eventos para recoletar
Aceito, para caber na meta de 20 minutos. Os pendentes ficam para a `diaria`.

### 13.4 Conteúdo que muda com `data_status` igual
Aceito. O hash continua decidindo se a linha é atualizada; `data_status` só decide se os filhos (autores, temas, tramitações) são buscados de novo. O texto da 12.1 foi ajustado.

### 13.5 Filho com falha deixa a proposição pendente
Aceito, com o limite de 200 pendentes por janela. O `relatorio` deve mostrar quantas proposições estão pendentes por falha repetida, para o grupo ver o tamanho do problema. A correção de verdade vem com os ajustes de `nullable` da Fase 2b.

### 13.6 Trava: conferir se o processo ainda existe
**Acréscimo:** ao encontrar `instance/coletor.lock`, o coletor confere se o PID gravado ainda está rodando (`os.kill(pid, 0)`: `ProcessLookupError` = processo morto). Se o processo não existe, a trava é abandonada: remover, gravar um aviso em `log_sistema` e seguir com a coleta. Se o processo existe, não rodar. O limite de 6 horas continua como segunda proteção, para o caso de o número do PID ter sido reaproveitado por outro programa. Com testes para os três casos: PID vivo, PID morto e trava com mais de 6 horas.

### 13.7 RF02 no documento do MVP
Continua com o grupo: atualizar o RF02 com o calendário de 12.1 e 13.1 a 13.3.

### 13.8 Primeira `diaria`
A primeira execução pode passar de 3 horas (cerca de 7.200 chamadas). Isso é aceito uma vez: rodar a primeira `diaria` com `nohup`, logo depois da amostra. A meta de 3 horas vale a partir da segunda execução. Se a segunda também passar, avisar o grupo.

### 13.9 Cuidado com commits
Rodar `invoke test` e conferir o resultado **antes** de fazer o commit, em comandos separados. Não fazer commit com teste falhando.

