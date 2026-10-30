from sqlalchemy import inspect

from desperta.ext.db import db


def test_health(client):
    resposta = client.get("/api/health")
    assert resposta.status_code == 200
    assert resposta.json == {"status": "ok", "message": "Desperta Brasil API is running"}


def test_cors_em_rotas_da_api(client):
    resposta = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert "Access-Control-Allow-Origin" in resposta.headers


def test_blueprints_dos_9_dominios(app):
    assert set(app.blueprints) == {
        "auth",
        "proposicoes",
        "votacoes",
        "parlamentares",
        "orgaos",
        "noticias",
        "ia",
        "sistema",
        "visitantes",
    }


def test_comandos_init_db_e_drop_db(app):
    runner = app.test_cli_runner()

    resultado = runner.invoke(args=["init-db"])
    assert resultado.exit_code == 0
    assert "32 tabelas" in resultado.output
    with app.app_context():
        assert len(inspect(db.engine).get_table_names()) == 32

    resultado = runner.invoke(args=["drop-db"])
    assert resultado.exit_code == 0
    with app.app_context():
        assert inspect(db.engine).get_table_names() == []
