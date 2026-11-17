"""Decisao 25.16: noticia viva (uma noticia por proposicao; fato novo vira atualizacao)."""

from datetime import date, datetime

import pytest

import fabricas
from desperta.auth import services as auth_services
from desperta.ia.geracao import gerar_noticia
from desperta.ia.gerador import GeradorFrases
from desperta.ia.models import GeracaoIA
from desperta.noticias import prioridade, viva
from desperta.noticias.models import Noticia
from desperta.noticias.services import como_detalhe_de_revisao, editar_noticia, mudar_status
from desperta.proposicoes.models import Proposicao, ProposicaoTema
from desperta.sistema.models import LogSistema
from desperta.votacoes.models import VotacaoProposicao

SINCRONIZADO = datetime(2024, 5, 16, 3, 0)


@pytest.fixture
def banco(db):
    db.session.add_all([fabricas.legislatura(), fabricas.orgao(), fabricas.tema()])
    db.session.flush()
    db.session.add_all(
        [
            fabricas.proposicao(
                ementa="Institui o Dia Nacional da Merenda.",
                cod_situacao=915,
                situacao="Aguardando Parecer",
                filhos_sincronizados_em=SINCRONIZADO,
            ),
            fabricas.votacao(
                descricao="Aprovado o Projeto de Lei nº 1.234.",
                aprovacao=True,
                data=date(2024, 5, 20),
                proposicao_id=2310837,
                filhos_sincronizados_em=SINCRONIZADO,
            ),
        ]
    )
    db.session.flush()
    db.session.add_all(
        [
            ProposicaoTema(proposicao_id=2310837, cod_tema=46, relevancia=0),
            VotacaoProposicao(votacao_id="2310837-8", proposicao_id=2310837),
        ]
    )
    db.session.commit()
    return db


@pytest.fixture
def admin(banco):
    return auth_services.criar_administrador("Lucas", "lucas@desperta.org", "senha-de-teste", "admin")


def _gerar(caso, ref):
    geracao, nova = gerar_noticia(None, caso, ref, GeradorFrases())
    assert geracao.status == "ok", geracao.erro
    return geracao.noticia


def _nova_situacao(banco, quando, codigo, nome):
    proposicao = banco.session.get(Proposicao, 2310837)
    proposicao.data_status, proposicao.cod_situacao, proposicao.situacao = quando, codigo, nome
    banco.session.commit()


def _noticias(banco):
    return banco.session.scalars(banco.select(Noticia).order_by(Noticia.id)).all()


# ======================================================
# RASCUNHO: O FATO ENTRA DIRETO NELE
# ======================================================
def test_fatos_da_mesma_proposicao_viram_uma_noticia_com_o_original_no_topo(banco):
    primeira = _gerar("nova", 2310837)
    titulo, resumo = primeira.titulo, primeira.resumo
    votacao = _gerar("votacao", "2310837-8")
    assert votacao.id == primeira.id and len(_noticias(banco)) == 1
    # Escolha do Lucas: o fato que abriu a noticia continua no topo
    assert (votacao.titulo, votacao.resumo) == (titulo, resumo)
    corpo = votacao.corpo
    assert corpo.count("## Atualizações") == 1
    atualizacao = corpo.split("## Atualizações\n\n")[1]
    assert atualizacao.startswith("### 20/05/2024: Câmara aprova projeto de lei que institui o Dia Nacional da Merenda")
    assert "O Plenário aprovou, na segunda-feira (20/05/2024), o PL 1234/2024." in atualizacao
    assert "Resultado: aprovado." in atualizacao
    assert [(f.tipo, f.ref_id) for f in votacao.fontes] == [
        ("proposicao", "2310837"),
        ("votacao", "2310837-8"),
        ("orgao", "180"),
    ]
    assert votacao.alterado_em is not None
    # As duas geracoes apontam para a mesma noticia; gerar de novo nao duplica
    assert banco.session.scalar(banco.select(banco.func.count()).select_from(GeracaoIA)) == 2
    _gerar("votacao", "2310837-8")
    assert len(_noticias(banco)) == 1 and corpo == _noticias(banco)[0].corpo
    assert banco.session.scalar(banco.select(LogSistema).filter_by(acao="atualizar_noticia_viva"))


def test_atualizacoes_da_mais_recente_para_a_mais_antiga(banco):
    _gerar("nova", 2310837)
    _gerar("votacao", "2310837-8")
    _nova_situacao(banco, datetime(2024, 5, 21, 10, 0), 926, "Aguardando Apreciação pelo Senado Federal")
    noticia = _gerar("situacao", 2310837)
    atualizacoes = noticia.corpo.split("## Atualizações\n\n")[1]
    assert atualizacoes.index("### 21/05/2024") < atualizacoes.index("### 20/05/2024")
    assert 'Situação: "Aguardando Apreciação pelo Senado Federal".' in atualizacoes


def test_texto_editado_pela_equipe_nao_e_mexido(banco, admin):
    noticia = _gerar("nova", 2310837)
    editar_noticia(noticia, admin, corpo="Texto escrito pela equipe.")
    _gerar("votacao", "2310837-8")
    assert noticia.corpo.startswith("Texto escrito pela equipe.\n\n## Atualizações\n\n### 20/05/2024")


def test_noticia_rejeitada_nao_recebe_fato_novo(banco, admin):
    noticia = _gerar("nova", 2310837)
    mudar_status(noticia, admin, "rejeitar", "Fora do escopo.")
    outra = _gerar("votacao", "2310837-8")
    assert outra.id != noticia.id and "## Atualizações" not in outra.corpo


# ======================================================
# PUBLICADA: RASCUNHO DE ATUALIZACAO
# ======================================================
def test_noticia_publicada_ganha_rascunho_de_atualizacao_que_entra_ao_publicar(banco, admin):
    original = _gerar("nova", 2310837)
    mudar_status(original, admin, "publicar")
    slug = original.slug

    rascunho = _gerar("votacao", "2310837-8")
    assert rascunho.id != original.id and rascunho.status == "rascunho"
    assert rascunho.titulo.startswith("Atualização: Câmara aprova projeto de lei")
    assert rascunho.corpo.startswith("### 20/05/2024: ")
    assert "## Atualizações" not in original.corpo
    detalhe = como_detalhe_de_revisao(rascunho)
    assert detalhe["atualiza"] == {"id": original.id, "titulo": original.titulo, "slug": slug}
    assert como_detalhe_de_revisao(original)["atualiza"] is None

    # Outro fato antes da revisao entra no mesmo rascunho de atualizacao, no topo
    _nova_situacao(banco, datetime(2024, 5, 21, 10, 0), 926, "Aguardando Apreciação pelo Senado Federal")
    assert _gerar("situacao", 2310837).id == rascunho.id
    assert rascunho.corpo.startswith("### 21/05/2024: ") and "### 20/05/2024: " in rascunho.corpo

    mudar_status(rascunho, admin, "publicar")
    assert rascunho.status == "arquivada" and rascunho.publicado_em is None
    assert original.slug == slug and original.alterado_em is not None
    atualizacoes = original.corpo.split("## Atualizações\n\n")[1]
    assert atualizacoes.index("### 21/05/2024") < atualizacoes.index("### 20/05/2024")
    assert ("votacao", "2310837-8") in [(f.tipo, f.ref_id) for f in original.fontes]
    assert [r.acao for r in original.revisoes][-1] == "editou"
    assert [r.acao for r in rascunho.revisoes][-1] == "publicou"
    assert banco.session.scalar(banco.select(LogSistema).filter_by(acao="publicar_atualizacao")).admin_id == admin.id
    # So a original e publicada: o rascunho nao vira pagina propria
    assert [n.id for n in _noticias(banco) if n.status == "publicada"] == [original.id]


def test_rascunho_de_atualizacao_editado_entra_como_a_equipe_deixou(banco, admin):
    original = _gerar("nova", 2310837)
    mudar_status(original, admin, "publicar")
    rascunho = _gerar("votacao", "2310837-8")
    editar_noticia(rascunho, admin, corpo="### 20/05/2024: Texto revisado pela equipe.")
    mudar_status(rascunho, admin, "publicar")
    assert original.corpo.endswith("## Atualizações\n\n### 20/05/2024: Texto revisado pela equipe.")


# ======================================================
# PRIORIDADE: VALE O FATO MAIS IMPORTANTE
# ======================================================
def test_prioridade_da_noticia_viva_e_a_do_fato_mais_importante(banco):
    noticia = _gerar("nova", 2310837)
    assert prioridade.calcular([noticia])[noticia.id].nivel == prioridade.MEDIA
    _gerar("votacao", "2310837-8")
    calculada = prioridade.calcular([noticia])[noticia.id]
    assert calculada.nivel == prioridade.ALTA
    assert calculada.motivos == ["votação do próprio projeto no Plenário", "projeto de lei novo"]


def test_proposicao_da_noticia(banco):
    noticia = _gerar("votacao", "2310837-8")
    assert viva.proposicao_da_noticia(noticia) == 2310837


# ======================================================
# JUNTAR OS RASCUNHOS QUE JA ESTAVAM NA FILA (ponto 3)
# ======================================================
def _rascunho_antigo(banco, titulo, entrada, fontes, criado_em, corpo="Texto antigo."):
    """Como os rascunhos de antes da 25.16: um por fato, cada um com a sua geracao."""
    import json

    from desperta.noticias.services import criar_rascunho

    noticia = criar_rascunho(titulo, f"Resumo de {titulo}.", corpo, 46, fontes)
    noticia.criado_em = criado_em
    banco.session.add(
        GeracaoIA(
            noticia_id=noticia.id,
            modelo_geracao="frases-v1",
            modelo_embedding="x",
            consulta="x",
            versao_prompt="frases-v1",
            entrada=json.dumps(entrada, sort_keys=True),
            status="ok",
        )
    )
    banco.session.commit()
    return noticia


@pytest.fixture
def fila_antiga(banco):
    proposicao = [("proposicao", "2310837")]
    nova = _rascunho_antigo(
        banco, "Projeto novo", {"caso": "nova", "proposicao_id": 2310837}, proposicao, datetime(2024, 5, 14, 12)
    )
    situacao = _rascunho_antigo(
        banco,
        "Situação nova",
        {"caso": "situacao", "proposicao_id": 2310837, "data_status": "2024-05-22T10:00:00"},
        proposicao,
        datetime(2024, 5, 22, 12),
    )
    votacao = _rascunho_antigo(
        banco,
        "Câmara aprova",
        {"caso": "votacao", "proposicao_id": 2310837, "votacao_id": "2310837-8"},
        [("votacao", "2310837-8"), ("proposicao", "2310837"), ("orgao", "180")],
        datetime(2024, 5, 23, 12),
        corpo="## O que propõe\n\nEmenta.\n\n## Resultado da votação\n\nResultado: aprovado.",
    )
    return nova, situacao, votacao


def test_juntar_os_rascunhos_da_mesma_proposicao(banco, admin, fila_antiga):
    nova, situacao, votacao = fila_antiga
    grupos, com_publicada = viva.grupos_para_juntar()
    assert list(grupos) == [2310837] and com_publicada == set()
    assert [n.id for n in grupos[2310837]] == [nova.id, situacao.id, votacao.id]

    juntada, repetidos = viva.juntar(grupos[2310837], admin)
    assert repetidos == 0
    banco.session.commit()
    assert juntada.id == nova.id and (juntada.titulo, juntada.resumo) == ("Projeto novo", "Resumo de Projeto novo.")
    assert [n.id for n in _noticias(banco)] == [nova.id]
    atualizacoes = juntada.corpo.split("## Atualizações\n\n")[1]
    # Pela data do fato: a votacao foi em 20/05 e a situacao em 22/05; a mais recente primeiro
    assert atualizacoes.index("### 22/05/2024: Situação nova") < atualizacoes.index("### 20/05/2024: Câmara aprova")
    assert "Resultado: aprovado." in atualizacoes
    assert ("votacao", "2310837-8") in [(f.tipo, f.ref_id) for f in juntada.fontes]
    # As geracoes passam para a viva: os fatos nao sao escritos de novo
    assert {g.noticia_id for g in banco.session.scalars(banco.select(GeracaoIA))} == {nova.id}
    assert (
        banco.session.scalar(
            banco.select(banco.func.count()).select_from(LogSistema).filter_by(acao="juntar_noticia_viva")
        )
        == 2
    )
    assert juntada.revisoes[-1].comentario.startswith("Notícia viva (25.16): juntou os rascunhos")
    assert viva.grupos_para_juntar() == ({}, set())


def test_proposicao_com_noticia_publicada_fica_de_fora(banco, admin, fila_antiga):
    mudar_status(fila_antiga[0], admin, "publicar")
    grupos, com_publicada = viva.grupos_para_juntar()
    assert grupos == {} and com_publicada == {2310837}


# ======================================================
# O MESMO FATO NAO E ESCRITO DE NOVO QUANDO A CAMARA ANDA (defeito achado em 17/11)
# ======================================================
def test_votacao_nao_e_escrita_de_novo_quando_a_data_da_situacao_muda(banco):
    from desperta.ia.automatico import gerar_novos

    primeira = gerar_novos(None, dias=30, hoje=date(2024, 5, 25))
    assert dict(primeira.gerados) == {"votacao": 1, "nova": 1}
    # A Camara anda um passo com a proposicao (sem mudar a situacao): a data do status muda
    banco.session.get(Proposicao, 2310837).data_status = datetime(2024, 5, 24, 9, 0)
    banco.session.commit()
    segunda = gerar_novos(None, dias=30, hoje=date(2024, 5, 25))
    # A votacao e a proposicao nova ja estao feitas; so a situacao (primeira informada, 25.1) e fato novo
    assert dict(segunda.gerados) == {"situacao": 1} and segunda.ja_feitos == 2
    assert banco.session.scalar(banco.select(banco.func.count()).select_from(GeracaoIA)) == 3
    # E a geracao a mao tambem reconhece o fato
    geracao, nova = gerar_noticia(None, "votacao", "2310837-8", GeradorFrases())
    assert nova is False


def test_juntar_conta_uma_vez_o_fato_escrito_mais_de_uma_vez(banco, admin, fila_antiga):
    nova, _, votacao = fila_antiga
    repetida = _rascunho_antigo(
        banco,
        "Câmara aprova (de novo)",
        {"caso": "votacao", "proposicao_id": 2310837, "votacao_id": "2310837-8", "data_status": "2024-05-24T09:00:00"},
        [("votacao", "2310837-8"), ("proposicao", "2310837")],
        datetime(2024, 5, 24, 12),
    )
    grupos, _ = viva.grupos_para_juntar()
    juntada, repetidos = viva.juntar(grupos[2310837], admin)
    banco.session.commit()
    assert repetidos == 1
    assert "Câmara aprova (de novo)" not in juntada.corpo and juntada.corpo.count("### 20/05/2024") == 1
    assert banco.session.get(Noticia, repetida.id) is None
    assert "1 repetiam um fato já contado" in juntada.revisoes[-1].comentario


# ======================================================
# O LEITOR VE QUE A NOTICIA FOI ATUALIZADA, COM O TITULO E O TEMA ORIGINAIS
# ======================================================
def test_api_avisa_a_atualizacao_e_mantem_titulo_e_tema(app, banco, admin):
    original = _gerar("nova", 2310837)
    titulo, tema = original.titulo, original.cod_tema
    mudar_status(original, admin, "publicar")
    cliente = app.test_client()
    antes = cliente.get(f"/api/noticias/{original.slug}").get_json()
    assert (antes["atualizada"], antes["atualizacoes"], antes["lista_de_atualizacoes"]) == (False, 0, [])

    mudar_status(_gerar("votacao", "2310837-8"), admin, "publicar")
    depois = cliente.get(f"/api/noticias/{original.slug}").get_json()
    assert depois["titulo"] == titulo and depois["tema"]["cod_tema"] == tema
    assert (depois["atualizada"], depois["atualizacoes"], depois["ultima_atualizacao"]) == (True, 1, "20/05/2024")
    [atualizacao] = depois["lista_de_atualizacoes"]
    assert atualizacao["data"] == "20/05/2024"
    assert atualizacao["titulo"].startswith("Câmara aprova projeto de lei")
    assert atualizacao["texto"].startswith("O Plenário aprovou")
    cartao = cliente.get("/api/noticias").get_json()["itens"][0]
    assert (cartao["titulo"], cartao["atualizada"]) == (titulo, True)
