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
    assert (
        "Access-Control-Allow-Origin"
        not in cliente.get("/api/health", headers={"Origin": "http://localhost:5173"}).headers
    )


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


# ======================================================
# ERROS FORA DAS REGRAS (404, 405 e 500 em JSON) E LOG
# ======================================================
def test_endereco_inexistente_na_api_responde_json(app):
    resposta = app.test_client().get("/api/nao-existe")
    assert resposta.status_code == 404
    assert resposta.get_json() == {"erro": "Endereco nao encontrado na API."}


def test_metodo_errado_responde_json(app):
    resposta = app.test_client().delete("/api/health")
    assert resposta.status_code == 405
    assert resposta.get_json() == {"erro": "Metodo nao permitido neste endereco."}


def test_erro_inesperado_responde_json_e_vai_para_o_log(caplog):
    app = create_app(TestConfig)

    @app.get("/api/teste-quebra")
    def quebra():
        raise RuntimeError("falha de proposito")

    with caplog.at_level("ERROR", logger=app.logger.name):
        resposta = app.test_client().get("/api/teste-quebra")
    assert resposta.status_code == 500
    corpo = resposta.get_json()
    assert corpo == {"erro": "Erro interno do servidor. O problema foi registrado no log."}
    # O detalhe fica so no log, nunca na resposta
    assert "falha de proposito" not in resposta.get_data(as_text=True)
    assert "GET /api/teste-quebra" in caplog.text
    assert "falha de proposito" in caplog.text


def test_fora_da_api_fica_a_resposta_padrao(app):
    resposta = app.test_client().get("/pagina-qualquer")
    assert resposta.status_code == 404
    assert resposta.get_json(silent=True) is None


def test_nivel_do_log_vem_da_configuracao():
    class LogDetalhado(TestConfig):
        LOG_NIVEL = "DEBUG"

    assert create_app(LogDetalhado).logger.level == 10
