import pytest

from desperta import create_app
from desperta.config import TestConfig
from desperta.ext.db import db as _db


@pytest.fixture
def app():
    return create_app(TestConfig)


@pytest.fixture
def db(app):
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()
