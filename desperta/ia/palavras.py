from sqlalchemy import text

from desperta.ext.db import db
from desperta.ext.db.busca import raizes_da_consulta

# ----------------------------------------------------------
# Busca por palavras nos trechos (tabela virtual FTS5, decisao 16.1)
# Nao e modelo SQLAlchemy e nao conta como tabela do modelo; reconstruivel a partir de trecho_rag.
# Decisao 11.1: o SQL proprio do FTS5 dos trechos fica so aqui
# Decisao 25.3: trecho_fts guarda as palavras como estao; trecho_fts_raiz guarda as raizes
# ("professores" e "professora" viram "professor") e e o indice que a busca usa.
# ----------------------------------------------------------
CRIAR_INDICE = (
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS trecho_fts USING fts5(
        texto,
        content='trecho_rag', content_rowid='id',
        tokenize='unicode61 remove_diacritics 2'
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trecho_fts_ai AFTER INSERT ON trecho_rag BEGIN
        INSERT INTO trecho_fts(rowid, texto) VALUES (new.id, new.texto);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trecho_fts_ad AFTER DELETE ON trecho_rag BEGIN
        INSERT INTO trecho_fts(trecho_fts, rowid, texto) VALUES ('delete', old.id, old.texto);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trecho_fts_au AFTER UPDATE OF texto ON trecho_rag BEGIN
        INSERT INTO trecho_fts(trecho_fts, rowid, texto) VALUES ('delete', old.id, old.texto);
        INSERT INTO trecho_fts(rowid, texto) VALUES (new.id, new.texto);
    END
    """,
)
# Indice das raizes: tabela FTS5 comum, mantida pelo codigo (acompanhar_pela_raiz em ia/models.py)
CRIAR_INDICE_RAIZ = (
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS trecho_fts_raiz USING fts5(
        texto,
        tokenize='unicode61 remove_diacritics 2'
    )
    """,
)
REMOVER_INDICE = (
    "DROP TABLE IF EXISTS trecho_fts_raiz",
    "DROP TRIGGER IF EXISTS trecho_fts_au",
    "DROP TRIGGER IF EXISTS trecho_fts_ad",
    "DROP TRIGGER IF EXISTS trecho_fts_ai",
    "DROP TABLE IF EXISTS trecho_fts",
)
_indice = db.table("trecho_fts_raiz", db.column("rowid"))


def _existe(tabela):
    return db.session.execute(
        text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :nome").bindparams(nome=tabela)
    ).first()


def criar_indice():
    """
    Trechos gravados antes de os indices existirem entram aqui; os seguintes, pelos gatilhos
    (trecho_fts) e pelo ORM (trecho_fts_raiz). Se o indice das raizes nao tem uma linha por
    trecho (gravacao feita por uma versao do codigo que nao o mantinha), ele e refeito.
    """
    existia = _existe("trecho_fts")
    for comando in CRIAR_INDICE + CRIAR_INDICE_RAIZ:
        db.session.execute(text(comando))
    if not existia:
        _reconstruir_palavras()
    trechos = db.session.execute(text("SELECT COUNT(*) FROM trecho_rag")).scalar()
    if trechos != db.session.execute(text("SELECT COUNT(*) FROM trecho_fts_raiz_docsize")).scalar():
        _reconstruir_raizes()


def remover(trecho_id):
    """Para exclusao em lote, que nao passa pelo ORM (o indice trecho_fts tem gatilho proprio)."""
    if _existe("trecho_fts_raiz"):
        db.session.execute(text("DELETE FROM trecho_fts_raiz WHERE rowid = :id").bindparams(id=trecho_id))


def _reconstruir_palavras():
    db.session.execute(text("INSERT INTO trecho_fts(trecho_fts) VALUES ('rebuild')"))


def _reconstruir_raizes():
    db.session.execute(text("DELETE FROM trecho_fts_raiz"))
    db.session.execute(text("INSERT INTO trecho_fts_raiz(rowid, texto) SELECT id, raiz(texto) FROM trecho_rag"))


def reconstruir():
    _reconstruir_palavras()
    _reconstruir_raizes()


def remover_indice():
    for comando in REMOVER_INDICE:
        db.session.execute(text(comando))


def _para_match(consulta):
    """
    Qualquer palavra serve, e o bm25 favorece as raras; as aspas evitam quebrar a sintaxe do MATCH.
    Decisao 25.3: a comparacao e pelas raizes das palavras.
    """
    return " OR ".join(f'"{raiz}"' for raiz in raizes_da_consulta(consulta))


def buscar(consulta, k, candidatos=None):
    """Devolve os ids dos trechos, do mais relevante ao menos; candidatos e um select de ids."""
    match = _para_match(consulta)
    if not match:
        return []
    busca = db.select(_indice.c.rowid).where(text("trecho_fts_raiz MATCH :consulta").bindparams(consulta=match))
    if candidatos is not None:
        busca = busca.where(_indice.c.rowid.in_(candidatos))
    busca = busca.order_by(db.func.bm25(db.literal_column("trecho_fts_raiz"))).limit(k)
    return list(db.session.scalars(busca))
