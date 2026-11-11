"""Item 4 da 22.10: os fatos novos viram rascunho sozinhos, sem duplicar."""

from datetime import date, datetime

import pytest

import fabricas
from desperta.ia.models import GeracaoIA, TrechoRAG
from desperta.noticias.models import Noticia
from desperta.proposicoes.models import ProposicaoTema
from desperta.sistema.models import LogSistema
from desperta.votacoes.models import VotacaoProposicao

HOJE = date(2024, 5, 16)
SINCRONIZADO = datetime(2024, 5, 16, 3, 0)


@pytest.fixture
def banco(app, db):
    """
    Janela de 3 dias antes de 16/05/2024 (desde 13/05):
    - PL 1234 (2310837) apresentado em 14/05, com tema: proposicao nova e votacao 2310837-8;
    - PEC 2 apresentada em 2023 e com situacao nova em 15/05: mudanca de situacao;
    - PL 3 apresentado em 15/05 sem tema: pulado;
    - PL 4 apresentado em 15/05 ainda pendente na coleta, com a votacao 4-1 tambem pendente;
    - REQ 5 apresentado em 15/05 (tipo nao acompanhado) e a votacao 5-1 so sobre ele: fora;
    - PL 6 de 2020, sem mudanca: fora.
    """
    pytest.importorskip("sqlite_vec")
    db.session.add_all(
        [
            fabricas.orgao(),
            fabricas.tema(),
            fabricas.proposicao(ementa="Institui o Dia Nacional da Merenda.", filhos_sincronizados_em=SINCRONIZADO),
            fabricas.proposicao(
                id=2,
                sigla_tipo="PEC",
                cod_tipo=136,
                descricao_tipo="Proposta de Emenda à Constituição",
                numero=2,
                ano=2023,
                ementa="Altera o art. 1º da Constituição Federal.",
                data_apresentacao=datetime(2023, 1, 10, 10, 0),
                data_status=datetime(2024, 5, 15, 11, 0),
                situacao="Pronta para Pauta",
                filhos_sincronizados_em=SINCRONIZADO,
            ),
            fabricas.proposicao(
                id=3, numero=3, data_apresentacao=datetime(2024, 5, 15, 9, 0), filhos_sincronizados_em=SINCRONIZADO
            ),
            fabricas.proposicao(id=4, numero=4, data_apresentacao=datetime(2024, 5, 15, 9, 0)),
            fabricas.proposicao(
                id=5,
                sigla_tipo="REQ",
                cod_tipo=1,
                descricao_tipo="Requerimento",
                numero=5,
                data_apresentacao=datetime(2024, 5, 15, 9, 0),
                filhos_sincronizados_em=SINCRONIZADO,
            ),
            fabricas.proposicao(
                id=6,
                numero=6,
                ano=2020,
                data_apresentacao=datetime(2020, 3, 1, 9, 0),
                data_status=datetime(2020, 3, 2, 9, 0),
                filhos_sincronizados_em=SINCRONIZADO,
            ),
            fabricas.votacao(
                descricao="Aprovado o Projeto de Lei nº 1.234.", aprovacao=True, filhos_sincronizados_em=SINCRONIZADO
            ),
            fabricas.votacao(id="4-1", data=date(2024, 5, 15), proposicao_id=4),
            fabricas.votacao(id="5-1", data=date(2024, 5, 15), proposicao_id=5, filhos_sincronizados_em=SINCRONIZADO),
        ]
    )
    db.session.flush()
    db.session.add_all(
        [
            ProposicaoTema(proposicao_id=2310837, cod_tema=46, relevancia=1),
            ProposicaoTema(proposicao_id=2, cod_tema=46, relevancia=1),
            VotacaoProposicao(votacao_id="2310837-8", proposicao_id=2310837),
            TrechoRAG(
                tipo="proposicao",
                ref_id="2310837",
                parte=1,
                texto="PL 1234/2024. Institui o Dia Nacional da Merenda.",
                tokens=8,
                embedding=bytes(3072),
                modelo_embedding="m",
                hash_texto="a" * 64,
            ),
        ]
    )
    db.session.commit()
    return db


def _rodar(**opcoes):
    from desperta.ia.automatico import gerar_novos

    return gerar_novos(None, dias=3, hoje=HOJE, **opcoes)


def _contar(banco, modelo):
    return banco.session.scalar(banco.select(banco.func.count()).select_from(modelo))


def test_escolhe_os_fatos_da_janela_com_votacoes_primeiro(banco):
    from desperta.ia.automatico import fatos_da_janela

    assert fatos_da_janela(date(2024, 5, 13)) == [
        ("votacao", "2310837-8", False),
        ("votacao", "4-1", True),
        ("situacao", 2, False),
        ("nova", 2310837, False),
        ("nova", 3, False),
        ("nova", 4, True),
    ]


def test_gera_um_rascunho_por_fato_e_conta_o_que_pulou(banco):
    resumo = _rodar()
    assert dict(resumo.gerados) == {"votacao": 1, "situacao": 1, "nova": 1}
    assert (resumo.candidatos, resumo.sem_tema, resumo.pendentes, resumo.erros) == (6, 1, 2, 0)
    noticias = banco.session.scalars(banco.select(Noticia)).all()
    assert len(noticias) == 3 and {n.status for n in noticias} == {"rascunho"}
    log = banco.session.scalar(banco.select(LogSistema).filter_by(acao="gerar_novos"))
    assert log.nivel == "info" and "sem_tema=1" in log.descricao and "pendentes_na_coleta=2" in log.descricao


def test_rodar_de_novo_nao_duplica_nem_refaz_a_rejeitada(banco):
    _rodar()
    banco.session.scalars(banco.select(Noticia)).first().status = "rejeitada"
    banco.session.commit()
    resumo = _rodar()
    assert sum(resumo.gerados.values()) == 0 and resumo.ja_feitos == 3
    assert _contar(banco, Noticia) == 3


def test_mudanca_de_situacao_depois_gera_de_novo(banco):
    _rodar()
    banco.session.get(fabricas.Proposicao, 2).data_status = datetime(2024, 5, 16, 10, 0)
    banco.session.commit()
    assert dict(_rodar().gerados) == {"situacao": 1}


def test_pendente_entra_quando_a_coleta_completa(banco):
    _rodar()
    banco.session.add(ProposicaoTema(proposicao_id=4, cod_tema=46, relevancia=1))
    banco.session.get(fabricas.Proposicao, 4).filhos_sincronizados_em = SINCRONIZADO
    banco.session.get(fabricas.Votacao, "4-1").filhos_sincronizados_em = SINCRONIZADO
    banco.session.commit()
    assert dict(_rodar().gerados) == {"votacao": 1, "nova": 1}


def test_simular_nao_grava_nada(banco):
    resumo = _rodar(simular=True)
    assert resumo.simulados == [("votacao", "2310837-8"), ("situacao", 2), ("nova", 2310837)]
    assert _contar(banco, Noticia) == 0 and _contar(banco, GeracaoIA) == 0 and _contar(banco, LogSistema) == 0


def test_limite_para_e_conta_o_que_ficou(banco):
    resumo = _rodar(limite=1)
    assert dict(resumo.gerados) == {"votacao": 1} and resumo.nao_feitos_pelo_limite == 2
    assert dict(_rodar().gerados) == {"situacao": 1, "nova": 1}


def test_erro_nao_e_repetido_a_cada_hora_mas_pode_ser_refeito(app, banco):
    app.config["GERADOR"] = "roberta"
    assert _rodar().erros == 3
    log = banco.session.scalar(banco.select(LogSistema).filter_by(acao="gerar_novos"))
    assert log.nivel == "aviso"
    segunda = _rodar()
    assert (segunda.erros, segunda.ja_feitos) == (0, 3)
    app.config["GERADOR"] = "frases"
    assert sum(_rodar(refazer_erros=True).gerados.values()) == 3
    assert _contar(banco, Noticia) == 3


def test_comando_simula_e_gera_so_com_palavras_sem_o_pendrive(app, banco, tmp_path):
    app.config["ROBERTA_DIR"] = str(tmp_path / "pendrive")
    dias = str((date.today() - date(2024, 5, 13)).days)
    executor = app.test_cli_runner()
    simulado = executor.invoke(args=["ia", "gerar-novos", "--simular", "--dias", dias])
    assert simulado.exit_code == 0, simulado.output
    assert "situacao 2" in simulado.output and "nada foi gravado" in simulado.output
    assert _contar(banco, Noticia) == 0
    gerado = executor.invoke(args=["ia", "gerar-novos", "--dias", dias])
    assert gerado.exit_code == 0, gerado.output
    assert "Usando só a busca por palavras" in gerado.output and "nova=1" in gerado.output
    assert _contar(banco, Noticia) == 3
