from collections import Counter
from datetime import datetime

import pytest

import fabricas
from desperta.proposicoes.services import informado, ou_nao_informado
from desperta.sistema.models import LogSistema
from desperta.votacoes import services as votacoes
from desperta.votacoes.models import Votacao


# ======================================================
# CAMPOS QUE A CAMARA NAO INFORMOU
# ======================================================
@pytest.mark.parametrize("valor", [None, "", ".", "  .  ", "-"])
def test_valores_que_significam_nao_informado(valor):
    assert informado(valor) is None
    assert ou_nao_informado(valor) == "não informado pela Câmara"
    assert ou_nao_informado(valor, feminino=True) == "não informada pela Câmara"


def test_valor_informado_volta_sem_espacos():
    assert informado("  Urgência ") == "Urgência"
    assert ou_nao_informado("Ordinária") == "Ordinária"


# ======================================================
# SITUACAO DOS VOTOS
# ======================================================
@pytest.fixture
def votacao(db):
    db.session.add_all([fabricas.legislatura(), fabricas.orgao()])
    db.session.flush()
    db.session.add_all([fabricas.deputado(), fabricas.deputado(id=2), fabricas.votacao()])
    db.session.commit()
    return db.session.get(Votacao, "2310837-8")


def _completa(db, votacao, descricao=None):
    votacao.filhos_sincronizados_em = datetime(2024, 5, 15)
    if descricao:
        votacao.descricao = descricao
    db.session.commit()


def test_votacao_ainda_sem_os_votos_e_pendente(db, votacao):
    situacao = votacoes.situacao_dos_votos(votacao)
    assert (situacao.codigo, situacao.explicacao) == (
        votacoes.PENDENTE,
        "Os votos desta votação ainda estão sendo coletados.",
    )


def test_votacao_pendente_com_erro_no_log_e_erro_na_coleta(db, votacao):
    db.session.add(
        LogSistema(
            nivel="erro",
            modulo="coletor",
            acao="gravar_registro",
            descricao="x",
            entidade="voto",
            entidade_id="2310837-8/204554",
        )
    )
    db.session.commit()
    assert votacoes.situacao_dos_votos(votacao).codigo == votacoes.ERRO_NA_COLETA


def test_votacao_completa_sem_votos_e_simbolica(db, votacao):
    _completa(db, votacao)
    assert votacoes.situacao_dos_votos(votacao).codigo == votacoes.SIMBOLICA


def test_votacao_com_todos_os_votos_sem_tipo_e_secreta(db, votacao):
    _completa(db, votacao, "Aprovado. Sim: 404; Não: 61; Abstenção: 1; Total: 466.")
    db.session.add_all([fabricas.voto(tipo_voto=None), fabricas.voto(deputado_id=2, tipo_voto=None)])
    db.session.commit()
    situacao = votacoes.situacao_dos_votos(votacao)
    assert situacao.codigo == votacoes.SECRETA
    assert situacao.explicacao == (
        "Votação secreta: a Câmara divulgou só o placar total (404 a favor, 61 contra e 1 abstenção)."
    )
    assert situacao.placar_da_camara == {"Sim": 404, "Não": 61, "Abstenção": 1, "Total": 466}


def test_votacao_com_parte_dos_votos_sem_tipo_e_inconsistente(db, votacao):
    _completa(db, votacao)
    db.session.add_all([fabricas.voto(), fabricas.voto(deputado_id=2, tipo_voto=None)])
    db.session.commit()
    situacao = votacoes.situacao_dos_votos(votacao)
    assert situacao.codigo == votacoes.INCONSISTENTE
    assert "1 dos 2 votos" in situacao.explicacao


def test_votacao_com_votos_e_nominal(db, votacao):
    _completa(db, votacao)
    db.session.add_all([fabricas.voto(), fabricas.voto(deputado_id=2, tipo_voto="Não")])
    db.session.commit()
    situacao = votacoes.situacao_dos_votos(votacao)
    assert (situacao.codigo, situacao.explicacao) == (votacoes.NOMINAL, "Votação nominal: 2 votos registrados.")
    assert situacao.votos == Counter({"Sim": 1, "Não": 1})


@pytest.mark.parametrize(
    "placar,frase",
    [
        ({"Sim": 299, "Não": 134, "Abstenção": 3}, "299 a favor, 134 contra e 3 abstenções"),
        ({"Sim": 1, "Não": 0}, "1 a favor e 0 contra"),
        ({"Sim": 10, "Não": 2, "Abstenção": 1, "Obstrução": 2}, "10 a favor, 2 contra, 1 abstenção e 2 obstruções"),
        ({}, ""),
    ],
)
def test_placar_em_frase(placar, frase):
    assert votacoes.placar_em_frase(placar) == frase
