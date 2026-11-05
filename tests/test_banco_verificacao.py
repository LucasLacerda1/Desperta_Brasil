from datetime import date

import pytest
from sqlalchemy import text

import fabricas
from desperta import create_app
from desperta.config import TestConfig
from desperta.ext.db import db as _db
from desperta.ext.db.verificacao import FALHA, OK, _placares, _versao_mais_nova, verificar_banco
from desperta.proposicoes.models import Proposicao


def _base(db):
    db.session.add_all([fabricas.legislatura(), fabricas.orgao(), fabricas.tema(), fabricas.proposicao()])
    db.session.flush()
    db.session.add(fabricas.deputado())
    db.session.commit()


def _por_nome(resultados):
    return {resultado.nome: resultado for resultado in resultados}


# ======================================================
# VOTOS X PLACAR DA CAMARA
# ======================================================
def test_placar_que_bate_com_os_votos(db):
    _base(db)
    db.session.add(fabricas.votacao(descricao="Aprovado. Sim: 1; Não: 0; Total: 1."))
    db.session.flush()
    db.session.add(fabricas.voto())
    db.session.commit()
    resultado = _placares()
    assert (resultado.situacao, resultado.detalhe) == (OK, "1 de 1 votacoes batem")


def test_placar_que_nao_bate_e_apontado(db):
    _base(db)
    db.session.add(fabricas.votacao(descricao="Aprovado. Sim: 2; Não: 0; Total: 2."))
    db.session.flush()
    db.session.add(fabricas.voto())
    db.session.commit()
    resultado = _placares()
    assert resultado.situacao == FALHA
    assert "2310837-8" in resultado.detalhe


def test_votacao_secreta_confere_so_o_total(db):
    _base(db)
    db.session.add(fabricas.votacao(descricao="Aprovado. Sim: 1; Não: 0; Total: 1."))
    db.session.flush()
    db.session.add(fabricas.voto(tipo_voto=None))
    db.session.commit()
    assert _placares().situacao == OK


def test_voto_do_presidente_nao_entra_no_total(db):
    _base(db)
    db.session.add_all([fabricas.votacao(descricao="Sim: 1; Não: 0; Total: 1."), fabricas.deputado(id=2)])
    db.session.flush()
    db.session.add_all([fabricas.voto(), fabricas.voto(deputado_id=2, tipo_voto="Artigo 17")])
    db.session.commit()
    assert _placares().situacao == OK


# ======================================================
# VERIFICACAO COMPLETA
# ======================================================
def test_verificar_em_banco_sem_migracao_aponta_a_versao(db):
    _base(db)
    resultados = _por_nome(verificar_banco())
    assert resultados["Versao do esquema e a ultima migracao"].situacao == FALHA
    assert resultados["Chaves estrangeiras (foreign_key_check)"].situacao == OK


def test_periodo_invertido_e_apontado(db):
    _base(db)
    db.session.get(fabricas.Legislatura, 57).data_fim = date(2000, 1, 1)
    db.session.commit()
    assert _por_nome(verificar_banco())["legislatura: fim depois do inicio"].situacao == FALHA


def test_coleta_interrompida_vira_aviso(db, app, tmp_path):
    app.instance_path = str(tmp_path)
    db.session.add(fabricas.coleta(status="parcial"))
    db.session.commit()
    assert _por_nome(verificar_banco())["Coletas sem horario de fim (interrompidas)"].situacao == "aviso"


# ======================================================
# COMANDOS, COM BANCO EM ARQUIVO
# ======================================================
@pytest.fixture
def app_em_arquivo(tmp_path):
    classe = type("ConfigEmArquivo", (TestConfig,), {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'banco.db'}"})
    app = create_app(classe)
    app.instance_path = str(tmp_path / "instance")
    with app.app_context():
        _db.create_all()
        _base(_db)
        # Como depois do flask db upgrade
        _db.session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        _db.session.execute(text("INSERT INTO alembic_version VALUES (:v)"), {"v": _versao_mais_nova()})
        _db.session.commit()
        _db.session.remove()
    yield app
    with app.app_context():
        _db.engine.dispose()


def test_comando_verificar_grava_relatorio(app_em_arquivo, tmp_path):
    relatorio = tmp_path / "verificacao.md"
    resultado = app_em_arquivo.test_cli_runner().invoke(args=["banco", "verificar", "--relatorio", str(relatorio)])
    assert resultado.exit_code == 0, resultado.output
    assert "0 falharam" in resultado.output
    conteudo = relatorio.read_text(encoding="utf-8")
    assert "| Situação | Grupo | Verificação | Detalhe |" in conteudo
    assert "PASSOU" in conteudo


def test_comando_testar_persistencia_passa_e_nao_mexe_no_original(app_em_arquivo, tmp_path):
    resultado = app_em_arquivo.test_cli_runner().invoke(args=["banco", "testar-persistencia"])
    assert resultado.exit_code == 0, resultado.output
    assert "8 passaram, 0 falharam" in resultado.output
    with app_em_arquivo.app_context():
        assert _db.session.scalar(_db.select(_db.func.count()).select_from(Proposicao)) == 1
    # A copia e apagada no fim
    assert not (tmp_path / "instance" / "persistencia-copia.db").exists()


def test_testar_persistencia_recusa_banco_em_memoria():
    app = create_app(TestConfig)
    resultado = app.test_cli_runner().invoke(args=["banco", "testar-persistencia"])
    assert resultado.exit_code != 0
    assert "banco em arquivo" in resultado.output


def test_coleta_interrompida_e_explicada_vira_informacao(db, app, tmp_path):
    """Transparencia: a coleta fica no historico, com o motivo, e nao e apagada."""
    app.instance_path = str(tmp_path)
    db.session.add(fabricas.coleta(status="erro", mensagem_erro="Interrompida em 30/10/2026, antes do registro de fim"))
    db.session.commit()
    resultado = _por_nome(verificar_banco())["Coletas sem horario de fim (interrompidas)"]
    assert resultado.situacao == "info"
    assert "explicada" in resultado.detalhe
