import pytest

from api_falsa import URL_BASE, ApiFalsa, carregar, envelope

from desperta import create_app
from desperta.coletor.cliente import ClienteCamara
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


@pytest.fixture
def esperas():
    return []


@pytest.fixture
def api():
    falsa = ApiFalsa()

    # Qualquer deputado, orgao ou proposicao pedido pelo id, como no detalhe da API
    def deputado(id_texto):
        corpo = carregar("deputado")
        corpo["dados"]["id"] = int(id_texto)
        corpo["dados"]["ultimoStatus"]["id"] = int(id_texto)
        return corpo

    def orgao(id_texto):
        return envelope(
            {
                "id": int(id_texto),
                "sigla": f"O{id_texto}",
                "nome": "Orgao",
                "apelido": "Orgao",
                "codTipoOrgao": 2,
                "tipoOrgao": "Comissao",
            }
        )

    def proposicao(id_texto):
        corpo = carregar("proposicao")
        corpo["dados"]["id"] = int(id_texto)
        return corpo

    def partido(id_texto):
        corpo = carregar("partido")
        corpo["dados"]["id"] = int(id_texto)
        return corpo

    def evento(id_texto):
        corpo = carregar("evento")
        corpo["dados"]["id"] = int(id_texto)
        return corpo

    falsa.responder("deputados/*", deputado)
    falsa.responder("orgaos/*", orgao)
    falsa.responder("proposicoes/*", proposicao)
    falsa.responder("partidos/*", partido)
    falsa.responder("eventos/*", evento)
    return falsa


@pytest.fixture
def cliente(api, esperas):
    return ClienteCamara(URL_BASE, sessao=api, dormir=esperas.append)


@pytest.fixture
def base(db, api, cliente):
    """Legislatura 57 e os 3 temas gravados, como a coleta faz antes das demais."""
    from desperta.coletor import legislaturas, temas

    api.responder("legislaturas", carregar("legislaturas"))
    api.responder("referencias/proposicoes/codTema", carregar("temas"))
    legislaturas.coletar(cliente)
    temas.coletar(cliente)
    return db
