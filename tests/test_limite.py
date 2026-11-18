"""RNF10 (decisao 25.4): limite de requisicoes por endereco nas rotas da API."""

import pytest

import fabricas
from desperta.auth import services as auth_services
from desperta.ext import limite

SENHA = "senha-de-teste"


@pytest.fixture
def cliente(app, db):
    app.config.update(LIMITE_GERAL=5, LIMITE_BUSCA=2, LIMITE_JANELA_S=60)
    return app.test_client()


@pytest.fixture
def relogio(monkeypatch):
    """O tempo do limite anda so quando o teste manda."""
    agora = [1000.0]
    monkeypatch.setattr(limite.time, "monotonic", lambda: agora[0])
    return agora


def _status(cliente, caminho="/api/health", **opcoes):
    return cliente.get(caminho, **opcoes).status_code


def test_acima_do_limite_responde_429_com_a_espera(cliente, relogio):
    assert [_status(cliente) for _ in range(5)] == [200] * 5
    resposta = cliente.get("/api/health")
    assert resposta.status_code == 429
    assert resposta.get_json() == {"erro": "Muitas requisições. Tente de novo em 61 segundos."}
    assert resposta.headers["Retry-After"] == "61"


def test_a_janela_anda_e_libera_de_novo(cliente, relogio):
    assert [_status(cliente) for _ in range(6)] == [200] * 5 + [429]
    relogio[0] += 59
    assert _status(cliente) == 429
    relogio[0] += 1
    assert _status(cliente) == 200
    # Pedido recusado nao conta: a espera nao cresce para quem insiste
    assert len(cliente.application.extensions["limite"].recentes[("geral", "127.0.0.1")]) == 1


def test_cada_endereco_tem_a_sua_conta(cliente, relogio):
    assert [_status(cliente) for _ in range(6)][-1] == 429
    assert _status(cliente, environ_overrides={"REMOTE_ADDR": "10.0.0.2"}) == 200


def test_busca_tem_limite_proprio_e_menor(cliente, relogio):
    busca = "/api/noticias/busca?q=merenda"
    assert [_status(cliente, busca) for _ in range(3)] == [200, 200, 429]
    # A busca bloqueada nao tira o resto do portal do ar para esse endereco
    assert _status(cliente, "/api/proposicoes/temas") == 200


def test_preflight_do_cors_nao_conta(cliente, relogio):
    for _ in range(10):
        assert cliente.options("/api/health").status_code == 200
    assert _status(cliente) == 200


def test_limite_zero_desliga(app, cliente, relogio):
    app.config["LIMITE_GERAL"] = 0
    assert {_status(cliente) for _ in range(30)} == {200}


def test_quem_esta_logado_na_equipe_nao_entra_no_limite(db, cliente, relogio):
    auth_services.limpar_tentativas()
    db.session.add(fabricas.administrador(email="editora@desperta.org"))
    db.session.commit()
    entrou = cliente.post("/api/auth/login", json={"email": "editora@desperta.org", "senha": SENHA})
    assert entrou.status_code == 200, entrou.get_json()
    assert {_status(cliente, "/api/noticias/admin") for _ in range(20)} == {200}
    # Depois de sair, volta a contar como visitante
    assert cliente.post("/api/auth/logout").status_code == 204
    assert [_status(cliente) for _ in range(5)][-1] == 429


def test_contagens_antigas_saem_da_memoria(app, cliente, relogio, monkeypatch):
    monkeypatch.setattr(limite, "LIMPAR_A_CADA", 3)
    contador = app.extensions["limite"]
    for numero in range(2):
        _status(cliente, environ_overrides={"REMOTE_ADDR": f"10.0.0.{numero}"})
    assert len(contador.recentes) == 2
    relogio[0] += 61
    _status(cliente)
    assert set(contador.recentes) == {("geral", "127.0.0.1")}
