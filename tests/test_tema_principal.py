"""Decisao 25.2: o tema principal da proposicao (relevancia 0 na API) e a ordem dos temas."""

import pytest

import fabricas
from desperta.proposicoes.models import ProposicaoTema
from desperta.proposicoes.services import tema_principal

ADMINISTRACAO, ECONOMIA, EDUCACAO, SAUDE = 34, 40, 46, 56


@pytest.fixture
def banco(db):
    db.session.add_all(
        [
            fabricas.tema(),
            fabricas.tema(cod_tema=SAUDE, nome="Saude", icone="medical_services"),
            fabricas.tema(cod_tema=ADMINISTRACAO, nome="Administracao Publica", icone="domain"),
            fabricas.tema(cod_tema=ECONOMIA, nome="Economia", icone="payments"),
        ]
    )
    db.session.add_all(fabricas.proposicao(id=numero, numero=numero) for numero in range(1, 8))
    db.session.commit()
    return db


def _temas(banco, proposicao_id, *pares):
    banco.session.add_all(
        ProposicaoTema(proposicao_id=proposicao_id, cod_tema=cod_tema, relevancia=relevancia)
        for cod_tema, relevancia in pares
    )
    banco.session.commit()


def test_com_a_ordem_da_camara_o_principal_e_o_de_relevancia_zero(banco):
    # Antes o codigo pegava a maior relevancia, que e o ultimo tema da lista da Camara
    _temas(banco, 1, (ADMINISTRACAO, 1), (SAUDE, 0), (EDUCACAO, 2))
    assert tema_principal(1) == SAUDE


def test_proposicao_com_um_tema_so_e_sem_tema(banco):
    _temas(banco, 1, (EDUCACAO, 0))
    assert tema_principal(1) == EDUCACAO
    assert tema_principal(2) is None


def test_sem_ordem_vale_o_tema_que_a_camara_mais_poe_em_primeiro(banco):
    # Nas proposicoes que a Camara ordenou, Saude vem na frente de Administracao Publica
    for proposicao_id in (1, 2, 3):
        _temas(banco, proposicao_id, (SAUDE, 0), (ADMINISTRACAO, 1))
    # Proposicao antiga, com todos os temas em 0: o menor codigo (34) nao decide mais
    _temas(banco, 4, (ADMINISTRACAO, 0), (SAUDE, 0))
    assert tema_principal(4) == SAUDE


def test_tema_que_a_camara_costuma_deixar_por_ultimo_perde_para_um_nunca_visto(banco):
    for proposicao_id in (1, 2, 3):
        _temas(banco, proposicao_id, (SAUDE, 0), (ADMINISTRACAO, 1))
    _temas(banco, 4, (ADMINISTRACAO, 0), (ECONOMIA, 0))
    assert tema_principal(4) == ECONOMIA


def test_sem_ordem_e_sem_historico_fica_o_menor_codigo(banco):
    _temas(banco, 4, (EDUCACAO, 0), (ECONOMIA, 0))
    assert tema_principal(4) == ECONOMIA


def test_api_mostra_os_temas_na_ordem_da_camara(app, banco):
    _temas(banco, 1, (ADMINISTRACAO, 2), (SAUDE, 0), (EDUCACAO, 1))
    temas = app.test_client().get("/api/proposicoes/1").get_json()["temas"]
    assert [tema["cod_tema"] for tema in temas] == [SAUDE, EDUCACAO, ADMINISTRACAO]


# ======================================================
# DECISAO 25.6: PROPOSICAO SEM TEMA DA CAMARA
# ======================================================
def test_tema_da_noticia_usa_o_tema_especial_e_cria_uma_vez_so(banco):
    from desperta.proposicoes.models import TEMA_SEM_CLASSIFICACAO, Tema
    from desperta.proposicoes.services import HASH_DO_PORTAL, tema_da_noticia

    _temas(banco, 1, (SAUDE, 0))
    assert tema_da_noticia(1) == (SAUDE, True)
    assert banco.session.get(Tema, TEMA_SEM_CLASSIFICACAO) is None
    assert tema_da_noticia(2) == (TEMA_SEM_CLASSIFICACAO, False)
    assert tema_da_noticia(3) == (TEMA_SEM_CLASSIFICACAO, False)
    banco.session.commit()
    especial = banco.session.get(Tema, TEMA_SEM_CLASSIFICACAO)
    assert especial.nome == "Sem tema informado pela Câmara" and especial.hash_origem == HASH_DO_PORTAL
    # O hash passa na verificacao do banco (SHA-256 em hexadecimal)
    assert len(HASH_DO_PORTAL) == 64 and int(HASH_DO_PORTAL, 16) >= 0


def test_api_da_proposicao_avisa_quando_nao_ha_tema(app, banco):
    _temas(banco, 1, (SAUDE, 0))
    cliente = app.test_client()
    assert cliente.get("/api/proposicoes/1").get_json()["aviso_tema"] is None
    assert cliente.get("/api/proposicoes/2").get_json()["aviso_tema"] == (
        "A Câmara ainda não informou o tema desta proposição."
    )


def test_tema_especial_aparece_na_lista_de_temas_do_portal(app, banco):
    from desperta.proposicoes.services import tema_sem_classificacao

    tema_sem_classificacao()
    banco.session.commit()
    nomes = [t["nome"] for t in app.test_client().get("/api/proposicoes/temas").get_json()["itens"]]
    assert "Sem tema informado pela Câmara" in nomes
