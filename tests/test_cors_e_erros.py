import pytest

from desperta import create_app
from desperta.config import TestConfig
from desperta.ext.erros import AcessoNegado, Conflito, DadosInvalidos, NaoEncontrado


# ======================================================
# CORS E COOKIE DE SESSAO (decisao 10.5)
# ======================================================
def test_origem_do_front_end_recebe_cors_com_credenciais(app):
    resposta = app.test_client().get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert resposta.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert resposta.headers["Access-Control-Allow-Credentials"] == "true"


def test_outra_origem_nao_recebe_cors(app):
    resposta = app.test_client().get("/api/health", headers={"Origin": "http://site-qualquer.com"})
    assert "Access-Control-Allow-Origin" not in resposta.headers


def test_origens_vem_da_configuracao():
    class ComOutraOrigem(TestConfig):
        CORS_ORIGINS = ["https://desperta.exemplo"]

    cliente = create_app(ComOutraOrigem).test_client()
    resposta = cliente.get("/api/health", headers={"Origin": "https://desperta.exemplo"})
    assert resposta.headers["Access-Control-Allow-Origin"] == "https://desperta.exemplo"
    assert "Access-Control-Allow-Origin" not in cliente.get(
        "/api/health", headers={"Origin": "http://localhost:5173"}
    ).headers


def test_cookie_de_sessao_protegido(app):
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    # So com HTTPS, em producao (SESSION_COOKIE_SECURE=1 no .env)
    assert isinstance(app.config["SESSION_COOKIE_SECURE"], bool)


# ======================================================
# ERROS DOS SERVICES VIRAM JSON (decisao 10.4)
# ======================================================
@pytest.mark.parametrize(
    "erro, codigo",
    [(DadosInvalidos, 400), (AcessoNegado, 403), (NaoEncontrado, 404), (Conflito, 409)],
)
def test_erro_do_service_vira_resposta_json(erro, codigo):
    app = create_app(TestConfig)

    @app.route("/api/teste-erro")
    def _falha():
        raise erro("mensagem clara")

    resposta = app.test_client().get("/api/teste-erro")
    assert resposta.status_code == codigo
    assert resposta.get_json() == {"erro": "mensagem clara"}
