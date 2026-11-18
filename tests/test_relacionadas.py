"""Decisao 25.13 (item 5): noticias relacionadas pelas fontes em comum."""

from datetime import datetime

import pytest

import fabricas
from desperta.noticias.models import NoticiaFonte
from desperta.noticias.relacionadas import chaves_da_noticia, relacionadas
from desperta.votacoes.models import VotacaoProposicao

PROJETO = 2310837
OUTRO = 2310900
VOTACAO = "2310837-8"


@pytest.fixture
def banco(db):
    db.session.add_all([fabricas.legislatura(), fabricas.orgao(), fabricas.tema()])
    db.session.flush()
    db.session.add_all(
        [
            fabricas.proposicao(),
            fabricas.proposicao(id=OUTRO, numero=5678),
            fabricas.votacao(proposicao_id=PROJETO),
        ]
    )
    db.session.flush()
    db.session.add(VotacaoProposicao(votacao_id=VOTACAO, proposicao_id=PROJETO))
    db.session.commit()
    return db


def _noticia(banco, slug, fontes, status="publicada", dia=10, tipo="noticia"):
    noticia = fabricas.noticia(
        slug=slug,
        titulo=slug,
        status=status,
        tipo=tipo,
        publicado_em=datetime(2026, 11, dia, 12, 0) if status == "publicada" else None,
    )
    for ordem, (tipo_fonte, ref) in enumerate(fontes, start=1):
        noticia.fontes.append(NoticiaFonte(tipo=tipo_fonte, ref_id=str(ref), ordem=ordem))
    banco.session.add(noticia)
    banco.session.commit()
    return noticia


def _slugs(noticias):
    return [n.slug for n in noticias]


def test_mesma_proposicao_liga_e_a_votacao_conta_a_proposicao_que_afeta(banco):
    projeto = _noticia(banco, "projeto", [("proposicao", PROJETO)])
    votacao = _noticia(banco, "votacao-do-projeto", [("votacao", VOTACAO)])
    _noticia(banco, "outro-projeto", [("proposicao", OUTRO)])

    assert _slugs(relacionadas(projeto)) == ["votacao-do-projeto"]
    assert _slugs(relacionadas(votacao)) == ["projeto"]


def test_so_publicadas_e_nunca_ela_mesma(banco):
    projeto = _noticia(banco, "projeto", [("proposicao", PROJETO)])
    _noticia(banco, "rascunho", [("proposicao", PROJETO)], status="rascunho")
    _noticia(banco, "arquivada", [("proposicao", PROJETO)], status="arquivada")

    assert relacionadas(projeto) == []


def test_deputado_e_partido_nao_ligam(banco):
    projeto = _noticia(banco, "projeto", [("proposicao", PROJETO), ("deputado", 204554)])
    _noticia(banco, "outro-projeto", [("proposicao", OUTRO), ("deputado", 204554)])

    assert relacionadas(projeto) == []
    assert ("deputado", "204554") not in chaves_da_noticia(projeto)


def test_mais_fontes_em_comum_primeiro_e_no_empate_a_mais_recente(banco):
    projeto = _noticia(banco, "projeto", [("proposicao", PROJETO), ("orgao", 180)])
    _noticia(banco, "votacao-antiga", [("votacao", VOTACAO)], dia=11)
    _noticia(banco, "votacao-recente", [("votacao", VOTACAO)], dia=15)
    _noticia(
        banco,
        "boletim",
        [("proposicao", PROJETO), ("votacao", VOTACAO), ("orgao", 180)],
        dia=12,
        tipo="relatorio",
    )

    assert _slugs(relacionadas(projeto)) == ["boletim", "votacao-recente", "votacao-antiga"]


def test_orgao_sozinho_nao_liga_so_reforca(banco):
    projeto = _noticia(banco, "projeto", [("proposicao", PROJETO), ("orgao", 180)])
    _noticia(banco, "outra-do-plenario", [("proposicao", OUTRO), ("orgao", 180)], dia=15)
    _noticia(banco, "votacao-no-plenario", [("votacao", VOTACAO), ("orgao", 180)], dia=11)
    _noticia(banco, "votacao-sem-orgao", [("votacao", VOTACAO)], dia=14)

    assert _slugs(relacionadas(projeto)) == ["votacao-no-plenario", "votacao-sem-orgao"]


def test_no_maximo_cinco(banco):
    projeto = _noticia(banco, "projeto", [("proposicao", PROJETO)])
    for dia in range(1, 9):
        _noticia(banco, f"boletim-{dia}", [("votacao", VOTACAO)], dia=dia, tipo="relatorio")

    assert _slugs(relacionadas(projeto)) == [f"boletim-{dia}" for dia in range(8, 3, -1)]


def test_noticia_sem_fonte_que_ligue_nao_tem_relacionadas(banco):
    sem_fonte = _noticia(banco, "sem-fonte", [])
    _noticia(banco, "projeto", [("proposicao", PROJETO)])

    assert relacionadas(sem_fonte) == []


def test_a_pagina_da_noticia_traz_as_relacionadas_como_cartoes(banco, app):
    _noticia(banco, "projeto", [("proposicao", PROJETO)])
    _noticia(banco, "votacao-do-projeto", [("votacao", VOTACAO)])

    dados = app.test_client().get("/api/noticias/projeto").get_json()

    assert [r["slug"] for r in dados["relacionadas"]] == ["votacao-do-projeto"]
    assert set(dados["relacionadas"][0]) >= {"titulo", "slug", "resumo", "tema", "publicado_em"}
