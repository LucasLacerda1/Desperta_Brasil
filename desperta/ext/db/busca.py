from sqlalchemy import text

# ----------------------------------------------------------
# Busca de texto nas noticias (tabela virtual FTS5)
# Nao e modelo SQLAlchemy e nao conta como tabela do modelo
# ----------------------------------------------------------
CRIAR_BUSCA_TEXTO = (
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS noticia_fts USING fts5(
        titulo, resumo, corpo,
        content='noticia', content_rowid='id',
        tokenize='unicode61 remove_diacritics 2'
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS noticia_fts_ai AFTER INSERT ON noticia BEGIN
        INSERT INTO noticia_fts(rowid, titulo, resumo, corpo)
        VALUES (new.id, new.titulo, new.resumo, new.corpo);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS noticia_fts_ad AFTER DELETE ON noticia BEGIN
        INSERT INTO noticia_fts(noticia_fts, rowid, titulo, resumo, corpo)
        VALUES ('delete', old.id, old.titulo, old.resumo, old.corpo);
    END
    """,
    # So OF titulo, resumo, corpo: somar visualizacoes nao reindexa a noticia
    """
    CREATE TRIGGER IF NOT EXISTS noticia_fts_au AFTER UPDATE OF titulo, resumo, corpo ON noticia BEGIN
        INSERT INTO noticia_fts(noticia_fts, rowid, titulo, resumo, corpo)
        VALUES ('delete', old.id, old.titulo, old.resumo, old.corpo);
        INSERT INTO noticia_fts(rowid, titulo, resumo, corpo)
        VALUES (new.id, new.titulo, new.resumo, new.corpo);
    END
    """,
)

REMOVER_BUSCA_TEXTO = (
    "DROP TRIGGER IF EXISTS noticia_fts_au",
    "DROP TRIGGER IF EXISTS noticia_fts_ad",
    "DROP TRIGGER IF EXISTS noticia_fts_ai",
    "DROP TABLE IF EXISTS noticia_fts",
)


def criar_busca_texto(conexao):
    for comando in CRIAR_BUSCA_TEXTO:
        conexao.execute(text(comando))


def remover_busca_texto(conexao):
    for comando in REMOVER_BUSCA_TEXTO:
        conexao.execute(text(comando))
