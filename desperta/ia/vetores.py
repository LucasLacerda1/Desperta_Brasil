from flask import current_app
from sqlalchemy import LargeBinary, column, literal, table, text

from desperta.ext.db import db

# ----------------------------------------------------------
# Indices vetoriais (tabelas virtuais do sqlite-vec), um por modelo de embeddings
# Nao sao modelos SQLAlchemy e nao contam como tabelas do modelo; reconstruiveis a partir de trecho_rag.
# Decisao 11.1: o SQL proprio do sqlite-vec fica so aqui
# Decisao 25.10: vec_trecho guarda a RoBERTaLexPT e vec_trecho_e5, o e5. Os dois tem 768 dimensoes, mas
# os vetores de um modelo nao se comparam com os do outro: cada busca usa o indice do seu modelo.
# ----------------------------------------------------------
TABELA = "vec_trecho"
TABELA_E5 = "vec_trecho_e5"
TABELAS = (TABELA, TABELA_E5)


def tabela(nome_modelo):
    return TABELA_E5 if nome_modelo == current_app.config["E5_MODEL"] else TABELA


def _criar(nome_tabela):
    return (
        f"CREATE VIRTUAL TABLE IF NOT EXISTS {nome_tabela} USING vec0("
        "trecho_id INTEGER PRIMARY KEY, embedding float[768] distance_metric=cosine)"
    )


def _indice(nome_tabela):
    return table(nome_tabela, column("trecho_id"), column("embedding"), column("distance"), column("k"))


def _conexao():
    """A conexao da sessao, com a extensao carregada: cada conexao do pool carrega uma vez."""
    conexao = db.session.connection()
    if not conexao.info.get("sqlite_vec"):
        import sqlite_vec

        sqlite = conexao.connection.driver_connection
        sqlite.enable_load_extension(True)
        sqlite_vec.load(sqlite)
        sqlite.enable_load_extension(False)
        conexao.info["sqlite_vec"] = True
    return conexao


def _existe(nome_tabela):
    return db.session.execute(
        text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :nome"), {"nome": nome_tabela}
    ).first()


def criar_indice(nome_modelo):
    _conexao().execute(text(_criar(tabela(nome_modelo))))


def gravar(nome_modelo, trecho_id, embedding):
    conexao = _conexao()
    nome_tabela = tabela(nome_modelo)
    # O vec0 nao tem upsert
    conexao.execute(text(f"DELETE FROM {nome_tabela} WHERE trecho_id = :id"), {"id": trecho_id})
    conexao.execute(
        text(f"INSERT INTO {nome_tabela} (trecho_id, embedding) VALUES (:id, :embedding)"),
        {"id": trecho_id, "embedding": embedding},
    )


def remover(trecho_id):
    """O trecho so esta no indice do seu modelo; apagar dos dois e mais simples e nao custa nada."""
    for nome_tabela in TABELAS:
        if _existe(nome_tabela):
            _conexao().execute(text(f"DELETE FROM {nome_tabela} WHERE trecho_id = :id"), {"id": trecho_id})


def reconstruir(nome_modelo):
    """Refaz o indice do modelo a partir de trecho_rag. Devolve o total de trechos."""
    conexao = _conexao()
    nome_tabela = tabela(nome_modelo)
    conexao.execute(text(f"DROP TABLE IF EXISTS {nome_tabela}"))
    conexao.execute(text(_criar(nome_tabela)))
    total = 0
    ultimo = 0
    while True:
        linhas = conexao.execute(
            text(
                "SELECT id, embedding FROM trecho_rag WHERE modelo_embedding = :modelo AND id > :ultimo "
                "ORDER BY id LIMIT 1000"
            ),
            {"modelo": nome_modelo, "ultimo": ultimo},
        ).all()
        if not linhas:
            return total
        conexao.execute(
            text(f"INSERT INTO {nome_tabela} (trecho_id, embedding) VALUES (:id, :embedding)"),
            [{"id": id_trecho, "embedding": embedding} for id_trecho, embedding in linhas],
        )
        total += len(linhas)
        ultimo = linhas[-1][0]


def remover_indice():
    """Para o drop-db: so carrega a extensao se algum indice existir (dropar exige o modulo vec0)."""
    for nome_tabela in TABELAS:
        if _existe(nome_tabela):
            _conexao().execute(text(f"DROP TABLE {nome_tabela}"))


def buscar(nome_modelo, embedding, k, candidatos=None):
    """Devolve (trecho_id, distancia), do mais parecido ao menos; candidatos e um select de ids."""
    indice = _indice(tabela(nome_modelo))
    consulta = db.select(indice.c.trecho_id, indice.c.distance).where(
        indice.c.embedding.op("MATCH")(literal(embedding, LargeBinary)),
        indice.c.k == k,
    )
    if candidatos is not None:
        consulta = consulta.where(indice.c.trecho_id.in_(candidatos))
    return [tuple(linha) for linha in _conexao().execute(consulta.order_by(indice.c.distance)).all()]
