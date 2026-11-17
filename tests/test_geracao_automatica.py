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
    - PEC 2 apresentada em 2023; em 15/05 a situacao passou de "Aguardando Parecer" (915)
      para "Pronta para Pauta" (924): mudanca de situacao;
    - PL 3 apresentado em 15/05 sem tema: vira noticia no tema especial (decisao 25.6);
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
                cod_situacao=924,
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
            fabricas.tramitacao(
                proposicao_id=2,
                sequencia=1,
                data_hora=datetime(2024, 5, 10, 9, 0),
                cod_situacao=915,
                situacao="Aguardando Parecer",
            ),
            fabricas.tramitacao(
                proposicao_id=2,
                sequencia=2,
                data_hora=datetime(2024, 5, 15, 11, 0),
                cod_situacao=924,
                situacao="Pronta para Pauta",
            ),
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
    assert dict(resumo.gerados) == {"votacao": 1, "situacao": 1, "nova": 2}
    assert (resumo.candidatos, resumo.sem_tema, resumo.pendentes, resumo.erros) == (6, 1, 2, 0)
    noticias = banco.session.scalars(banco.select(Noticia)).all()
    # 25.16: a votacao e a proposicao nova do PL 1234 sao a mesma noticia viva (4 fatos, 3 noticias)
    assert len(noticias) == 3 and {n.status for n in noticias} == {"rascunho"}
    viva = banco.session.scalars(banco.select(Noticia).order_by(Noticia.id)).first()
    assert viva.titulo.startswith("Câmara aprova PL 1234/2024")
    assert "## Atualizações\n\n### 14/05/2024: PL 1234/2024 institui o Dia Nacional da Merenda" in viva.corpo
    assert _contar(banco, GeracaoIA) == 4
    log = banco.session.scalar(banco.select(LogSistema).filter_by(acao="gerar_novos"))
    assert log.nivel == "info" and "sem_tema_da_camara=1" in log.descricao and "pendentes_na_coleta=2" in log.descricao


def test_rodar_de_novo_nao_duplica_nem_refaz_a_rejeitada(banco):
    _rodar()
    banco.session.scalars(banco.select(Noticia)).first().status = "rejeitada"
    banco.session.commit()
    resumo = _rodar()
    assert sum(resumo.gerados.values()) == 0 and resumo.ja_feitos == 4
    assert _contar(banco, Noticia) == 3


def test_situacao_que_muda_de_verdade_gera_de_novo(banco):
    _rodar()
    pec = banco.session.get(fabricas.Proposicao, 2)
    pec.data_status, pec.cod_situacao, pec.situacao = datetime(2024, 5, 16, 10, 0), 923, "Aguardando Deliberação"
    banco.session.commit()
    assert dict(_rodar().gerados) == {"situacao": 1}


def test_so_a_data_do_status_andar_nao_e_mudanca_de_situacao(banco):
    # Decisao 25.1: a Camara muda a data do status a cada passo; com a mesma situacao, nao ha rascunho novo
    _rodar()
    banco.session.get(fabricas.Proposicao, 2).data_status = datetime(2024, 5, 16, 10, 0)
    banco.session.add(
        fabricas.tramitacao(
            proposicao_id=2,
            sequencia=3,
            data_hora=datetime(2024, 5, 16, 10, 0),
            descricao="Abertura de Prazo",
            cod_situacao=924,
            situacao="Pronta para Pauta",
        )
    )
    banco.session.commit()
    resumo = _rodar()
    assert sum(resumo.gerados.values()) == 0
    assert (resumo.candidatos, resumo.ja_feitos) == (5, 3)
    assert _contar(banco, Noticia) == 3


def test_proposicao_sem_situacao_na_camara_nao_e_mudanca_de_situacao(banco):
    # Decisao 25.1: o passo novo anda a data, mas a Camara nao informou situacao nenhuma
    pec = banco.session.get(fabricas.Proposicao, 2)
    pec.cod_situacao, pec.situacao = None, None
    banco.session.commit()
    assert dict(_rodar().gerados) == {"votacao": 1, "nova": 2}


def test_situacao_mudou_compara_com_a_ultima_situacao_informada(banco):
    from desperta.proposicoes.services import situacao_mudou

    dia = datetime(2024, 5, 15, 11, 0)
    assert situacao_mudou(2, 924, dia) is True  # antes era 915
    assert situacao_mudou(2, 915, dia) is False  # a mesma de antes
    assert situacao_mudou(2, None, dia) is False  # a Camara nao informou
    assert situacao_mudou(2, 924, None) is False  # sem data do status
    # Sem nenhuma tramitacao anterior com situacao: e a primeira que a Camara informa
    assert situacao_mudou(6, 924, datetime(2020, 3, 2, 9, 0)) is True
    # Passo anterior sem situacao nao conta como "situacao de antes"
    banco.session.add(fabricas.tramitacao(proposicao_id=2, sequencia=9, data_hora=datetime(2024, 5, 14, 9, 0)))
    banco.session.commit()
    assert situacao_mudou(2, 915, dia) is False


def test_gerar_novos_refaz_o_indice_das_raizes_incompleto(banco):
    # Decisao 25.3: noticia gravada por uma versao do codigo que nao mantinha o indice das raizes
    _rodar()
    banco.session.execute(banco.text("DELETE FROM noticia_fts_raiz"))
    banco.session.commit()
    _rodar()
    assert banco.session.execute(banco.text("SELECT COUNT(*) FROM noticia_fts_raiz_docsize")).scalar() == 3
    avisos = banco.select(banco.func.count()).select_from(LogSistema).filter_by(acao="busca_raiz_refeita")
    assert banco.session.scalar(avisos) == 1
    # Com o indice completo, a execucao seguinte nao refaz nem avisa de novo
    _rodar()
    assert banco.session.scalar(avisos) == 1


def test_pendente_entra_quando_a_coleta_completa(banco):
    _rodar()
    banco.session.add(ProposicaoTema(proposicao_id=4, cod_tema=46, relevancia=1))
    banco.session.get(fabricas.Proposicao, 4).filhos_sincronizados_em = SINCRONIZADO
    banco.session.get(fabricas.Votacao, "4-1").filhos_sincronizados_em = SINCRONIZADO
    banco.session.commit()
    # 25.17: a votacao 4-1 e de procedimento no Plenario (fato pequeno) e o PL 4 ainda nao tinha
    # noticia viva: fica so para o boletim; o PL novo vira noticia propria
    segunda = _rodar()
    assert dict(segunda.gerados) == {"nova": 1} and segunda.para_o_boletim == 1
    # Na execucao seguinte o PL 4 ja tem noticia viva: a votacao entra nela tambem (escolha do Lucas)
    assert dict(_rodar().gerados) == {"votacao": 1}


def test_simular_nao_grava_nada(banco):
    resumo = _rodar(simular=True)
    assert resumo.simulados == [("votacao", "2310837-8"), ("situacao", 2), ("nova", 2310837), ("nova", 3)]
    assert resumo.sem_tema == 1
    assert _contar(banco, Noticia) == 0 and _contar(banco, GeracaoIA) == 0 and _contar(banco, LogSistema) == 0


def test_limite_para_e_conta_o_que_ficou(banco):
    resumo = _rodar(limite=1)
    assert dict(resumo.gerados) == {"votacao": 1} and resumo.nao_feitos_pelo_limite == 3
    assert dict(_rodar().gerados) == {"situacao": 1, "nova": 2}


def test_erro_nao_e_repetido_a_cada_hora_mas_pode_ser_refeito(app, banco):
    app.config["GERADOR"] = "roberta"
    assert _rodar().erros == 4
    log = banco.session.scalar(banco.select(LogSistema).filter_by(acao="gerar_novos"))
    assert log.nivel == "aviso"
    segunda = _rodar()
    assert (segunda.erros, segunda.ja_feitos) == (0, 4)
    app.config["GERADOR"] = "frases"
    assert sum(_rodar(refazer_erros=True).gerados.values()) == 4
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
    assert "Usando só a busca por palavras" in gerado.output and "nova=2" in gerado.output
    assert _contar(banco, Noticia) == 3


# ======================================================
# DECISAO 25.6: PROPOSICAO SEM TEMA DA CAMARA
# ======================================================
def test_proposicao_sem_tema_vira_noticia_no_tema_especial(banco):
    from desperta.proposicoes.models import TEMA_SEM_CLASSIFICACAO, TEMA_SEM_CLASSIFICACAO_NOME

    _rodar()
    noticia = banco.session.scalar(
        banco.select(Noticia).join(fabricas.NoticiaFonte).where(fabricas.NoticiaFonte.ref_id == "3")
    )
    assert noticia.cod_tema == TEMA_SEM_CLASSIFICACAO
    assert noticia.tema.nome == TEMA_SEM_CLASSIFICACAO_NOME and noticia.tema.icone == "help"
    # Decisao 25.13: a falta de tema e uma lacuna, na secao propria, fora do paragrafo principal
    assert (
        "A Câmara ainda não informou o tema desta proposição."
        in noticia.corpo.split("## O que a Câmara não informou")[1]
    )
    assert "informou o tema" not in noticia.resumo
    # O tema especial e criado uma vez so
    assert banco.session.scalar(banco.select(banco.func.count()).select_from(fabricas.Tema)) == 2


def test_quando_a_camara_informa_o_tema_a_noticia_muda_de_tema(banco):
    from desperta.ia.automatico import atualizar_temas
    from desperta.proposicoes.models import TEMA_SEM_CLASSIFICACAO

    _rodar()
    fonte = fabricas.NoticiaFonte
    noticia = banco.session.scalar(banco.select(Noticia).join(fonte).where(fonte.ref_id == "3"))
    texto = (noticia.titulo, noticia.resumo, noticia.corpo)
    assert atualizar_temas() == 0
    banco.session.add(ProposicaoTema(proposicao_id=3, cod_tema=46, relevancia=0))
    banco.session.commit()
    assert _rodar().temas_atualizados == 1
    banco.session.refresh(noticia)
    assert noticia.cod_tema == 46 and (noticia.titulo, noticia.resumo, noticia.corpo) == texto
    log = banco.session.scalar(banco.select(LogSistema).filter_by(acao="tema_atualizado"))
    assert (log.entidade, log.entidade_id) == ("noticia", str(noticia.id))
    assert (
        banco.session.scalar(
            banco.select(banco.func.count()).select_from(Noticia).filter_by(cod_tema=TEMA_SEM_CLASSIFICACAO)
        )
        == 0
    )


def test_noticia_arquivada_fica_no_tema_em_que_estava(banco):
    from desperta.ia.automatico import atualizar_temas
    from desperta.proposicoes.models import TEMA_SEM_CLASSIFICACAO

    _rodar()
    fonte = fabricas.NoticiaFonte
    noticia = banco.session.scalar(banco.select(Noticia).join(fonte).where(fonte.ref_id == "3"))
    noticia.status = "arquivada"
    banco.session.add(ProposicaoTema(proposicao_id=3, cod_tema=46, relevancia=0))
    banco.session.commit()
    assert atualizar_temas() == 0
    assert noticia.cod_tema == TEMA_SEM_CLASSIFICACAO
