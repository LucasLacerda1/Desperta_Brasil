import os
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

import fabricas
from desperta.ia.models import TrechoRAG
from desperta.noticias.models import Noticia
from desperta.orgaos.models import DeputadoOrgao
from desperta.parlamentares.models import Partido
from desperta.votacoes.models import Orientacao, Votacao


def _falha_ao_gravar(db, *objetos):
    db.session.add_all(objetos)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def _base_votacao(db):
    db.session.add_all([fabricas.orgao(), fabricas.votacao()])
    db.session.commit()


def test_votacao_aceita_id_em_texto(db):
    _base_votacao(db)
    votacao = db.session.scalar(db.select(Votacao).where(Votacao.id == "2310837-8"))
    assert votacao.id == "2310837-8"
    assert votacao.orgao.sigla == "PLEN"


def test_slug_duplicado_e_barrado(db):
    db.session.add_all([fabricas.tema(), fabricas.noticia()])
    db.session.commit()
    _falha_ao_gravar(db, fabricas.noticia(titulo="Outro titulo"))
    assert len(db.session.scalars(db.select(Noticia)).all()) == 1


def test_email_duplicado_e_barrado(db):
    db.session.add(fabricas.administrador())
    db.session.commit()
    _falha_ao_gravar(db, fabricas.administrador(nome="Outra pessoa"))


def test_trecho_duplicado_e_barrado(db):
    db.session.add(fabricas.trecho())
    db.session.commit()
    _falha_ao_gravar(db, fabricas.trecho(texto="Outro texto"))


def test_trecho_de_outro_modelo_e_aceito(db):
    db.session.add_all([fabricas.trecho(), fabricas.trecho(modelo_embedding="outro-modelo")])
    db.session.commit()
    assert len(db.session.scalars(db.select(TrechoRAG)).all()) == 2


def test_partidos_com_a_mesma_sigla_sao_aceitos(db):
    db.session.add_all([fabricas.partido(id=1), fabricas.partido(id=2, nome="Partido antigo")])
    db.session.commit()
    assert len(db.session.scalars(db.select(Partido).where(Partido.sigla == "PL")).all()) == 2


def test_fk_e_conferida_no_sqlite(db):
    _base_votacao(db)
    _falha_ao_gravar(db, fabricas.voto(deputado_id=999))


def test_mesmo_cargo_em_outra_data_e_aceito(db):
    db.session.add_all([fabricas.legislatura(), fabricas.deputado(), fabricas.orgao()])
    db.session.flush()
    campos = {"deputado_id": 204554, "orgao_id": 180, "cod_titulo": "1", "titulo": "Titular"}
    db.session.add_all(
        [
            DeputadoOrgao(data_inicio=date(2023, 2, 1), **campos),
            DeputadoOrgao(data_inicio=date(2024, 2, 1), **campos),
        ]
    )
    db.session.commit()
    assert len(db.session.scalars(db.select(DeputadoOrgao)).all()) == 2


def test_embedding_grava_e_le_3072_bytes_sem_perda(db):
    original = os.urandom(3072)
    db.session.add(fabricas.trecho(embedding=original))
    db.session.commit()
    db.session.expire_all()
    lido = db.session.scalar(db.select(TrechoRAG)).embedding
    assert lido == original
    assert len(lido) == 3072


def test_status_invalido_em_noticia_e_barrado(db):
    db.session.add(fabricas.tema())
    db.session.commit()
    _falha_ao_gravar(db, fabricas.noticia(status="inexistente"))


@pytest.mark.parametrize("campos", [{"tipo": "boletim"}, {"origem": "robo"}])
def test_outros_valores_invalidos_em_noticia(db, campos):
    db.session.add(fabricas.tema())
    db.session.commit()
    _falha_ao_gravar(db, fabricas.noticia(**campos))


def test_papel_invalido_e_barrado(db):
    _falha_ao_gravar(db, fabricas.administrador(papel="dono"))


def test_status_invalido_em_coleta_e_barrado(db):
    _falha_ao_gravar(db, fabricas.coleta(status="talvez"))


def test_sexo_invalido_e_barrado(db):
    db.session.add(fabricas.legislatura())
    db.session.commit()
    _falha_ao_gravar(db, fabricas.deputado(sexo="X"))


def test_tipo_lideranca_invalido_e_barrado(db):
    _base_votacao(db)
    _falha_ao_gravar(db, Orientacao(votacao_id="2310837-8", partido_bloco="PL", tipo_lideranca="Z", orientacao="Sim"))


def test_valores_padrao(db):
    db.session.add_all([fabricas.tema(), fabricas.noticia(), fabricas.administrador(), fabricas.visitante()])
    db.session.commit()
    noticia = db.session.scalar(db.select(Noticia))
    assert (noticia.tipo, noticia.status, noticia.visualizacoes) == ("noticia", "rascunho", 0)
    assert noticia.criado_em is not None


def test_somar_visualizacao_nao_altera_data(db):
    db.session.add_all([fabricas.tema(), fabricas.noticia()])
    db.session.commit()
    noticia = db.session.scalar(db.select(Noticia))
    noticia.visualizacoes += 1
    db.session.commit()
    assert noticia.alterado_em is None


def test_senha_guarda_hash_e_confere(db):
    admin = fabricas.administrador()
    assert admin.senha_hash != "senha-de-teste"
    assert admin.confere_senha("senha-de-teste")
    assert not admin.confere_senha("errada")
