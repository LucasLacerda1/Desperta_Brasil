# Desperta Brasil — guia do projeto para o Claude Code

> Coloque este arquivo na **raiz do repositório** com o nome `CLAUDE.md`. O Claude Code lê esse arquivo sozinho no início de cada sessão.
> Última atualização: 09/11/2026 (Fases 1, 1.5, 2 e 2b concluídas; Fase 3 em andamento; decisões nas seções 10 a 23; ajuste físico do banco em `docs/AJUSTE_BANCO_SISTEMA.md`; treino da Roberta escritora em `docs/TREINAR_ROBERTA_ESCRITORA.md`; leitura encadeada da PEC em `docs/LEITURA_ENCADEADA.md`).

## 0. Como trabalhar neste projeto (leia primeiro)

- **Idioma:** responda, comente o código e escreva mensagens de commit em **português do Brasil**.
- **Padrão obrigatório:** o código segue a estrutura do projeto **TaskFlow**, usado como exemplo pelo professor da disciplina (Programação Web Avançada, UVV). A seção 3 descreve esse padrão. Não invente outra organização, não troque o Flask-SQLAlchemy por outro ORM e não use outro estilo de modelo.
- **Ordem do trabalho:** o projeto é construído por fases (seção 7). **As Fases 1 (banco), 1.5 (ajuste físico do banco, `docs/AJUSTE_BANCO_SISTEMA.md`), 2 (coletor) e 2b (campos opcionais, com 2 migrações, 22.2) estão concluídas, e o banco tem a bateria de persistência (22.4). O ajuste da `horaria` (PR nº 2) espera as medições da terça, 10/11. A fase atual é a 3 (IA e RAG, branch `fase-3-rag`): antes da Roberta escritora (3b), vem a análise da PEC com a Roberta original (22.6). Siga a ordem de 23.8.** Princípio do portal: transparência total (22.5). Não comece as rotas da API ou o front-end antes da fase anterior estar pronta e testada, a não ser que o grupo peça. Antes de mudar código, leia as seções 10 a 23 (decisões tomadas depois de cada relatório).
- **Git:** a `main` no GitHub é a versão estável. Cada fase é feita numa branch própria (`fase-2-coletor`, `fase-3-ia`…), com commits pequenos ao fim de cada passo e mensagem em português; ao terminar a fase, abrir um pull request para a `main`. Quem faz o merge é o Lucas, depois de revisar (Caio e Rhuan revisam quando puderem). Não fazer push direto na `main`. Nunca versione `.venv/`, `instance/`, `.env` nem arquivos `*.db`, `*.db-wal`, `*.db-shm`.
- **O modelo do banco já foi decidido pelo grupo** (32 tabelas, seção 5). Não acrescente, remova nem renomeie tabelas ou colunas por conta própria. A única exceção são as colunas técnicas, índices e configurações listados em `docs/AJUSTE_BANCO_SISTEMA.md` (camada física: controle de sincronização, índices, FTS5, migrações), que não mudam o modelo lógico. Se achar um problema no modelo, aponte e pergunte antes de mudar.
- **Ao terminar cada passo:** rode os testes (`invoke test`) e mostre o resultado.
- **Coautoria (22.8):** todo commit de trabalho e todo merge leva `Co-authored-by` do Caio e do Rhuan.
- **Tudo open source (seção 18):** só use bibliotecas, modelos e ferramentas de código aberto, e adapte no próprio código o máximo possível. Nada de API paga ou serviço fechado (OpenAI, Google, AWS etc.) no funcionamento do portal.

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
| RF02 | Coleta agendada (revisto em 05/11/2026, ver 12.1, 13.1 a 13.3, 14.2 e 15.3), em quatro rotinas. **De hora em hora:** votações e eventos de ontem e de hoje e proposições do dia dos tipos acompanhados (PL, PLP, PEC, MPV e PDL); pula proposições conferidas há menos de 6 horas, para sozinha aos 20 minutos e busca votações e eventos primeiro. **Diária, de madrugada:** proposições dos últimos 3 dias e tudo o que ficou pendente (pautas, votos e proposições incompletas). **Semanal, no domingo de madrugada:** varredura de 30 dias das proposições, tabelas de apoio (legislaturas, partidos, deputados, órgãos e temas), membros de órgãos, Mesa, lideranças e blocos. **Mensal:** frentes. Só uma coleta roda por vez; outros tipos de proposição entram só quando citados por votação ou pauta; os limites de 20 minutos e 6 horas são configuráveis. |
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
| IA (RAG) | **RoBERTaLexPT** (`eduagarcia/RoBERTaLexPT-base`) para embeddings e busca. Escrita: `GeradorFrases` (frases prontas) e, se passar na avaliação, a **Roberta escritora**, um modelo separado treinado a partir da RoBERTaLexPT (seção 17) |
| Busca vetorial | **sqlite-vec** no próprio SQLite; PyTorch + Hugging Face Transformers |
| Voz | **Whisper** (`faster-whisper`, modelo `small`, idioma `pt`) **só na busca por voz**; o áudio não é guardado. **Piper** (voz pt-BR) para ler as notícias; o áudio é gerado na publicação e salvo em arquivo pelo slug. (Web Speech API descartada, 18.2) |
| Fonte de dados | API de Dados Abertos da Câmara v2: `https://dadosabertos.camara.leg.br/api/v2` (REST, gratuita, sem chave, JSON, **sem CORS**: só o back-end chama) |

Decisões que **não** devem ser mudadas sem o grupo:
- **Sem Redis no MVP.** (Fica como evolução, para fila de gerações ou cache.)
- O Whisper **não lê texto**: só transcreve a busca por voz. A leitura é do Piper.
- Voz não cria tabela nova.
- A versão original da RoBERTaLexPT-base, usada como modelo de **embeddings**, **não gera texto**: só faz busca. A escrita é de um **modelo separado**, a versão adaptada da Fase 3b: a Roberta escritora (encoder-decoder montado e treinado a partir dela, seção 17), que fica em `instance/modelos/roberta-escritora/`.
- A API Flask não carrega nenhum dos dois modelos; eles rodam no módulo de IA, em segundo plano, depois de cada coleta.

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

- Carregar com `AutoTokenizer` e `AutoModel` (`eduagarcia/RoBERTaLexPT-base`), `model.eval()` e `torch.no_grad()`, uma vez no início do módulo de IA; dispositivo pelo `IA_DISPOSITIVO` (seção 20: RTX 4050 quando houver, CPU se não houver).
- Limite de 512 tokens; trechos de até 400 tokens com 50 de sobreposição; textos curtos ficam num trecho só.
- Embedding: mean pooling com a máscara de atenção + normalização L2 (768 dimensões, float32).
- Índice: tabela virtual do sqlite-vec ligada a `trecho_rag.id`, por exemplo `CREATE VIRTUAL TABLE vec_trecho USING vec0(trecho_id INTEGER PRIMARY KEY, embedding float[768] distance_metric=cosine)`. Criada pelo módulo de IA (não pelo `create_all`) e reconstruível a partir de `trecho_rag`.
- Busca: 8 trechos mais parecidos, com filtro por tipo e data quando preciso; gravar em `geracao_trecho` com `posicao` e `similaridade`.
- Só registros novos ou com `hash_texto` diferente recebem embedding depois de cada coleta.
- O que vira trecho: proposição (sigla, número/ano, ementa, ementa detalhada, keywords); tramitação (data, órgão, situação, despacho); votação (descrição, órgão, data, resultado e a situação dos votos: nominal, secreta, simbólica ou pendente, 22.5); evento e item de pauta (descrição, tópico, texto do parecer).
- Começar com o modelo original e medir a busca; fine-tuning com sentence-transformers só se precisar.
- **Quem escreve (atualizado, seção 17):** `ia/gerador.py` tem a interface, o `GeradorFalso` (testes), o `GeradorFrases` (plano B, padrão do MVP) e, depois da Fase 3b, o `GeradorRoberta`.

### 6.2 Voz (Fase 5)

- `POST /api/voz/transcrever`: recebe o áudio gravado pelo navegador (MediaRecorder), transcreve com faster-whisper (`small`, `language="pt"`) e devolve o texto. **Não guardar o áudio.**
- Leitura: ao publicar (ou alterar) uma notícia, gerar o áudio com o Piper (voz pt-BR) em `AUDIO_DIR/<slug>.wav`; o botão "Ouvir" toca esse arquivo (sem Web Speech API, 18.2).

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

### Fase 2 — Coletor (CONCLUÍDA em 01/11/2026: 409 testes, amostra sem falha de coluna; PR nº 1)
Pacote `desperta/coletor/` (cliente HTTP com backoff, um módulo por endpoint, upsert pelo id), comandos `flask coletar ...` e tarefas invoke. Registra `coleta` e `log_sistema`. Testes com respostas da API gravadas em arquivos JSON (sem chamar a API real nos testes).

Além da seção 6, a Fase 2 precisa:
- **Backoff de verdade (RNF02):** a API já devolveu HTTP 504 em `/legislaturas/57/lideres` e em `/deputados?siglaSexo=M`. Repetir em 429 e 5xx com espera exponencial (ex.: 2, 4, 8, 16 s, até 5 tentativas) e timeout por chamada.
- **Um registro ruim não derruba a coleta (decisão 10.2):** gravar cada registro com `db.session.begin_nested()`; se der `IntegrityError` (ex.: campo `NOT NULL` vazio), desfazer só ele, registrar em `log_sistema` (nível `erro`, `entidade` e `entidade_id` preenchidos, nome da coluna na descrição) e marcar a `coleta` como `parcial`.
- **Primeira carga de validação:** rodar uma carga real maior (pelo menos um ano de proposições de vários tipos, inclusive antigas, votações e eventos) e entregar ao grupo a lista de colunas que falharam e quantas vezes. **Não afrouxar `nullable` por conta própria.**
- **Orientações:** seguir a decisão 10.1.
- **Pedidos do relatório da Fase 1.5:** seguir a decisão 11.4 (contadores HTTP, endpoints com 504, `nullable` testado numa cópia do banco).
- **Decisões depois do relatório da Fase 2:** seguir a seção 12. O que falta para fechar a fase está em 12.7.

### Fase 2b — Ajustes de `nullable` (CONCLUÍDA em 04/11/2026 com 2 migrações, ver 22.2; a 14.1 fechou só a parte dos textos vazios)
O Flask-Migrate já foi iniciado na Fase 1.5. Quando o grupo decidir os ajustes de `nullable` da carga de validação, aplicá-los como uma nova migração (`flask db migrate` + revisão + `flask db upgrade`). Toda mudança no esquema é migração, não `create_all()`.

### Fase 3 — IA e RAG
Trechos, embeddings, índice sqlite-vec, busca híbrida (16.1), geração de rascunhos com o `GeradorFrases` (17.2), registro em `geracao_ia`, `geracao_trecho` e `noticia_fonte`, transparência dos dados (22.5) e análise da PEC com a Roberta original (22.6).

### Fase 3b — Roberta escritora
Treinar a RoBERTaLexPT como encoder-decoder para escrever título e resumo (seção 17 e `docs/TREINAR_ROBERTA_ESCRITORA.md`). Só entra no portal se passar na avaliação.

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

- ~~Qual modelo de linguagem generativo vai escrever as notícias.~~ Decidido na seção 17: a própria RoBERTaLexPT será treinada para escrever; o `GeradorFrases` é o plano B.
- Voz exata do Piper em pt-BR (o valor em `Config` é só um padrão). Conferir a licença da voz escolhida (18.2).
- Licença do próprio Desperta Brasil (18.3).
- Onde o projeto será publicado (servidor, HTTPS). Plano inicial na 21.4.
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
Continua com o grupo: atualizar o RF02 com o calendário de 12.1 e 13.1 a 13.3. **Atualizado em 05/11/2026:** o texto do RF02 na seção 1.2 foi reescrito com o calendário; o grupo copia o mesmo texto para o documento do MVP.

### 13.8 Primeira `diaria`
A primeira execução pode passar de 3 horas (cerca de 7.200 chamadas). Isso é aceito uma vez: rodar a primeira `diaria` com `nohup`, logo depois da amostra. A meta de 3 horas vale a partir da segunda execução. Se a segunda também passar, avisar o grupo.

### 13.9 Cuidado com commits
Rodar `invoke test` e conferir o resultado **antes** de fazer o commit, em comandos separados. Não fazer commit com teste falhando.

---

## 14. Decisões tomadas depois do relatório final da Fase 2 (01/11/2026)

### 14.1 Fase 2b: textos vazios em colunas obrigatórias
A amostra não teve nenhuma falha de `NOT NULL`. Apareceram só textos vazios (`''`) que a própria API manda: `tramitacao.despacho` (7 linhas), `orgao.sigla` (2) e `orgao.apelido` (1).
- **Decisão: nada muda no banco.** As três colunas continuam `NOT NULL` e guardam `''` como a API manda (regra da seção 9 do ajuste físico: em coluna obrigatória, texto vazio fica `''`). A Fase 2b fecha **sem migração**. **Atualizado em 22.2:** a carga de 3 meses mostrou campos que a API manda nulos, e a Fase 2b ganhou 2 migrações.
- Na API do portal e no front-end (Fases 4 e 5), texto vazio é tratado como "sem valor": não mostrar despacho vazio, e mostrar `orgao.nome` quando `sigla` estiver vazia.
- O `flask coletar relatorio` passa a contar também textos vazios em colunas obrigatórias de texto, para isso aparecer sem consulta à parte.

### 14.2 `horaria` em dia cheio (35 min, meta de 20)
O teste do dia cheio foi um caso extremo (dois dias inteiros de uma vez, 2.674 chamadas só de proposições), mas mostra o risco: no fim de um dia movimentado, cada `horaria` voltaria a conferir todas as proposições do dia. Ajustes, numa branch pequena (`fase-2-horaria`) depois do merge do PR nº 1:
- **Não reconferir o que já foi conferido há pouco:** na `horaria`, pular proposições com `sincronizado_em` de menos de 6 horas. A `diaria` da madrugada confere todas de novo.
- **Orçamento de tempo:** a `horaria` para sozinha ao chegar a 20 minutos, fecha a coleta como `parcial` e deixa o resto para a próxima hora (ou para a `diaria`). A ordem é votações e eventos primeiro, proposições por último, porque votações são o que o portal mais destaca.
- Testes para os dois casos.
- **Medir num dia útil com sessão no Plenário** (terça ou quarta à tarde; 02/11 é feriado de Finados). Rodar `time flask coletar horaria` três vezes no mesmo dia (início da tarde, fim da tarde e noite) e registrar tempo e requisições.

### 14.3 Pull request nº 1
Marcar como pronto para revisão e incluir o Rhuan como revisor. O merge na `main` acontece depois da revisão de pelo menos um dos dois. **Atualizado em 01/11/2026:** como Caio e Rhuan estão ocupados, o Lucas revisa e faz o merge sozinho; os dois ficam como revisores para acompanhar depois. O ajuste de 14.2 e a medição vêm num pull request separado, para não segurar a Fase 2.

### 14.4 Carga dos últimos 3 meses
Depois do merge, rodar a carga dos últimos 3 meses (12.2), à noite, com `setsid nohup` e o PC sem suspensão. É ela que dá conteúdo ao portal e matéria-prima para a IA da Fase 3. Frentes que faltaram entram na próxima `mensal`.

### 14.5 Antes da Fase 3
**Resolvida na seção 17.** O grupo precisava escolher o modelo de linguagem que vai escrever as notícias (seção 9). Sem isso, a Fase 3 só consegue fazer a parte da RoBERTaLexPT (trechos, embeddings, sqlite-vec e busca), com o gerador falso previsto em 6.1.

---

## 15. Decisões depois do ajuste da `horaria` (01/11/2026)

PR nº 1 com merge na `main`. O ajuste da 14.2 está no PR nº 2 (`fase-2-horaria`), que fica como **rascunho** até a medição em dia útil.

### 15.1 Proposições pendentes não são puladas
Aceito. Proposição sem filhos (por exemplo, citada por uma votação nova) é conferida mesmo com `sincronizado_em` recente.

### 15.2 Votações antes de eventos
Aceito, para os itens de pauta já acharem a votação gravada.

### 15.3 Limites em `Config`
Mudar no PR nº 2: os 20 minutos e as 6 horas saem das constantes de `rotinas.py` e vão para `Config`, lidos de variável de ambiente (`HORARIA_ORCAMENTO_MIN=20`, `HORARIA_RECONFERIR_HORAS=6`), como `TIPOS_ACOMPANHADOS`. Assim dá para ajustar depois da medição sem mexer no código.

### 15.4 Atraso de até 6 horas
Aceito. Uma mudança de situação logo depois da conferência aparece em até 6 horas ou na `diaria`. Votações, que são o principal do portal, não têm esse atraso.

### 15.5 Ordem dos próximos passos
1. Carga dos últimos 3 meses (14.4) numa noite com o PC ligado, a partir da `main`.
2. Medição da `horaria` na terça, 03/11, se houver sessão no Plenário (início da tarde, fim da tarde e noite). Se passar de 20 minutos, avisar o grupo.
3. Depois da medição: tirar o PR nº 2 de rascunho, Lucas revisa e faz o merge.
4. Enquanto isso, a Fase 3 pode começar a partir da `main`, numa branch `fase-3-rag`, só com a parte da RoBERTaLexPT (trechos, embeddings, sqlite-vec e busca) e o gerador falso de 6.1, até o grupo escolher o modelo de linguagem (14.5).

---

## 16. Decisões depois do início da Fase 3 (01/11/2026)

PR nº 3 (`fase-3-rag`) fica como **rascunho** até a busca melhorar e as tramitações serem indexadas.

### 16.1 Busca híbrida (vetorial + palavras)
A RoBERTaLexPT sozinha acertou 38% e dá similaridade entre 0,95 e 0,99 para quase tudo. Isso é esperado num modelo treinado para preencher lacunas e não para comparar frases: os vetores ficam todos parecidos. Decisão:
- **Índice FTS5 de `trecho_rag`** (`trecho_fts`), igual ao `noticia_fts`: `content='trecho_rag'`, `tokenize='unicode61 remove_diacritics 2'`, gatilhos de inserção, remoção e atualização de `texto`. Tabela virtual, fora das 32, criada pelo módulo de IA (SQL isolado, como em 11.1) e ignorada pelo Flask-Migrate.
- **Junção dos resultados por RRF** (Reciprocal Rank Fusion): buscar os 50 melhores em cada índice e somar `1 / (60 + posição)` de cada lista; os 8 maiores vão para o gerador. Os filtros por tipo e data valem para as duas buscas. Em `geracao_trecho.similaridade` gravar a nota do RRF.
- **Experimento barato junto:** centralizar os embeddings (subtrair o vetor médio de todos os trechos e normalizar de novo). Costuma separar melhor os vetores desse tipo de modelo. Guardar o vetor médio num arquivo em `instance/` e aplicar também na consulta. Medir com e sem.
- Fine-tuning com sentence-transformers só se a busca híbrida não bastar.

### 16.2 Como medir a busca
A medida "contém a palavra" favorece a busca por palavras. Trocar por um **conjunto de 20 consultas** escritas pelo grupo, cada uma com as proposições que deveriam aparecer (conferidas à mão), em `tests/dados/consultas_busca.json`. Métrica: quantas das esperadas aparecem nos 8 primeiros. Comparar vetorial, palavras, híbrida e híbrida com centralização. O Claude Code pode propor um rascunho das 20 consultas a partir do banco para o grupo corrigir.

### 16.3 Tramitações
- **Texto com identificação:** começar o trecho com a proposição (ex.: `PL 1234/2024 — `) e os primeiros 200 caracteres da ementa, depois data, órgão, situação e despacho. Sem isso, um despacho sozinho não diz de que projeto se trata.
- **Só as recentes:** indexar tramitações dos últimos 90 dias (variável `RAG_TRAMITACAO_DIAS=90` em `Config`). O portal escreve sobre o que está acontecendo; as antigas continuam no banco para a página da proposição.
- Indexar à noite, depois da carga de 3 meses, e medir o tempo.

### 16.4 `flask db check` falhando na `main` e na `fase-2-horaria`
Levar para o PR nº 2 só a mudança do `migrations/env.py` que ignora `vec_trecho` (e já preparar para ignorar `trecho_fts`), para o `flask db check` passar antes do merge da Fase 3. Testes e coletas não são afetados.

### 16.5 Decisões do Claude Code
Aceitas: PyTorch só para CPU (trocado pelo PyTorch com CUDA na 20.2); tipo e nome do evento juntos no trecho; sem geração real até o grupo escolher o modelo; testes de IA pulados sem as dependências. A do texto das tramitações foi trocada pela 16.3.

### 16.6 Ordem
1. 16.4 no PR nº 2.
2. Na `fase-3-rag`: 16.7, 16.1 e o rascunho das consultas de 16.2.
3. Noite com o PC ligado: carga de 3 meses (15.5), depois indexação das tramitações recentes (16.3).
4. Grupo corrige as 20 consultas; Claude Code mede as quatro opções e relata.
5. Terça, 03/11: medição da `horaria` e merge do PR nº 2.

### 16.7 Onde o modelo fica
O modelo baixado não pode depender do cache escondido do usuário. Configurar em `Config` e no `.env.example`: `HF_HOME=instance/modelos` (o modelo fica dentro do projeto, fora do git) e, depois do primeiro download, `HF_HUB_OFFLINE=1` (roda sem internet e sem conferir versão). Um comando `flask ia baixar-modelo` (e `invoke baixar-modelo`) faz o download uma vez e confere se o modelo carrega. Registrar no README o tamanho (cerca de 500 MB). **Atualizado na seção 21:** a RoBERTaLexPT-base passa a vir de `ROBERTA_DIR`, que vai apontar para um pendrive; os outros modelos ficam em `MODELOS_DIR` (`instance/modelos`).

---

## 17. Gerador das notícias: a RoBERTaLexPT aprende a escrever (01/11/2026)

### 17.1 Decisão do grupo
Em vez de um modelo de linguagem pronto (14.5), a **própria RoBERTaLexPT** será treinada para escrever, montada como **encoder-decoder** (warm-start, RoBERTa2RoBERTa). O plano completo está em `docs/TREINAR_ROBERTA_ESCRITORA.md`. Resumo:
- Ela escreve só **`titulo` e `resumo`**. O `corpo` é montado pelo código com os dados do banco.
- O treino é feito **na GPU principal do PC do Lucas, a NVIDIA RTX 4050** (seção 20), com um script em `scripts/treino/`. Google Colab ou Kaggle só se a 4050 não der conta.
- Os exemplos de treino (pares "dados da Câmara → título e lide") vêm da Agência Câmara de Notícias, **só se o `robots.txt` e os termos permitirem**. Esses textos servem só para treino e nunca vão para o portal nem para o banco.
- O dataset fica em arquivo (`instance/dataset/pares.jsonl`), sem tabelas novas.
- Só entra no portal se passar na avaliação: no máximo 2 erros de fato em 50 casos e clareza média de pelo menos 4,0.

### 17.2 Plano B primeiro
Antes de qualquer treino, implementar o **`GeradorFrases`** em `desperta/ia/gerador.py` (frases prontas, sem IA, nunca inventa número, nome ou data). `GERADOR` em `Config`: `falso`, `frases` ou `roberta`, com padrão `frases`. O MVP sai com ele se a Roberta escritora não ficar boa a tempo. Não apagar depois.

### 17.3 Ordem
**Ajustada em 19.4: a etapa 1 pode começar já.** A Fase 3b vem **depois** dos passos de 16.6 (busca híbrida, carga de 3 meses, tramitações, medição da `horaria` e merge do PR nº 2). Dentro dela: etapa 1 (`GeradorFrases`, na `fase-3-rag`) → etapa 2 (dataset, numa branch `fase-3b-roberta-escritora`; relatório com volume e licença) → **o grupo confirma** → etapa 3 (treino) → etapa 4 (avaliação) → etapa 5 (integração, só se passar).

---

## 18. Princípio do projeto: tudo open source e adaptado no código (01/11/2026)

### 18.1 A regra
O Desperta Brasil é uma plataforma **open source** e **personalizada no próprio código**. Por isso:
- Toda biblioteca, modelo e ferramenta usada pelo portal precisa ter **licença aberta** (MIT, BSD, Apache 2.0, GPL/AGPL, CC-BY etc.). Antes de acrescentar uma dependência nova, conferir a licença e anotar no relatório.
- **Nenhum serviço fechado ou pago no funcionamento do portal:** nada de OpenAI, Gemini, Google Cloud, AWS, APIs de tradução ou de voz de terceiros. A única fonte externa é a API de Dados Abertos da Câmara.
- **Adaptar em vez de usar pronto:** quando der, o comportamento é do projeto (exemplos: a Roberta treinada para escrever, seção 17; o `GeradorFrases`; a busca híbrida, 16.1; as rotinas do coletor). Usar a biblioteca como base e escrever a parte do Desperta no nosso código, sem copiar código de outro projeto sem respeitar a licença.
- Modelos baixados ficam em `instance/modelos/` e rodam **sem internet** (16.7).

### 18.2 O que isso muda no que já foi decidido
- **Web Speech API (antes citada nas seções 2 e 6):** sai como alternativa. No Chrome ela manda o áudio para servidores do Google. A voz fica só com Whisper (busca) e Piper (leitura).
- **Vozes do Piper:** o Piper é aberto, mas cada voz tem a sua licença. Escolher uma voz pt-BR com licença que permita uso e redistribuição e registrar no README.
- **Google Colab ou Kaggle (17):** agora são só reserva (seção 20); a máquina do treino é a RTX 4050. Se forem usados, são só a máquina emprestada. O código do treino (notebook em `scripts/treino/`) é do projeto e precisa rodar também em qualquer PC com GPU, sem depender de função exclusiva do Colab ou do Kaggle.
- **Dados da Agência Câmara (17):** usados só no treino, nunca redistribuídos no repositório.

### 18.3 Licença do projeto (o grupo decide)
**Situação:** o grupo vai discutir com o professor. Até lá, não criar `LICENSE` e não cobrar essa decisão nos relatórios.

O repositório precisa de um arquivo `LICENSE`. Sugestões:
- **AGPL-3.0:** quem usar o código num site também precisa abrir as mudanças. É a que mais protege a ideia de plataforma aberta.
- **MIT:** mais simples e livre, mas permite que alguém feche uma cópia.
O Claude Code não escolhe: só cria o `LICENSE` depois da decisão do grupo. Ao criar, colocar no README a lista de dependências e modelos com as licenças de cada um e os créditos da RoBERTaLexPT (Garcia et al., PROPOR 2024).

---

## 19. Decisões depois da Fase 3, parte 2 (01/11/2026)

### 19.1 Centralização: descartada
Piorou nos dois modos (híbrida 63% → 54%, vetorial 41% → 29%). Não adotar. `RAG_CENTRALIZAR` fica com padrão desligado e o código pode ficar, mas não entra em nenhum fluxo. Se o grupo confirmar com as consultas corrigidas, remover o comando, a variável e `instance/vetor_medio.npy` num commit separado.

### 19.2 Busca: ainda sem decisão final
A medida preliminar favorece a busca por palavras, porque as esperadas vieram de palavras nas ementas. A decisão entre híbrida e só palavras espera as consultas corrigidas (16.2). Enquanto isso:
- O padrão continua `hibrida`.
- Acrescentar à medição uma quinta opção: **RRF com peso**, com a lista de palavras pesando 1,0 e a vetorial 0,5 (`RAG_PESO_VETOR=0.5` em `Config`). A ideia é manter os acertos que só a híbrida achou ("vacinar idosos em casa") sem deixar o vetor derrubar os da busca por palavras ("piso salarial dos professores").
- Na medida final, mostrar também quantos resultados fora do assunto aparecem nos 8 primeiros de cada opção (exemplo: vaquejada em "educação"), marcados à mão pelo grupo no mesmo arquivo.
- Fine-tuning da RoBERTaLexPT para busca só se nenhuma opção passar de 70% com as consultas corrigidas.

### 19.3 Correções no guia
Feitas nesta versão: seção 0 (fase atual), seção 2 (modelo de embeddings x Roberta escritora, sem "a definir") e 16.7 movida para depois da 16.6.

### 19.4 Ordem a partir de agora
1. **Pode começar já:** Fase 3b, etapa 1 (`GeradorFrases`, na `fase-3-rag`). Ela não depende da carga nem da busca final. Isso adianta a 17.3, que pedia para esperar a 16.6 inteira.
2. Junto: a opção de RRF com peso (19.2) e `.vscode/` no `.gitignore`.
3. Noite com o PC ligado: carga de 3 meses e tramitações recentes (16.6, passo 3).
4. Grupo corrige as 20 consultas; Claude Code mede as cinco opções e relata (19.2).
5. Terça, 03/11: medição da `horaria` e merge do PR nº 2.
6. Só depois: etapa 2 da Fase 3b (dataset).

### 19.5 Decisões do Claude Code
Aceitas: `.env` local com `HF_HUB_OFFLINE=1`; apagar a cópia antiga do modelo em `~/.cache/huggingface`; `trecho_rag` guardando o embedding original; correção das esperadas do rascunho. Não apagar nada fora do projeto de novo sem avisar antes no relatório.

---

## 20. GPU: usar a NVIDIA RTX 4050 (01/11/2026)

### 20.1 Qual placa
O PC do Lucas tem uma GPU integrada e a **GPU principal, NVIDIA GeForce RTX 4050**. Todo trabalho de IA que usar GPU usa **a RTX 4050**, nunca a integrada.
- Conferir com `nvidia-smi` e `torch.cuda.get_device_name(0)` (precisa conter `4050`).
- `CUDA_VISIBLE_DEVICES=0` e `torch.device("cuda:0")`.
- Se o CUDA não aparecer, **parar e avisar o Lucas**. Não instalar, trocar nem configurar driver da NVIDIA ou `prime-select` por conta própria.

### 20.2 O que muda
- **PyTorch:** trocar o PyTorch só para CPU (16.5) pelo PyTorch com CUDA, no `.venv`. Registrar no README o comando e o tamanho novo do `.venv`. O `pyproject.toml` continua pedindo só `torch`.
- **Configuração:** `IA_DISPOSITIVO` em `Config` e no `.env.example`: `auto` (padrão: usa `cuda:0` se existir, senão processador), `cuda` (exige a GPU e para com erro se não houver) ou `cpu`. Registrar no log qual dispositivo foi usado em cada execução.
- **Embeddings e indexação (`flask ia indexar`):** usam a RTX 4050 pelo `IA_DISPOSITIVO`. Isso deve acelerar muito a indexação das tramitações (16.3). Medir o tempo com GPU e anotar no relatório. A 6.1 dizia "CPU": passa a ser "GPU quando houver; o código continua funcionando na CPU".
- **Treino da Roberta escritora (17):** na RTX 4050, com os ajustes de memória de `docs/TREINAR_ROBERTA_ESCRITORA.md`, seção 3.
- **API Flask:** continua sem carregar PyTorch nem a GPU (6.1).
- **Testes:** continuam rodando sem GPU. Testes que precisam de CUDA são pulados quando ela não existe.

### 20.3 Open source (seção 18)
O driver e o CUDA da NVIDIA são da fabricante da placa, não do projeto. São aceitos como driver do computador. O código do Desperta continua todo aberto e precisa rodar também sem placa da NVIDIA (`IA_DISPOSITIVO=cpu`).

### 20.4 Ordem
Fazer 20.2 (PyTorch com CUDA e `IA_DISPOSITIVO`) junto com os itens 1 e 2 da 19.4, antes da noite da carga, para a indexação das tramitações já usar a GPU.

---

## 21. RoBERTaLexPT no pendrive e servidor no futuro (01/11/2026)

### 21.1 O que o Lucas quer
Por enquanto tudo roda no PC do Lucas. **Só a RoBERTaLexPT-base fica num pendrive, completa: a Roberta e os seus parâmetros** (pesos, configuração e tokenizador). Todo o resto fica na pasta do projeto, no disco do PC: banco, dataset, checkpoints, a Roberta escritora treinada (Fase 3b) e os modelos de voz (Fase 5). Depois, o projeto vai para um **servidor**, para funcionar sem depender do PC. O pendrive ainda não chegou: até lá, a RoBERTaLexPT continua em `instance/modelos`.

### 21.2 Como configurar
- **`MODELOS_DIR`** em `Config` e no `.env.example`: pasta dos modelos do projeto. Padrão e valor fixo no PC do Lucas: `instance/modelos`. Ali ficam `roberta-escritora/` (Fase 3b), `whisper-small/` e `piper/` (Fase 5).
- **`ROBERTA_DIR`** em `Config` e no `.env.example`: pasta só da RoBERTaLexPT-base. Padrão: `<MODELOS_DIR>/roberta-lexpt-base`. Com o pendrive: por exemplo `ROBERTA_DIR=/media/<usuario>/DESPERTA/roberta-lexpt-base` (o Ubuntu monta o pendrive em `/media/<usuario>/<nome do pendrive>`; o pendrive deve se chamar `DESPERTA` para o caminho não mudar).
- **O que vai para o pendrive, na pasta `ROBERTA_DIR`:** o modelo inteiro, sem faltar nada para carregar sem internet: os pesos (`model.safetensors`, os 125 milhões de parâmetros, cerca de 500 MB), a configuração (`config.json`) e o tokenizador (`tokenizer.json`, `tokenizer_config.json`, `vocab.json`, `merges.txt`, `special_tokens_map.json`, os que existirem). O `flask ia baixar-modelo` confere se todos estão lá e mostra a lista.
- **Roberta escritora (Fase 3b):** fica no PC, em `ROBERTA_ESCRITORA_DIR` (padrão `<MODELOS_DIR>/roberta-escritora`). Por ser uma variável própria, dá para levá-la ao pendrive depois mudando só uma linha do `.env`, se o Lucas quiser.
- **Pastas simples:** cada modelo salvo com `save_pretrained` (modelo e tokenizer) e carregado pelo caminho com `local_files_only=True`. Não usar o formato de cache do Hugging Face (pastas `blobs` e `snapshots` com links), porque pendrives em exFAT ou FAT32 não aceitam links. `HF_HOME` só serve, temporariamente, durante o download.
- **`flask ia baixar-modelo`** baixa a RoBERTaLexPT, salva em `ROBERTA_DIR`, confere se carrega e mostra o caminho e o tamanho. Com `HF_HUB_OFFLINE=1`, nada é baixado sozinho em outro lugar.
- **`flask ia mover-roberta --para <pasta>`** (novo): copia a RoBERTaLexPT para a nova pasta (o pendrive), confere se carrega de lá e mostra a linha para atualizar `ROBERTA_DIR` no `.env`. **Não apaga a cópia antiga**: apagar é decisão do Lucas, depois de conferir.
- O treino da Fase 3b lê a RoBERTaLexPT de `ROBERTA_DIR` (pendrive) e salva o resultado em `ROBERTA_ESCRITORA_DIR` (PC).

### 21.3 Se o pendrive não estiver conectado
- **Coletor, API, testes e a Roberta escritora continuam funcionando**, porque não dependem da RoBERTaLexPT-base. (A Roberta escritora é um modelo separado, salvo no PC, com os seus próprios pesos.)
- **Comandos que usam a RoBERTaLexPT-base** (`flask ia indexar`, `buscar`, `reconstruir`, `medir-busca` e o treino) conferem `ROBERTA_DIR` no começo. Se ela não existir ou estiver vazia, **param com uma mensagem clara** ("RoBERTaLexPT não encontrada em <caminho>. O pendrive está conectado?"), gravam um aviso em `log_sistema` e saem com erro, sem travar a coleta.
- **Indexação depois de cada coleta:** sem o pendrive, a coleta termina normalmente e a indexação fica pendente. Ela roda na próxima vez, porque é incremental pelo `hash_texto`.
- **Geração de notícias:** a busca do RAG precisa da RoBERTaLexPT para transformar a consulta em vetor. Sem o pendrive, usar só a busca por palavras (`trecho_fts`) naquela execução e gravar um aviso no log. Nunca deixar de gravar a `geracao_ia`.
- **Nunca baixar a RoBERTaLexPT de novo para o disco do PC** só porque o pendrive não estava conectado.
- Testes para os três casos: pasta existe, pasta não existe e pasta vazia.

### 21.4 Servidor (futuro, não fazer agora)
O plano para quando o portal sair do PC do Lucas (depois da Fase 6, ou antes se o grupo pedir):
- Servidor Linux com software aberto: Gunicorn rodando o Flask, Nginx na frente com HTTPS (Let's Encrypt), o front-end Vue gerado com `npm run build` e servido pelo Nginx.
- Coletor e indexação agendados no próprio servidor, com `systemd` ou `cron`, usando a trava de 13.6.
- O banco continua em SQLite num servidor só. PostgreSQL só se houver mais de um servidor (11.1).
- Os modelos ficam no disco do servidor: `MODELOS_DIR` e `ROBERTA_DIR` apontam para lá. Sem placa de vídeo, `IA_DISPOSITIVO=cpu` (seção 20).
- **O treino continua na RTX 4050 do PC do Lucas.** Para o servidor vão só a Roberta escritora pronta e a RoBERTaLexPT-base.
- Hoje, a única preparação é manter **todo caminho e todo endereço configurável por variável de ambiente** (`DATABASE_URL`, `MODELOS_DIR`, `ROBERTA_DIR`, `ROBERTA_ESCRITORA_DIR`, `AUDIO_DIR`, `CORS_ORIGINS`, `IA_DISPOSITIVO`), sem nenhum caminho do PC do Lucas escrito no código.

### 21.5 Ordem
Fazer 21.2 e 21.3 junto com a 20.2, com `ROBERTA_DIR` no padrão (`instance/modelos/roberta-lexpt-base`). Quando o pendrive chegar, o Lucas avisa e o Claude Code roda `flask ia mover-roberta` e atualiza o `.env`.

---

## 22. Decisões e trabalho de 03 a 05/11/2026

### 22.1 Carga de 3 meses (03 e 04/11)
Rodou de 03/08 a 03/11/2026, em 1 h 26 min, a partir do código da `fase-3-rag` (o coletor era igual ao da `main`). As proposições foram de 3.489 para 9.937, e as votações de 24 para 1.068. Em seguida, a indexação na RTX 4050 levou 2 minutos. Backup antes da carga: `instance/desperta-antes-carga-3meses.db`. Log: `instance/carga-3meses.log`.

### 22.2 Fase 2b: campos que a API manda nulos
A carga mostrou campos obrigatórios que a Câmara manda nulos. Decisão do Lucas: "a Câmara vai continuar fazendo isso, então tem que ser null".
- **Migração `535ba879b66f` (PR nº 4):** `voto.tipo_voto` opcional. Na votação secreta (02/09/2026, PDL 995/2026, indicação ao TCU), a API registra só a presença. Confirmado com a API e com notícias.
- **Migração `f8a2f7162512` (PR nº 5):** `proposicao.regime`, `proposicao.data_status`, `proposicao.url_inteiro_teor` e `tramitacao.regime` opcionais. As 17 proposições que tinham falhado foram recuperadas.
- **Coletor:** votação com voto que falhou fica pendente e volta na `diaria`, como a proposição na 13.5.
- Cada migração foi testada numa cópia do banco antes, com backup (`instance/desperta-antes-fase-2b.db` e `instance/desperta-antes-campos-opcionais.db`).

### 22.3 Deputados repetidos na listagem (PR nº 6)
A listagem `/deputados?idLegislatura=` traz o mesmo deputado uma vez por partido em que ele esteve, e o coletor alternava o partido a cada coleta (cerca de 200 "atualizados" sem mudança real). Agora, quando as linhas diferem, vale o detalhe `/deputados/{id}`. Na API real, a segunda coleta seguida deu 0 atualizados.

### 22.4 Bateria de persistência (PR nº 6)
- `flask banco verificar` (só leitura): integridade, chaves estrangeiras, 32 tabelas, versão do esquema, WAL, votos contra o placar da Câmara, referências sem FK, índices de busca, embeddings, datas, hashes e coletas interrompidas.
- `flask banco testar-persistencia`: numa cópia feita pelo backup do SQLite, testa ida e volta, upsert sem duplicar, atualização no lugar, erro isolado, restrições e cascata. A cópia é apagada no fim.
- Os dois aceitam `--relatorio arquivo.md`. Também: `invoke verificar-banco` e `invoke testar-persistencia`.
- No banco real: 20 aprovados, 0 falhas e 0 avisos; persistência 8 de 8.
- **Amostra para mostrar:** `instance/desperta-amostra.db` (15 MB), criada pelas migrações com uma parte coerente dos dados, sem o índice vetorial.

### 22.5 Princípio: transparência total no portal
Decisão do Lucas (05/11): o portal deve ser o mais claro e transparente possível e informar tudo.
- **O banco guarda exatamente o que a API mandou** (por exemplo, o `"."` no `regime`). O código classifica e explica; não apagar a diferença no banco.
- `desperta/proposicoes/services.py`: `""`, `"."`, `"-"` e nulo são "não informado pela Câmara" (`informado()` e `ou_nao_informado()`).
- `desperta/votacoes/services.py`: `situacao_dos_votos()` classifica a votação em pendente, erro na coleta, secreta (com o placar escrito pela Câmara), simbólica, nominal ou inconsistente, com a explicação em texto.
- Os trechos de votação que a Roberta lê e o `GeradorFrases` usam essas explicações. O corpo do rascunho mostra situação, regime e apreciação, ou que não foram informados.
- Na Fase 4 e 5, o portal deve mostrar também: data da última coleta e aviso de dados desatualizados, como cada notícia foi feita (gerador, revisão e fontes) e avisos de erro aparente nos dados da Câmara.
- **Em aberto (grupo):** as proposições sem tema (109 dos tipos acompanhados) não geram notícia. Opções: um tema especial "Sem tema oficial", marcado como criado pelo portal, ou tema opcional na notícia.
- Coleta nº 6 (30/10): marcada como `erro`, com o motivo, e mantida no histórico.

### 22.6 Análise da PEC com a Roberta original
- **A Roberta original vem primeiro; o treino fica para depois**, e só se as rodadas mostrarem que é necessário, com a confirmação do grupo.
- **PEC:** a 319/2004 (id 265999), com o texto completo em `instance/analise_pec/PEC_319_2004.txt`, dividido em 12 trechos numerados (EMENTA, P1 a P4 e J1 a J7). A interpretação do grupo usa `instance/analise_pec/interpretacao_modelo.json`, uma por pessoa, preenchida antes de ver qualquer resultado.
- **Leitura com contexto:** cada parágrafo é lido junto com o seu contexto, metade dos 512 tokens para cada parte, com o contexto antes do texto (`<s> contexto </s></s> parágrafo </s>`). O vetor sai só dos tokens do parágrafo, para o contexto comum não deixar os parágrafos parecidos demais. Parágrafo maior que a metade é cortado com sobreposição.
- **Modelos de contexto:** o grupo escreve modelos com chaves do JSON da API, por exemplo `{titulo}`, `{tema}`, `{ementa}` (no lugar do resumo, porque só 11% das proposições acompanhadas têm `ementaDetalhada`), `{palavras_chave}` e `{paragrafo_anterior}`. Na PEC 319/2004, tudo isso soma cerca de 190 tokens e cabe no contexto. **Cuidado:** o tema no contexto entrega o teste D, e as palavras-chave entregam o teste E. Nesses testes, usar modelos sem essas chaves.
- **Rodadas:** cada configuração ou modelo é uma rodada, registrada em `instance/analise_pec/rodadas/`. Primeiro a base (Roberta original, sem contexto). O grupo define antes a meta de "preciso" e escolhe as PECs de conferência, que não são usadas nos ajustes.
- Código em `scripts/analise_pec/`, ainda não escrito: espera a interpretação e os modelos.
- Estudo completo em `docs/ESTUDO_ROBERTA_X_GRUPO.md`.

### 22.7 Pendrive
- Kingston de 115 GB, em FAT32, com o nome `KINGSTON` (e não `DESPERTA`), montado em `/run/media/olam/KINGSTON`.
- No PC, `ROBERTA_DIR` aponta para `/run/media/olam/KINGSTON/Desperta_Brasil/instance/modelos/roberta-lexpt-base`. Sem o pendrive, os comandos de IA param com aviso, e dá para usar a cópia do PC só numa execução (`ROBERTA_DIR=instance/modelos/roberta-lexpt-base`).
- No pendrive: `Desperta_Brasil/` (cópia completa, com `.env` que vale para qualquer PC), `Desperta_Brasil_leve/` (com a amostra como banco e sem o modelo), `desperta-amostra.db`, `COMO_RODAR_O_BANCO.md` e `LEIA-ME.md`. As cópias são retratos e precisam ser atualizadas à mão.

### 22.8 Coautoria nos commits
O trabalho é feito no PC do Lucas, e o Caio e o Rhuan participam. Todo commit de trabalho e todo merge leva, no fim da mensagem, depois de uma linha em branco:
```text
Co-authored-by: Caio Henrique de Oliveira <caioheriqueolive@gmail.com>
Co-authored-by: Rhuan Santos Wolfgramm <srhuan35@gmail.com>
```
Commit que já foi para o GitHub não é reescrito. Os commits `7cd1e90` e `c052cab`, na `main`, ficaram com um e-mail errado do Caio. No merge pelo site, usar "Create a merge commit", para manter a coautoria.

### 22.9 Cuidados operacionais
- `flask db upgrade` e `flask db check` precisam rodar **a partir da pasta da branch certa**, porque a pasta `migrations/` é a da pasta atual.
- Para copiar o banco, usar o backup do SQLite. Os arquivos `-wal` e `-shm` fazem parte do banco enquanto ele está em uso.
- Antes de qualquer mudança no banco real: backup em `instance/desperta-antes-*.db` e teste numa cópia.
- Parar coletas com `kill -TERM <PID>`, nunca `pkill -f` com o texto do comando.

### 22.10 Ordem a partir de agora (substituída pela 23.8)
1. Terça, 10/11: as duas medições da `horaria` que faltam (a primeira, em 04/11, bateu os 20 minutos) e o merge do PR nº 2.
2. Grupo: interpretação da PEC, modelos de contexto, meta de "preciso" e PECs de conferência. Depois, o Claude Code escreve `scripts/analise_pec/` e roda as rodadas.
3. Grupo: correção das 20 consultas da busca; depois, medir as 5 opções e decidir a busca (19.2).
4. Claude Code: gerar rascunhos sozinho a partir de `itens_novos`, otimizar a `horaria` e agendar as rotinas, com o ok do Lucas.
5. Merge da `fase-3-rag` na `main` e começo da Fase 4.
6. Treino da Roberta (análise e escritora), só depois das rodadas e com a confirmação do grupo.

---

## 23. Decisões e trabalho de 05 a 08/11/2026

### 23.1 Visualizador do banco (só desenvolvimento)
- `invoke ver-banco` abre o banco no navegador com o **Datasette** (Apache 2.0), em modo só leitura, em `http://127.0.0.1:8001`; `--banco instance/desperta-amostra.db` abre a amostra. Dependência opcional `[ver]` (`datasette` e `datasette-template-sql`, ambos Apache 2.0). Não faz parte do portal.
- Configuração gerada por `scripts/ver_banco/montar_metadata.py`: menu com busca rápida, tabelas por assunto, nomes no lugar dos ids, filtros e 15 consultas prontas.
- **Visão geral** em `/visao-geral` (`scripts/ver_banco/templates/pages/visao-geral.html`): números principais, período, proposições, votações, o que a Câmara não informou, coletas, erros do log, IA e notícias.
- Na página de resultado de uma consulta livre, o menu fica escondido, para o resultado aparecer no topo.

### 23.2 Rascunhos automáticos (`flask ia gerar-novos`)
- Item 4 da 22.10. Escolha do Lucas (07/11): viram rascunho **todas** as votações (Plenário e comissões) que afetam um tipo acompanhado, **todas** as mudanças de situação depois do dia da apresentação e **todas** as proposições novas dos tipos acompanhados. Votações primeiro.
- Janela: `GERACAO_JANELA_DIAS` (padrão 3). Pula fato que já tem geração (inclusive notícia rejeitada e geração com erro, que só volta com `--refazer-erros`), proposição sem tema e fato pendente na coleta. Opções `--simular`, `--limite` e `--dias`; resumo em `log_sistema` (`acao = gerar_novos`). Código em `desperta/ia/automatico.py`; `invoke gerar-novos`.
- A geração passou a ler a proposição antes de criar o gerador, para todo erro gravar a entrada completa.
- **Achado:** a Câmara demora para dar tema às proposições novas (27 de 40 da semana de 31/10 sem tema). Como proposição sem tema não gera notícia, a maioria das novas passa da janela antes de ganhar tema. Isso deixa mais urgente a decisão em aberto da 22.5.

### 23.3 Leitura encadeada da PEC (`docs/LEITURA_ENCADEADA.md`)
Plano do grupo (07/11): a Roberta lê a PEC em pedaços e leva adiante, em texto, o que ela mesma escolheu (frase e palavras), sem treino. Decisões, registradas no documento:
1. **Metade e metade:** 254 tokens de contexto e 254 de pedaço.
2. **Frases:** o texto vira uma lista fixa e numerada de frases; o grupo cita sempre pelo código. Na PEC 319/2004 são 22 (F1 a F22).
3. **Textos menores primeiro;** PECs maiores só quando a Roberta estiver precisa nas menores.
4. **Corte no meio do texto é aceito:** o resto vai para a leitura seguinte.
5. **Três camadas, nesta ordem:** a **planta padrão** (a estrutura que toda PEC tem), entendida por uma **leitura prévia** (cada bloco vira um vetor e cada frase é ligada ao bloco mais parecido; só o nome do bloco escolhido pela Roberta entra no contexto, nunca o do script); o **contexto inicial** (`{sigla}, de {autor}. Ementa: {ementa}`); e as **interpretações** da Roberta. A planta **não** é o contexto inicial.
6. **Tudo o que é modelo é geral, para toda PEC** (planta, contexto inicial e formulário de interpretação); o que é de uma PEC só fica em arquivos com o nome dela.
7. **Planta base do grupo:** parte normativa com 6 blocos (epígrafe, autoria, ementa, preâmbulo, artigo e nova redação) e justificação por função (objetivo, problemas, citação, solução e fecho), sem número de parágrafo; 274 tokens.
8. **Teste D com duas notas:** `temas` (até 3) e `temas_tambem_aceitos`; nota exata e nota ampla.
9. **Interpretações da PEC 319/2004:** a do Lucas (resumo e palavras-chave adotados da do Claude, depois de ler e concordar, então não contam como leitura independente; 5 frases e temas são escolha dele) e a do Claude (documento do claude.ai, completado pelo Claude Code em 08/11). A do Claude é um leitor a mais; a base é a interpretação humana.

### 23.4 Arquivos da análise (`instance/analise_pec/`, fora do git)
- Gerais: `modelos_contexto.json` (planta padrão, contexto inicial, rodadas), `interpretacao_modelo.json` (formulário).
- Da PEC 319/2004: `PEC_319_2004.txt` (com códigos antigos EMENTA, P1 a P4, J1 a J7), `PEC_319_2004_pedacos.txt` (8 pedaços), `PEC_319_2004_frases.json` (F1 a F22, com `bloco_certo`), `PEC_319_2004_dados.txt`, `PEC_319_2004_interpretacao_e_planta.md` (documento do claude.ai), `interpretacao_PEC_319_2004.json` (para preencher), `interpretacao_PEC_319_2004_lucas.json` e `interpretacao_PEC_319_2004_claude.json`.
- Tokenizador conferido: `<mask>` é o 50264; " demarcação" e " indígenas" são um token cada.

### 23.5 Rodadas e o que é "Roberta perfeita"
- **"Perfeita" não é 100%:** é concordar com o grupo tanto quanto as pessoas do grupo concordam entre si, e continuar assim em PECs que ela nunca viu. Lucas e Claude, por exemplo, não coincidem em nenhuma das 5 frases.
- **Primeiras 5 rodadas na PEC 319** (cada uma pontuada contra todas as interpretações): (1) base, cada frase sozinha; (2) encadeada só com as interpretações; (3) + contexto inicial; (4) + planta; (5) controle com frases sorteadas no lugar das interpretações, com 5 sorteios. Opcional: de trás para frente.
- **Regras dos ajustes:** combinar a meta antes; limite de ajustes (por exemplo, 10 rodadas); depois, a melhor configuração roda uma vez só nas PECs de conferência, sem mexer em nada.
- **Falta para chegar lá:** interpretações do Caio e do Rhuan (teto e consenso); meta por teste (sugestão: A 3 de 5, B 70%, C entre as 3 primeiras de 30, D 2 de 3 na nota ampla, E 5 de 10, blocos 70% contra 36% do acaso); 2 ou 3 PECs de conferência curtas, com texto, frases e interpretações; decidir o teste C (comparar só ementas ou baixar o texto inteiro das outras PECs); treinos 1 e 2 do estudo só se as rodadas não chegarem na meta e com a confirmação do grupo; depois, PECs maiores e decidir para que a leitura da Roberta vai servir no portal.

### 23.6 GPU e kernel
O kernel 7.0.0-43 foi instalado sem o módulo da NVIDIA (`linux-modules-nvidia-595-open-7.0.0-43-generic` ainda não saiu). Até sair, para usar a RTX 4050: `sudo grub-reboot "Advanced options for Ubuntu>Ubuntu, with Linux 7.0.0-42-generic"` antes de reiniciar (vale um boot). Sem a placa, a IA roda no processador (`IA_DISPOSITIVO=auto`). Continua valendo a 20.1: o Claude Code não mexe no driver.

### 23.7 Coleta e primeiros rascunhos reais (08/11)
- Backups antes: `instance/desperta-antes-coleta-08-11.db` e `instance/desperta-antes-rascunhos-08-11.db`. Log: `instance/coleta-diaria-08-11.log`.
- `diaria` em 6 min (2.400 requisições, 0 erro HTTP). A `diaria` não traz votações nem eventos novos, que são da `horaria` (ontem e hoje): depois de dias sem coleta, rodar também `flask coletar votacoes` e `eventos` na janela que faltou (aqui, 05 a 08/11: 12 votações, 11 no Plenário, todas de 05/11).
- `flask ia indexar` em 17 s na RTX 4050: 1.720 trechos novos ou alterados e 269 removidos (tramitações com mais de 90 dias).
- `flask ia gerar-novos` (janela desde 05/11) em 1 min 34 s: **626 rascunhos** (9 votações, 606 mudanças de situação e 11 proposições novas), 0 erro, 8 puladas sem tema. Rodar de novo não gera nada (626 já feitos). Verificação do banco: 20 aprovados, 0 falhas.
- Proposições 10.512, tramitações 175.788, votações 1.218, trechos 30.410.

### 23.8 Ordem a partir de agora
1. ~~As 5 primeiras rodadas da PEC 319 (23.5), com relatório.~~ Feito, com 1.000 repetições e os 4 leitores (23.9).
2. Terça, 10/11: as duas medições da `horaria` que faltam e o merge do PR nº 2; depois, otimizar a `horaria` e agendar as rotinas.
3. Grupo: meta de "preciso", PECs de conferência, ok na planta e no contexto inicial, o que conta como frase importante (23.9), tema das proposições sem tema (22.5) e as 20 consultas da busca (19.2).
4. Revisão dos 626 rascunhos pela equipe (na Fase 4, pela área administrativa).
5. Merge da `fase-3-rag` na `main` e começo da Fase 4.
6. Treino da Roberta, só depois das rodadas e com a confirmação do grupo.

### 23.9 Rodadas da PEC 319 com 4 leitores (08 e 09/11)
- As 14 rodadas (7 formas de leitura, com e sem whitening) foram repetidas 1.000 vezes com dropout (`scripts/analise_pec/repeticoes.py`), primeiro com 2 leitores e depois com os 4 e o consenso (`--consenso lucas caio rhuan`). Resultado em `docs/LEITURA_ENCADEADA.md`, decisões 10 e 11, e no relatório (seções 4.5 e 4.6 da aba ABNT).
- **Uma rodada única engana:** o mesmo leitor vai de 0,35 a 0,90 de AUC de uma leitura para outra. Toda configuração nova é avaliada por repetições.
- **Contexto, memória, planta e RAG quase não mudam a leitura** (no máximo 0,07; a memória sorteada rende o mesmo que a verdadeira). **O whitening é o único ganho que se repete:** tema oficial de cerca de 20º para cerca de 9º.
- **O grupo está dividido:** Caio e Claude ficam com o texto normativo, Lucas e Rhuan com o fim da justificação; Lucas e Caio, o único par independente (o Rhuan partiu do arquivo do Lucas), têm 1 frase em comum. O consenso de 2 das 3 pessoas é a própria escolha do Rhuan, e contra ele a Roberta fica no acaso.
- **Decisão pendente do grupo:** combinar o que conta como frase importante (ou reunir mais leituras independentes) antes de fixar a meta de "preciso" ou de propor treino. Recomendação do Claude Code: deixar a análise da PEC como estudo por enquanto e seguir para a Fase 4; no portal, a RoBERTaLexPT entra pela busca e pela sugestão de tema.
