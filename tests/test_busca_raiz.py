"""Decisao 25.3: a busca compara a raiz das palavras, com ou sem acento."""

from datetime import datetime

import pytest

import fabricas
from desperta.ext.db.busca import grupos_de_raizes, raiz, raizes_da_consulta
from desperta.noticias.services import buscar_noticias

PUBLICADA_EM = datetime(2026, 11, 10, 15, 0)


@pytest.fixture
def noticia(db):
    def criar(**campos):
        if db.session.get(fabricas.Tema, 46) is None:
            db.session.add(fabricas.tema())
        item = fabricas.noticia(**{"status": "publicada", "publicado_em": PUBLICADA_EM, **campos})
        db.session.add(item)
        db.session.commit()
        return item

    return criar


# ======================================================
# A FUNCAO
# ======================================================
@pytest.mark.parametrize(
    "formas",
    [
        ("professor", "professores", "professora", "professoras"),
        ("vacina", "vacinas", "vacinar", "vacinação"),
        ("escola", "escolas", "escolar"),
        ("idoso", "idosa", "idosos"),
    ],
)
def test_formas_da_mesma_palavra_tem_uma_raiz_em_comum(formas):
    comuns = set.intersection(*(set(raizes_da_consulta(forma)) for forma in formas))
    assert comuns, formas


def test_palavra_com_acento_guarda_tambem_a_raiz_sem_acento():
    # O Snowball depende do acento: quem digita "vacinacao" precisa achar "vacinação"
    assert set(raizes_da_consulta("vacinacao")) <= set(raiz("vacinação").split())
    assert set(raizes_da_consulta("previdencia")) <= set(raiz("Previdência").split())
    assert raiz("PL 1234/2024") == "pl 1234 2024"


def test_texto_vazio_e_pontuacao_nao_tem_raiz():
    assert raiz(None) == "" and raiz("") == "" and raiz("... !?") == ""
    assert grupos_de_raizes("... !?") == [] and raizes_da_consulta(None) == []


def test_consulta_nao_repete_palavra():
    assert grupos_de_raizes("escola Escola ESCOLAS") == [("escol",)]


# ======================================================
# BUSCA DO PORTAL
# ======================================================
def test_busca_acha_plural_genero_e_verbo(noticia):
    item = noticia(titulo="Piso salarial das professoras", resumo="Reajuste", corpo="Vacinação de idosos em casa.")
    for termo in ("professores", "professor", "salarial professora", "vacinar idosa", "vacinas"):
        assert buscar_noticias(termo) == [item], termo


def test_busca_sem_acento_acha_texto_com_acento(noticia):
    item = noticia(titulo="Previdência", resumo="Educação básica", corpo="Vacinação e saúde pública.")
    for termo in ("previdencia", "educacao basica", "VACINACAO", "saude publica", "previdência"):
        assert buscar_noticias(termo) == [item], termo


def test_todas_as_palavras_da_busca_precisam_aparecer(noticia):
    noticia(titulo="Merenda escolar", resumo="r", corpo="c")
    assert buscar_noticias("merenda") != []
    assert buscar_noticias("merenda transporte") == []


def test_busca_com_aspas_e_simbolos_nao_quebra(noticia):
    item = noticia(titulo="Merenda escolar", resumo="r", corpo="c")
    assert buscar_noticias('"merenda" (escolar) * ^ : -') == [item]
    assert buscar_noticias('" ) (') == []
    # AND e OR digitados sao palavras como as outras, nao comandos do MATCH
    assert buscar_noticias("merenda OR transporte") == []


def test_indice_das_raizes_acompanha_edicao_e_exclusao(db, noticia):
    item = noticia(titulo="Merenda escolar", resumo="r", corpo="c")
    item.titulo = "Transporte de estudantes"
    db.session.commit()
    assert buscar_noticias("estudante") == [item]
    assert buscar_noticias("merendas") == []
    db.session.delete(item)
    db.session.commit()
    assert buscar_noticias("estudante") == []
    assert db.session.execute(db.text("SELECT COUNT(*) FROM noticia_fts_raiz_docsize")).scalar() == 0


def test_o_banco_nao_tem_gatilho_que_dependa_do_codigo(db, noticia):
    # Com gatilho chamando raiz(), outra versao do codigo (outra branch) nao conseguiria gravar noticia
    noticia(titulo="Merenda escolar", resumo="r", corpo="c")
    gatilhos = db.session.execute(db.text("SELECT sql FROM sqlite_master WHERE type = 'trigger'")).scalars().all()
    assert gatilhos and not any("raiz(" in sql for sql in gatilhos)


def test_noticia_gravada_fora_do_orm_entra_na_conferencia(db, noticia):
    from desperta.ext.db.busca import conferir_busca_raiz

    item = noticia(titulo="Merenda escolar", resumo="r", corpo="c")
    # Como se uma versao antiga do codigo tivesse gravado a noticia: o indice das raizes fica sem ela
    db.session.execute(db.text("DELETE FROM noticia_fts_raiz"))
    db.session.commit()
    assert buscar_noticias("merendas") == []
    with db.engine.begin() as conexao:
        assert conferir_busca_raiz(conexao) is True
        assert conferir_busca_raiz(conexao) is False
    assert buscar_noticias("merendas") == [item]


def test_somar_visualizacao_nao_reindexa(db, noticia):
    item = noticia(titulo="Merenda escolar", resumo="r", corpo="c")
    ler = db.text("SELECT rowid, titulo FROM noticia_fts_raiz")
    antes = db.session.execute(ler).all()
    item.visualizacoes += 1
    db.session.commit()
    assert db.session.execute(ler).all() == antes == [(item.id, "merend escol")]
