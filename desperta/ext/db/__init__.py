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
