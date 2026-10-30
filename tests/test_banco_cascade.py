import pytest
from sqlalchemy.exc import IntegrityError

import fabricas
from desperta.noticias.models import NoticiaFonte, NoticiaRevisao
from desperta.ia.models import GeracaoIA
from desperta.orgaos.models import PautaItem
from desperta.proposicoes.models import ProposicaoAutor, ProposicaoTema, Tramitacao
from desperta.visitantes.models import VisitanteTema
from desperta.votacoes.models import Orientacao, Votacao, VotacaoProposicao, Voto


def _total(db, modelo):
    return len(db.session.scalars(db.select(modelo)).all())


def test_apagar_noticia_apaga_fontes_e_revisoes(db):
    dados = fabricas.popular(db)
    db.session.delete(dados.noticia)
    db.session.commit()
    assert _total(db, NoticiaFonte) == 0
    assert _total(db, NoticiaRevisao) == 0
    # A execucao da IA continua registrada, sem noticia
    assert db.session.scalar(db.select(GeracaoIA)).noticia_id is None


def test_apagar_visitante_apaga_seus_temas(db):
    dados = fabricas.popular(db)
    db.session.delete(dados.visitante)
    db.session.commit()
    assert _total(db, VisitanteTema) == 0


def test_apagar_proposicao_apaga_autores_temas_e_tramitacoes(db):
    dados = fabricas.popular(db)
    db.session.delete(dados.proposicao)
    db.session.commit()
    assert _total(db, ProposicaoAutor) == 0
    assert _total(db, ProposicaoTema) == 0
    assert _total(db, Tramitacao) == 0
    assert _total(db, VotacaoProposicao) == 0
    # Quem so aponta para a proposicao continua, com o campo nulo
    assert db.session.scalar(db.select(Votacao)).proposicao_id is None
    assert db.session.scalar(db.select(PautaItem)).proposicao_id is None


def test_apagar_votacao_apaga_votos_e_orientacoes(db):
    dados = fabricas.popular(db)
    db.session.delete(dados.votacao)
    db.session.commit()
    assert _total(db, Voto) == 0
    assert _total(db, Orientacao) == 0
    assert _total(db, VotacaoProposicao) == 0
    assert db.session.scalar(db.select(PautaItem)).votacao_id is None


def test_apagar_evento_apaga_pauta(db):
    dados = fabricas.popular(db)
    db.session.delete(dados.votacao)
    db.session.delete(dados.evento)
    db.session.commit()
    assert _total(db, PautaItem) == 0


def test_remover_da_lista_apaga_o_orfao(db):
    dados = fabricas.popular(db)
    dados.visitante.temas.clear()
    db.session.commit()
    assert _total(db, VisitanteTema) == 0


def test_tema_em_uso_nao_pode_ser_apagado(db):
    dados = fabricas.popular(db)
    db.session.delete(dados.tema)
    # O ORM recusa antes de chegar ao banco, pois a FK faz parte da PK de proposicao_tema
    with pytest.raises((AssertionError, IntegrityError)):
        db.session.commit()
    db.session.rollback()
    assert _total(db, ProposicaoTema) == 1
