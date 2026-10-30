import pytest

import fabricas
from desperta.ext.db import db as _db


def _modelos(app):
    return sorted((m.class_ for m in _db.Model.registry.mappers), key=lambda c: c.__name__)


def test_ha_linha_e_repr_em_todos_os_32_modelos(db, app):
    fabricas.popular(db)
    modelos = _modelos(app)
    assert len(modelos) == 32
    for modelo in modelos:
        registro = db.session.scalar(db.select(modelo))
        assert registro is not None, modelo.__name__
        assert "__repr__" in vars(modelo), modelo.__name__
        assert repr(registro).startswith(f"<{modelo.__name__} "), modelo.__name__


def test_repr_do_administrador_nao_mostra_a_senha(db):
    admin = fabricas.administrador()
    assert admin.senha_hash not in repr(admin)


@pytest.mark.parametrize(
    "atributo, esperado",
    [
        ("proposicao", "PL 1234/2024"),
        ("votacao", "2310837-8"),
        ("noticia", "camara-aprova-projeto"),
    ],
)
def test_repr_mostra_a_identificacao(db, atributo, esperado):
    dados = fabricas.popular(db)
    assert esperado in repr(getattr(dados, atributo))
