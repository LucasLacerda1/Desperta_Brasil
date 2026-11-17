"""Decisao 25.17: boletins do dia para os fatos pequenos."""

from datetime import date, datetime

import pytest

import fabricas
from desperta.ia import boletim
from desperta.ia.models import GeracaoIA
from desperta.noticias import prioridade
from desperta.noticias.models import Noticia
from desperta.proposicoes.models import Proposicao, ProposicaoAutor, ProposicaoTema, Tema
from desperta.proposicoes.situacoes import SITUACOES
from desperta.sistema.models import LogSistema
from desperta.votacoes.models import Votacao, VotacaoProposicao

DIA = date(2026, 11, 16)
SINCRONIZADO = datetime(2026, 11, 16, 22, 0)


def _proposicao(id, sigla="PL", **campos):
    dados = {
        "id": id,
        "numero": id,
        "ano": 2026,
        "sigla_tipo": sigla,
        "ementa": f"Ementa da proposição {id}.",
        "data_apresentacao": datetime(2026, 3, 1, 10, 0),
        "filhos_sincronizados_em": SINCRONIZADO,
    }
    return fabricas.proposicao(**{**dados, **campos})


@pytest.fixture
def banco(db):
    """
    Dia 16/11/2026:
    - PL 1: votacao do projeto no Plenario (grande) e votacao de requerimento no Plenario (pequena);
    - PL 2: votacao na CCJC e na CFT (pequenas);
    - PL 3: situacao mudou para "Aguardando Parecer" (pequena); PL 4: para "Pronta para Pauta" (marco, grande);
    - PDL 5 apresentado no dia (pequeno); PL 6 apresentado no dia (grande).
    """
    db.session.add_all(
        [
            fabricas.legislatura(),
            fabricas.orgao(),
            fabricas.orgao(id=2003, sigla="CCJC", nome="Comissão de Constituição e Justiça"),
            fabricas.orgao(id=2004, sigla="CFT", nome="Comissão de Finanças e Tributação"),
            fabricas.tema(),
            fabricas.tema(cod_tema=53, nome="Processo Legislativo e Atuação Parlamentar"),
        ]
    )
    db.session.flush()
    db.session.add_all(
        [
            _proposicao(1, cod_situacao=915, situacao="Aguardando Parecer"),
            _proposicao(2, cod_situacao=915, situacao="Aguardando Parecer"),
            _proposicao(3, cod_situacao=915, situacao="Aguardando Parecer", data_status=datetime(2026, 11, 16, 9)),
            _proposicao(4, cod_situacao=924, situacao="Pronta para Pauta", data_status=datetime(2026, 11, 16, 9)),
            fabricas.proposicao(
                id=5,
                numero=5,
                ano=2026,
                sigla_tipo="PDL",
                ementa="Susta os efeitos do decreto.",
                data_apresentacao=datetime(2026, 11, 16, 11),
                filhos_sincronizados_em=SINCRONIZADO,
            ),
            _proposicao(6, data_apresentacao=datetime(2026, 11, 16, 12)),
        ]
    )
    db.session.flush()

    def votacao(id, proposicao_id, orgao_id, sigla, descricao):
        db.session.add(
            fabricas.votacao(
                id=id,
                data=DIA,
                data_hora_registro=datetime(2026, 11, 16, 15),
                orgao_id=orgao_id,
                sigla_orgao=sigla,
                descricao=descricao,
                aprovacao=True,
                proposicao_id=proposicao_id,
                filhos_sincronizados_em=SINCRONIZADO,
            )
        )
        db.session.flush()
        db.session.add(VotacaoProposicao(votacao_id=id, proposicao_id=proposicao_id))

    votacao("1-1", 1, 180, "PLEN", "Aprovado o Projeto de Lei nº 1, de 2026.")
    votacao("1-2", 1, 180, "PLEN", "Aprovado o Requerimento de Urgência.")
    votacao("2-1", 2, 2003, "CCJC", "Aprovado o Parecer.")
    votacao("2-2", 2, 2004, "CFT", "Aprovado o Parecer.")
    for id in (1, 2, 3, 4, 5, 6):
        db.session.add(ProposicaoTema(proposicao_id=id, cod_tema=46, relevancia=0))
    db.session.add(
        ProposicaoAutor(proposicao_id=5, ordem=1, nome="Fulana", cod_tipo=1, tipo="Deputado", proponente=True)
    )
    db.session.add_all(
        [
            fabricas.tramitacao(
                proposicao_id=3, sequencia=1, data_hora=datetime(2026, 3, 1), cod_situacao=907, situacao="x"
            ),
            fabricas.tramitacao(
                proposicao_id=4, sequencia=1, data_hora=datetime(2026, 3, 1), cod_situacao=915, situacao="x"
            ),
        ]
    )
    db.session.commit()
    return db


# ======================================================
# CLASSIFICACAO
# ======================================================
def _classe(banco, caso, proposicao_id, votacao_id=None):
    proposicao = banco.session.get(Proposicao, proposicao_id)
    votacao = banco.session.get(Votacao, votacao_id) if votacao_id else None
    resultado = boletim.classificar(caso, proposicao, votacao)
    return resultado.destino, resultado.categoria


@pytest.mark.parametrize(
    "caso,proposicao_id,votacao_id,esperado",
    [
        ("votacao", 1, "1-1", ("propria", None)),
        ("votacao", 1, "1-2", ("boletim", "plenario")),
        ("votacao", 2, "2-1", ("boletim", "comissoes")),
        ("situacao", 3, None, ("boletim", "andamento")),
        ("situacao", 4, None, ("propria", None)),
        ("nova", 5, None, ("boletim", "novas")),
        ("nova", 6, None, ("propria", None)),
    ],
)
def test_classificacao(banco, caso, proposicao_id, votacao_id, esperado):
    assert _classe(banco, caso, proposicao_id, votacao_id) == esperado


def test_situacao_nao_informada_vai_para_o_andamento(banco):
    proposicao = banco.session.get(Proposicao, 3)
    proposicao.cod_situacao, proposicao.situacao = None, None
    banco.session.commit()
    assert _classe(banco, "situacao", 3) == ("boletim", "andamento")


def test_falha_grave_da_camara_vira_noticia_propria(banco):
    banco.session.add_all([fabricas.deputado(), fabricas.voto(votacao_id="2-1", tipo_voto=None)])
    banco.session.commit()
    resultado = boletim.classificar("votacao", banco.session.get(Proposicao, 2), banco.session.get(Votacao, "2-1"))
    assert resultado.destino == "propria" and resultado.motivo == "falha grave nos dados da Câmara: so_placar"


def test_caso_sem_regra_vira_noticia_propria_e_avisa(banco):
    proposicao = banco.session.get(Proposicao, 3)
    proposicao.cod_situacao, proposicao.situacao = 9999, "Situação nova"
    banco.session.commit()
    assert _classe(banco, "situacao", 3) == ("propria", None)
    assert banco.session.scalar(banco.select(LogSistema).filter_by(acao="classificacao_desconhecida"))


# ======================================================
# BOLETINS
# ======================================================
def test_quatro_boletins_um_por_tipo_de_fato(banco):
    resultado = boletim.gerar_boletins(DIA)
    assert [(categoria, novo) for categoria, _, novo in resultado] == [
        ("plenario", True),
        ("comissoes", True),
        ("andamento", True),
        ("novas", True),
    ]
    noticias = {n.titulo: n for n in banco.session.scalars(banco.select(Noticia))}
    assert set(noticias) == {
        "Boletim de 16/11/2026: votações de procedimento no Plenário",
        "Boletim de 16/11/2026: votações nas comissões",
        "Boletim de 16/11/2026: andamento das proposições",
        "Boletim de 16/11/2026: proposições novas",
    }
    for noticia in noticias.values():
        assert (noticia.tipo, noticia.status, noticia.cod_tema) == ("relatorio", "rascunho", 53)
        assert "Nenhum número, nome ou data foi escrito à mão." in noticia.corpo

    plenario = noticias["Boletim de 16/11/2026: votações de procedimento no Plenário"]
    # Só o requerimento: a votação do projeto tem notícia própria
    assert "Requerimento de Urgência" in plenario.corpo and "Projeto de Lei nº 1" not in plenario.corpo
    assert "https://www.camara.leg.br/propostas-legislativas/1" in plenario.corpo
    assert plenario.resumo.startswith("Em 16/11/2026, o Plenário da Câmara fez 1 votação de procedimento")
    assert [(f.tipo, f.ref_id) for f in plenario.fontes] == [("votacao", "1-2")]

    comissoes = noticias["Boletim de 16/11/2026: votações nas comissões"]
    assert "## Comissão de Constituição e Justiça (CCJC)\n\n- PL 2/2026" in comissoes.corpo
    assert "## Comissão de Finanças e Tributação (CFT)\n\n- PL 2/2026" in comissoes.corpo
    # A explicacao da votacao simbolica vem uma vez so
    assert comissoes.corpo.startswith("Votação simbólica: a Câmara não registra o voto de cada deputado")
    assert comissoes.corpo.count("Votação simbólica.") == 2
    assert comissoes.resumo == "Em 16/11/2026, as comissões da Câmara registraram 2 votações em 2 comissões."

    andamento = noticias["Boletim de 16/11/2026: andamento das proposições"]
    assert f"## Aguardando Parecer\n\n{SITUACOES[915]}\n\n- PL 3/2026" in andamento.corpo
    assert "PL 4/2026" not in andamento.corpo  # marco: notícia própria

    novas = noticias["Boletim de 16/11/2026: proposições novas"]
    assert "## PDL\n\n- PDL 5/2026, de Fulana: Susta os efeitos do decreto" in novas.corpo
    assert "PL 6/2026" not in novas.corpo

    geracao = banco.session.scalar(banco.select(GeracaoIA).filter_by(noticia_id=plenario.id))
    assert geracao.modelo_geracao == "boletim-v1" and geracao.modelo_embedding == "nenhum (relatorio sem busca)"
    assert prioridade.calcular([plenario])[plenario.id].motivos == ["boletim do dia"]


def test_o_mesmo_dia_nao_gera_dois_boletins_e_simular_nao_grava(banco):
    assert [novo for _, _, novo in boletim.gerar_boletins(DIA, simular=True)] == [None] * 4
    assert banco.session.scalar(banco.select(banco.func.count()).select_from(Noticia)) == 0
    boletim.gerar_boletins(DIA)
    assert [novo for _, _, novo in boletim.gerar_boletins(DIA)] == [False] * 4
    assert banco.session.scalar(banco.select(banco.func.count()).select_from(Noticia)) == 4


def test_dia_sem_fato_pequeno_nao_gera_boletim(banco):
    assert boletim.gerar_boletins(date(2026, 11, 10)) == []
    assert boletim.em_texto(date(2026, 11, 10), []) == "10/11/2026: nenhum fato pequeno, nenhum boletim"


def test_padrao_e_ontem(banco):
    assert len(boletim.gerar_boletins(hoje=date(2026, 11, 17), simular=True)) == 4


def test_comando_boletins(app, banco):
    resultado = app.test_cli_runner().invoke(args=["ia", "boletins", "--dia", "2026-11-16", "--simular"])
    assert resultado.exit_code == 0, resultado.output
    assert "Boletim de 16/11/2026: votações nas comissões" in resultado.output
    assert "Simulação: nada foi gravado." in resultado.output
    resultado = app.test_cli_runner().invoke(args=["ia", "boletins", "--dia", "2026-11-16"])
    assert resultado.exit_code == 0 and "comissoes=novo" in resultado.output


def test_tema_do_boletim_precisa_existir(banco):
    banco.session.delete(banco.session.get(Tema, 53))
    banco.session.commit()
    resultado = boletim.gerar_boletins(DIA)
    assert {geracao.status for _, geracao, _ in resultado} == {"erro"}
