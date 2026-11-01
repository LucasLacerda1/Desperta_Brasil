from sqlalchemy import LargeBinary, column, literal, table, text

from desperta.ext.db import db

# ----------------------------------------------------------
# Indice vetorial (tabela virtual do sqlite-vec)
# Nao e modelo SQLAlchemy e nao conta como tabela do modelo; reconstruivel a partir de trecho_rag.
# Decisao 11.1: o SQL proprio do sqlite-vec fica so aqui
# ----------------------------------------------------------
TABELA = "vec_trecho"
CRIAR_INDICE = (
    f"CREATE VIRTUAL TABLE IF NOT EXISTS {TABELA} USING vec0("
    "trecho_id INTEGER PRIMARY KEY, embedding float[768] distance_metric=cosine)"
)
_indice = table(TABELA, column("trecho_id"), column("embedding"), column("distance"), column("k"))


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


def criar_indice():
    _conexao().execute(text(CRIAR_INDICE))


def gravar(trecho_id, embedding):
    conexao = _conexao()
    # O vec0 nao tem upsert
    conexao.execute(text(f"DELETE FROM {TABELA} WHERE trecho_id = :id"), {"id": trecho_id})
    conexao.execute(
        text(f"INSERT INTO {TABELA} (trecho_id, embedding) VALUES (:id, :embedding)"),
        {"id": trecho_id, "embedding": embedding},
    )


def remover(trecho_id):
    _conexao().execute(text(f"DELETE FROM {TABELA} WHERE trecho_id = :id"), {"id": trecho_id})


def reconstruir(nome_modelo):
    """Refaz o indice a partir de trecho_rag; devolve quantos trechos entraram."""
    conexao = _conexao()
    conexao.execute(text(f"DROP TABLE IF EXISTS {TABELA}"))
    conexao.execute(text(CRIAR_INDICE))
    conexao.execute(
        text(
            f"INSERT INTO {TABELA} (trecho_id, embedding) "
            "SELECT id, embedding FROM trecho_rag WHERE modelo_embedding = :modelo"
        ),
        {"modelo": nome_modelo},
    )
    return conexao.execute(text(f"SELECT count(*) FROM {TABELA}")).scalar_one()


def remover_indice():
    """Para o drop-db: so carrega a extensao se o indice existir (dropar exige o modulo vec0)."""
    existe = db.session.execute(
        text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :nome"), {"nome": TABELA}
    ).first()
    if existe:
        _conexao().execute(text(f"DROP TABLE {TABELA}"))


def buscar(embedding, k, candidatos=None):
    """Devolve (trecho_id, distancia), do mais parecido ao menos; candidatos e um select de ids."""
    consulta = db.select(_indice.c.trecho_id, _indice.c.distance).where(
        _indice.c.embedding.op("MATCH")(literal(embedding, LargeBinary)),
        _indice.c.k == k,
    )
    if candidatos is not None:
        consulta = consulta.where(_indice.c.trecho_id.in_(candidatos))
    return [tuple(linha) for linha in _conexao().execute(consulta.order_by(_indice.c.distance)).all()]
