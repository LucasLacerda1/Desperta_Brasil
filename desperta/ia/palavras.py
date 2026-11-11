import re

from sqlalchemy import text

from desperta.ext.db import db

# ----------------------------------------------------------
# Busca por palavras nos trechos (tabela virtual FTS5, decisao 16.1)
# Nao e modelo SQLAlchemy e nao conta como tabela do modelo; reconstruivel a partir de trecho_rag.
# Decisao 11.1: o SQL proprio do FTS5 dos trechos fica so aqui
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
REMOVER_INDICE = (
    "DROP TRIGGER IF EXISTS trecho_fts_au",
    "DROP TRIGGER IF EXISTS trecho_fts_ad",
    "DROP TRIGGER IF EXISTS trecho_fts_ai",
    "DROP TABLE IF EXISTS trecho_fts",
)
_indice = db.table("trecho_fts", db.column("rowid"))


def criar_indice():
    """Trechos gravados antes de o indice existir entram aqui; os seguintes, pelos gatilhos."""
    existia = db.session.execute(
        text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'trecho_fts'")
    ).first()
    for comando in CRIAR_INDICE:
        db.session.execute(text(comando))
    if not existia:
        reconstruir()


def reconstruir():
    db.session.execute(text("INSERT INTO trecho_fts(trecho_fts) VALUES ('rebuild')"))


def remover_indice():
    for comando in REMOVER_INDICE:
        db.session.execute(text(comando))


def _para_match(consulta):
    """Qualquer palavra serve, e o bm25 favorece as raras; as aspas evitam quebrar a sintaxe do MATCH."""
    return " OR ".join(f'"{palavra}"' for palavra in re.findall(r"\w+", consulta or ""))


def buscar(consulta, k, candidatos=None):
    """Devolve os ids dos trechos, do mais relevante ao menos; candidatos e um select de ids."""
    match = _para_match(consulta)
    if not match:
        return []
    busca = db.select(_indice.c.rowid).where(text("trecho_fts MATCH :consulta").bindparams(consulta=match))
    if candidatos is not None:
        busca = busca.where(_indice.c.rowid.in_(candidatos))
    busca = busca.order_by(db.func.bm25(db.literal_column("trecho_fts"))).limit(k)
    return list(db.session.scalars(busca))
