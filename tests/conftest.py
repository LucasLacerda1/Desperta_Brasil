import pytest

from desperta import create_app
from desperta.config import TestConfig
from desperta.ext.db import db as _db
from desperta.ext.db.busca import criar_busca_texto, remover_busca_texto


@pytest.fixture
def app():
    return create_app(TestConfig)


@pytest.fixture
def db(app):
    with app.app_context():
        _db.create_all()
        with _db.engine.begin() as conexao:
            criar_busca_texto(conexao)
        yield _db
        _db.session.remove()
        with _db.engine.begin() as conexao:
            remover_busca_texto(conexao)
        _db.drop_all()
