"""Decisao 25.18: planta da noticia, conferidor e publicacao automatica."""

from datetime import date, datetime

import pytest

import fabricas
from desperta.auth import services as auth_services
from desperta.auth.models import Administrador
from desperta.ia.geracao import gerar_noticia
from desperta.ia.gerador import GeradorFrases
from desperta.noticias import planta
from desperta.noticias.models import Noticia, NoticiaRevisao
from desperta.noticias.services import como_foi_feita, editar_noticia, mudar_status
from desperta.proposicoes.models import Proposicao, ProposicaoTema
from desperta.sistema.models import LogSistema
from desperta.votacoes.models import VotacaoProposicao

SINCRONIZADO = datetime(2024, 5, 16, 3, 0)
CORPO = "## O que propõe\n\nEmenta.\n\n## Onde está na Câmara\n\nSituação: x."
BOM = (
    "PL 1234/2024 institui o Dia Nacional da Merenda",
    "O projeto de lei PL 1234/2024 foi apresentado em 14/05/2024.",
)


# ======================================================
# REGRAS DO TEXTO
# ======================================================
def _falhas(titulo=BOM[0], resumo=BOM[1], corpo=CORPO, caso="nova", **campos):
    return planta.conferir_texto(titulo, resumo, corpo, caso, **campos).falhas


def test_texto_na_planta_passa():
    assert _falhas() == []


@pytest.mark.parametrize(
    "campos,falha",
    [
        ({"titulo": "PL 1/2024 " + "x" * 120}, "título com 130 caracteres"),
        ({"titulo": "PL 1234/2024 institui o Dia…"}, "título cortado no meio"),
        ({"titulo": "Projeto institui o Dia Nacional da Merenda"}, "título sem a sigla"),
        ({"resumo": "Uma frase. Outra frase. Mais uma frase."}, "parágrafo principal com 3 frases"),
        ({"resumo": "O projeto de lei PL 1/2024 teve 300 votos a favor."}, "placar no parágrafo principal"),
        ({"resumo": "O projeto de lei PL 1/2024 não foi informado."}, "o que a Câmara não informou"),
        ({"resumo": "O PL 1234/2024 foi apresentado em 14/05/2024."}, "sigla PL sem explicação"),
        ({"resumo": "O projeto de lei PL 1/2024 é polêmico."}, "palavra de opinião: polêmic"),
        ({"titulo": "Câmara finalmente aprova PL 1234/2024"}, "palavra de opinião: finalmente"),
        ({"corpo": "## O que propõe\n\nEmenta."}, "faltam os blocos: Onde está na Câmara"),
        ({"caso": "votacao"}, "faltam os blocos: Resultado da votação"),
        ({"caso": None}, "caso sem planta"),
    ],
)
def test_cada_regra_da_planta(campos, falha):
    falhas = _falhas(**campos)
    assert any(f.startswith(falha) for f in falhas), falhas


def test_avisos_nao_seguram_a_publicacao():
    longo = "O projeto de lei PL 1234/2024 foi apresentado em 14/05/2024 " + "e trata de muitas coisas " * 12 + "."
    conferencia = planta.conferir_texto(BOM[0], longo, CORPO, "nova")
    assert conferencia.avisos and any("palavras" in falha for falha in conferencia.falhas)
    curto = planta.conferir_texto(BOM[0], "O projeto de lei PL 1/2024 " + "e mais " * 12 + "fim.", CORPO, "nova")
    assert curto.passou and curto.avisos == ["1 frase(s) do parágrafo principal com mais de 25 palavras"]


def test_boletim_e_atualizacao_tem_regras_proprias():
    # Boletim: sem sigla no titulo e sem os blocos de noticia
    assert planta.conferir_texto(
        "Boletim de 16/11/2026: votações nas comissões", "Em 16/11/2026, 2 votações.", "", "boletim", tipo="relatorio"
    ).passou
    # Rascunho de atualizacao: o titulo nao vai ao ar (entra na noticia original)
    assert planta.conferir_texto(
        "Atualização: " + "x" * 200, BOM[1], "### 20/05/2024: x", "votacao", atualizacao=True
    ).passou


# ======================================================
# CONFIANCA E PUBLICACAO
# ======================================================
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


def _gerar(caso="nova", ref=2310837):
    # A geracao usa o sqlite-vec (grupo ia do pyproject); sem ele o teste e pulado
    pytest.importorskip("sqlite_vec")
    geracao, _ = gerar_noticia(None, caso, ref, GeradorFrases())
    assert geracao.status == "ok", geracao.erro
    return geracao.noticia


def test_noticia_gerada_na_planta_passa_e_a_antiga_nao(banco):
    noticia = _gerar()
    conferencia = planta.conferir(noticia)
    assert conferencia.passou, conferencia.falhas
    antiga = fabricas.noticia(slug="antiga", corpo=CORPO)
    banco.session.add(antiga)
    banco.session.commit()
    assert "escrita antes da planta (rascunho antigo)" in planta.conferir(antiga).falhas


def test_equipe_mexendo_falha_grave_e_situacao_desconhecida_vao_para_a_equipe(banco):
    noticia = _gerar()
    admin = auth_services.criar_administrador("Lucas", "lucas@desperta.org", "senha-de-teste", "admin")
    editar_noticia(noticia, admin, resumo=noticia.resumo + " ")  # sem mudança de texto: nao conta
    assert planta.conferir(noticia).passou
    editar_noticia(noticia, admin, titulo="PL 1234/2024 institui o Dia da Merenda")
    assert "a equipe já mexeu neste rascunho" in planta.conferir(noticia).falhas

    outra = _gerar("votacao", "2310837-8")
    banco.session.add_all([fabricas.deputado(), fabricas.voto(tipo_voto=None)])
    proposicao = banco.session.get(Proposicao, 2310837)
    proposicao.cod_situacao, proposicao.situacao = 9999, "Situação nova"
    banco.session.commit()
    falhas = planta.conferir(outra).falhas
    assert "falha grave nos dados da Câmara: so_placar" in falhas
    assert "situação fora do dicionário: 'Situação nova'" in falhas


def test_ensaio_so_conta_e_ligada_publica_com_o_usuario_tecnico(app, banco):
    noticia = _gerar()
    ensaio = planta.publicar_automaticas("ensaio")
    assert (ensaio.conferidas, ensaio.publicaveis, ensaio.publicadas) == (1, 1, 0)
    assert noticia.status == "rascunho"
    assert banco.session.scalar(banco.select(LogSistema).filter_by(acao="publicacao_automatica"))

    ligada = planta.publicar_automaticas("ligada")
    assert (ligada.publicadas, noticia.status) == (1, "publicada")
    sistema = banco.session.scalar(banco.select(Administrador).filter_by(email=planta.EMAIL_DO_SISTEMA))
    assert sistema.nome == "Publicação automática" and sistema.ativo is False
    revisao = banco.session.scalar(banco.select(NoticiaRevisao).filter_by(noticia_id=noticia.id))
    assert (revisao.acao, revisao.admin_id) == ("publicou", sistema.id)
    feita = como_foi_feita(noticia)
    assert feita["publicada_automaticamente"] is True and feita["revisada_pela_equipe"] is False
    assert feita["publicada_por"] == "Publicação automática"
    # Ninguem entra com o usuario tecnico
    assert (
        app.test_client().post("/api/auth/login", json={"email": planta.EMAIL_DO_SISTEMA, "senha": "x"}).status_code
        != 200
    )


def test_fato_novo_de_publicada_sai_sozinho_como_atualizacao(banco):
    original = _gerar()
    planta.publicar_automaticas("ligada")
    rascunho = _gerar("votacao", "2310837-8")
    assert rascunho.id != original.id and rascunho.titulo.startswith("Atualização:")
    resultado = planta.publicar_automaticas("ligada")
    assert resultado.publicadas == 1
    assert rascunho.status == "arquivada" and "## Atualizações" in original.corpo


def test_desligada_nao_confere_nada(banco):
    _gerar()
    resultado = planta.publicar_automaticas("desligada")
    assert resultado.conferidas == 0 and resultado.em_texto() == "publicacao automatica desligada"
    with pytest.raises(ValueError):
        planta.publicar_automaticas("talvez")


def test_publicada_pela_equipe_e_revisada(banco):
    noticia = _gerar()
    admin = auth_services.criar_administrador("Lucas", "lucas@desperta.org", "senha-de-teste", "admin")
    mudar_status(noticia, admin, "publicar")
    feita = como_foi_feita(noticia)
    assert feita["publicada_automaticamente"] is False and feita["revisada_pela_equipe"] is True


def test_fila_mostra_a_conferencia(app, banco):
    _gerar()
    auth_services.criar_administrador("Caio", "caio@desperta.org", "senha-de-teste", "editor")
    cliente = app.test_client()
    assert (
        cliente.post("/api/auth/login", json={"email": "caio@desperta.org", "senha": "senha-de-teste"}).status_code
        == 200
    )
    item = cliente.get("/api/noticias/admin").get_json()["itens"][0]
    assert item["conferencia"]["passou"] is True
    assert cliente.get(f"/api/noticias/admin/{item['id']}").get_json()["conferencia"]["passou"] is True


def test_comando_publicar_automaticas(app, banco):
    _gerar()
    resultado = app.test_cli_runner().invoke(args=["ia", "publicar-automaticas", "--modo", "ensaio"])
    assert resultado.exit_code == 0 and "publicaria (ensaio)=1" in resultado.output
    assert banco.session.scalar(banco.select(Noticia.status)) == "rascunho"
