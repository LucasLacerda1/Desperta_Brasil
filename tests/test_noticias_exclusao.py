import pytest

import fabricas
from desperta.ext.erros import AcessoNegado, Conflito
from desperta.ia.models import GeracaoIA
from desperta.noticias.models import Noticia, NoticiaFonte, NoticiaRevisao
from desperta.noticias.services import excluir_noticia
from desperta.sistema.models import LogSistema


@pytest.fixture
def dados(db):
    d = fabricas.popular(db)
    d.admin.papel = "admin"
    db.session.commit()
    return d


def _conta(db, modelo):
    return db.session.scalar(db.select(db.func.count()).select_from(modelo))


@pytest.mark.parametrize("status", ["rascunho", "rejeitada"])
def test_admin_apaga_rascunho_ou_rejeitada_e_guarda_a_geracao(db, dados, status):
    dados.noticia.status = status
    db.session.commit()
    noticia_id, geracao_id = dados.noticia.id, dados.geracao.id

    excluir_noticia(dados.noticia, dados.admin)

    assert db.session.get(Noticia, noticia_id) is None
    assert _conta(db, NoticiaFonte) == 0 and _conta(db, NoticiaRevisao) == 0
    geracao = db.session.get(GeracaoIA, geracao_id)
    assert geracao is not None and geracao.noticia_id is None
    log = db.session.scalar(db.select(LogSistema).filter_by(acao="excluir_noticia"))
    esperado = ("admin", dados.admin.id, "noticia", str(noticia_id))
    assert (log.modulo, log.admin_id, log.entidade, log.entidade_id) == esperado


@pytest.mark.parametrize("status", ["em_revisao", "publicada", "arquivada"])
def test_noticia_que_ja_andou_no_fluxo_nao_e_apagada(db, dados, status):
    dados.noticia.status = status
    db.session.commit()
    with pytest.raises(Conflito):
        excluir_noticia(dados.noticia, dados.admin)
    assert db.session.get(Noticia, dados.noticia.id) is not None


def test_editor_nao_apaga(db, dados):
    dados.admin.papel = "editor"
    db.session.commit()
    with pytest.raises(AcessoNegado):
        excluir_noticia(dados.noticia, dados.admin)
    assert db.session.get(Noticia, dados.noticia.id) is not None


def test_admin_desativado_nao_apaga(db, dados):
    dados.admin.ativo = False
    db.session.commit()
    with pytest.raises(AcessoNegado):
        excluir_noticia(dados.noticia, dados.admin)


def test_erro_do_banco_vira_409_e_desfaz_tudo(db, dados, monkeypatch):
    def falha():
        raise AssertionError("registro em uso")

    monkeypatch.setattr(db.session, "commit", falha)
    with pytest.raises(Conflito):
        excluir_noticia(dados.noticia, dados.admin)
    monkeypatch.undo()
    assert db.session.get(Noticia, dados.noticia.id) is not None
    assert db.session.get(GeracaoIA, dados.geracao.id).noticia_id == dados.noticia.id
