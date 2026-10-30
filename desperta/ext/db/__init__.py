import sqlite3

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, event
from sqlalchemy.engine import Engine

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


def init_app(app):
    db.init_app(app)
    migrate.init_app(app, db)


# ----------------------------------------------------------
# SQLite so confere chave estrangeira com foreign_keys=ON; WAL e busy_timeout
# deixam o coletor gravar enquanto a API le, sem "database is locked"
# ----------------------------------------------------------
@event.listens_for(Engine, "connect")
def _configurar_sqlite(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
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
