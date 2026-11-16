"""RF07 (decisao 25.5): relatorio da semana, montado so com os dados do banco."""

from collections import Counter
from datetime import date, datetime

import pytest

import fabricas
from desperta.ia import relatorio
from desperta.ia.models import GeracaoIA
from desperta.noticias.models import Noticia
from desperta.noticias.services import listar_para_revisao
from desperta.proposicoes.models import ProposicaoTema
from desperta.sistema.models import LogSistema

HOJE = date(2026, 11, 15)
SINCRONIZADO = datetime(2026, 11, 14, 3, 0)
TITULO = "A semana na Câmara: 8 a 14 de novembro de 2026"


def _proposicao(id, **campos):
    antiga = datetime(2025, 3, 1, 9, 0)
    padrao = {"numero": id, "ano": 2025, "data_apresentacao": antiga, "data_status": antiga}
    return fabricas.proposicao(id=id, **{**padrao, **campos})


def _votacao(id, dia, proposicao_id, descricao, **campos):
    return fabricas.votacao(
        id=id,
        data=date(2026, 11, dia),
        data_hora_registro=datetime(2026, 11, dia, 15, 0),
        proposicao_id=proposicao_id,
        descricao=descricao,
        filhos_sincronizados_em=SINCRONIZADO,
        **campos,
    )


@pytest.fixture
def banco(db):
    """
    Semana de 08 a 14/11/2026:
    - PL 10/2026, novo, com tema, aprovado no Plenario em 11/11;
    - PL 11/2025, rejeitado no Plenario em 12/11 e com um requerimento aprovado em 13/11;
    - PL 12/2024 passou de "Pronta para Pauta" para "Aguardando Sanção" em 13/11 (avanco);
    - PL 13/2024 teve um passo novo em 12/11, mas ja estava "Pronta para Pauta" (nao e avanco);
    - PL 14/2024 mudou para "Aguardando Parecer", que nao e situacao de avanco;
    - PEC 15/2026, nova e ainda sem tema; REQ 16/2026, novo, de tipo nao acompanhado;
    - uma votacao em comissao em 12/11 e uma votacao do Plenario em 07/11, fora da semana.
    """
    db.session.add_all(
        [
            fabricas.orgao(),
            fabricas.orgao(id=2001, sigla="CE", nome="Comissao de Educacao", apelido="Educacao"),
            fabricas.tema(),
            fabricas.tema(cod_tema=53, nome="Processo Legislativo e Atuação Parlamentar", icone="account_balance"),
            _proposicao(
                10, ano=2026, ementa="Institui o Dia Nacional da Merenda.", data_apresentacao=datetime(2026, 11, 10)
            ),
            _proposicao(11, ementa="Cria o Programa de Transporte Escolar."),
            _proposicao(
                12,
                ano=2024,
                ementa="Institui a Semana da Leitura.",
                cod_situacao=1150,
                situacao="Aguardando Sanção",
                data_status=datetime(2026, 11, 13, 10, 0),
            ),
            _proposicao(
                13, ano=2024, cod_situacao=924, situacao="Pronta para Pauta", data_status=datetime(2026, 11, 12, 9, 0)
            ),
            _proposicao(
                14, ano=2024, cod_situacao=915, situacao="Aguardando Parecer", data_status=datetime(2026, 11, 12, 9, 0)
            ),
            _proposicao(
                15,
                sigla_tipo="PEC",
                descricao_tipo="Proposta de Emenda à Constituição",
                ano=2026,
                data_apresentacao=datetime(2026, 11, 9, 9, 0),
            ),
            _proposicao(
                16, sigla_tipo="REQ", descricao_tipo="Requerimento", ano=2026, data_apresentacao=datetime(2026, 11, 9)
            ),
            fabricas.coleta(finalizado_em=datetime(2026, 11, 15, 3, 5)),
        ]
    )
    db.session.flush()
    db.session.add_all(
        [
            ProposicaoTema(proposicao_id=10, cod_tema=46, relevancia=0),
            _votacao("10-1", 11, 10, "Aprovado o Projeto de Lei nº 10, de 2026.", aprovacao=True),
            _votacao("11-1", 12, 11, "Rejeitado o Projeto de Lei nº 11, de 2025.", aprovacao=False),
            _votacao("11-2", 13, 11, "Aprovado o Requerimento de Urgência (Art. 155 do RICD).", aprovacao=True),
            _votacao("10-9", 12, 10, "Aprovado o Parecer.", aprovacao=True, orgao_id=2001, sigla_orgao="CE"),
            _votacao("11-0", 7, 11, "Aprovado o Projeto de Lei nº 11, de 2025.", aprovacao=True),
            fabricas.tramitacao(
                proposicao_id=12,
                sequencia=1,
                data_hora=datetime(2026, 11, 5, 9, 0),
                cod_situacao=924,
                situacao="Pronta para Pauta",
            ),
            fabricas.tramitacao(
                proposicao_id=13,
                sequencia=1,
                data_hora=datetime(2026, 11, 5, 9, 0),
                cod_situacao=924,
                situacao="Pronta para Pauta",
            ),
            fabricas.tramitacao(
                proposicao_id=14,
                sequencia=1,
                data_hora=datetime(2026, 11, 5, 9, 0),
                cod_situacao=924,
                situacao="Pronta para Pauta",
            ),
        ]
    )
    db.session.commit()
    return db


def _contar(banco, modelo):
    return banco.session.scalar(banco.select(banco.func.count()).select_from(modelo))


# ======================================================
# PERIODO
# ======================================================
def test_semana_passada_sao_os_sete_dias_ate_ontem():
    assert relatorio.semana_passada(HOJE) == (date(2026, 11, 8), date(2026, 11, 14))


@pytest.mark.parametrize(
    "inicio,fim,texto",
    [
        (date(2026, 11, 8), date(2026, 11, 14), "8 a 14 de novembro de 2026"),
        (date(2026, 11, 29), date(2026, 12, 5), "29 de novembro a 5 de dezembro de 2026"),
        (date(2026, 12, 27), date(2027, 1, 2), "27 de dezembro de 2026 a 2 de janeiro de 2027"),
    ],
)
def test_periodo_em_texto(inicio, fim, texto):
    assert relatorio.periodo_em_texto(inicio, fim) == texto


# ======================================================
# LEITURA E TEXTO
# ======================================================
def test_le_so_o_que_aconteceu_na_semana(banco):
    dados, titulo, resumo, corpo = relatorio.previa(hoje=HOJE)
    assert (dados.votacoes_no_plenario, dados.votacoes_em_comissoes) == (3, 1)
    assert [item.votacao_id for item in dados.de_projetos] == ["10-1", "11-1"]
    assert dados.novas == Counter({"PL": 1, "PEC": 1})
    assert (dados.novas_com_tema, dados.temas) == (1, [("Educacao", 1)])
    # Decisao 25.1: passo novo com a mesma situacao nao e avanco
    assert {s: [a.identificacao for a in grupo] for s, grupo in dados.avancos.items()} == {
        "Aguardando Sanção": ["PL 12/2024"]
    }
    assert titulo == TITULO
    assert resumo == (
        "De 8 a 14 de novembro de 2026, a Câmara fez 3 votações no Plenário e 1 votação em comissões. "
        "No Plenário, 1 projeto foi aprovado e 1 projeto foi rejeitado. "
        "1 proposição mudou para uma situação de avanço, como pauta do Plenário, Senado ou sanção. "
        "2 proposições novas foram apresentadas."
    )
    assert _contar(banco, Noticia) == 0 and _contar(banco, GeracaoIA) == 0


def test_corpo_conta_votacoes_avancos_temas_e_como_foi_feito(banco):
    corpo = relatorio.previa(hoje=HOJE)[3]
    paragrafos = corpo.split("\n\n")
    assert paragrafos[0] == (
        "De 8 a 14 de novembro de 2026, a Câmara dos Deputados registrou 3 votações no Plenário e "
        "1 votação em comissões. Foram apresentadas 2 proposições dos tipos que o portal acompanha: 1 PEC e 1 PL."
    )
    assert paragrafos[1].split("\n") == [
        "Votações de projetos no Plenário (2):",
        "- PL 10/2026, em 11/11/2026: Aprovado o Projeto de Lei nº 10, de 2026. Votação simbólica: a Câmara não "
        "registra o voto de cada deputado. Ementa: Institui o Dia Nacional da Merenda.",
        "- PL 11/2025, em 12/11/2026: Rejeitado o Projeto de Lei nº 11, de 2025. Votação simbólica: a Câmara não "
        "registra o voto de cada deputado. Ementa: Cria o Programa de Transporte Escolar.",
        "A outra votação do Plenário foi de requerimentos, redação final e outros procedimentos.",
    ]
    assert paragrafos[2].split("\n") == [
        "O que avançou (1 proposição):",
        'Situação "Aguardando Sanção" (1):',
        "- PL 12/2024, em 13/11/2026: Institui a Semana da Leitura.",
    ]
    assert paragrafos[3] == (
        "A Câmara já deu tema a 1 das 2 proposições novas. Temas mais comuns entre elas: Educacao (1)."
    )
    # A coleta terminou as 03h05 UTC, que sao 00h05 em Brasilia
    assert paragrafos[4].startswith(
        "Como este relatório foi feito: montado automaticamente com os dados que a Câmara publicou até "
        "15/11/2026, às 00h05"
    )
    assert len(paragrafos) == 5


def test_grupo_grande_mostra_os_primeiros_e_conta_o_resto(banco, monkeypatch):
    monkeypatch.setattr(relatorio, "ITENS_POR_GRUPO", 1)
    pl13 = banco.session.get(fabricas.Proposicao, 13)
    pl13.cod_situacao, pl13.situacao = 1150, "Aguardando Sanção"
    banco.session.commit()
    dados, _, _, corpo = relatorio.previa(hoje=HOJE)
    assert 'Situação "Aguardando Sanção" (2):' in corpo
    assert "- e mais 1 proposição nessa situação." in corpo
    # So as proposicoes citadas pelo nome viram fonte
    assert relatorio._fontes(dados) == [("votacao", "10-1"), ("votacao", "11-1"), ("proposicao", "12")]


# ======================================================
# GERACAO
# ======================================================
def test_gera_um_rascunho_do_tipo_relatorio_com_as_fontes(banco):
    geracao, novo = relatorio.gerar_relatorio_semanal(hoje=HOJE)
    assert novo is True
    noticia = geracao.noticia
    assert (noticia.tipo, noticia.status, noticia.origem, noticia.cod_tema) == ("relatorio", "rascunho", "ia", 53)
    assert noticia.titulo == TITULO and noticia.slug == "a-semana-na-camara-8-a-14-de-novembro-de-2026"
    assert [(f.tipo, f.ref_id, f.ordem) for f in sorted(noticia.fontes, key=lambda f: f.ordem)] == [
        ("votacao", "10-1", 1),
        ("votacao", "11-1", 2),
        ("proposicao", "12", 3),
    ]
    assert (geracao.status, geracao.modelo_geracao, geracao.versao_prompt) == (
        "ok",
        "relatorio-semanal-v1",
        "relatorio-semanal-v1",
    )
    assert geracao.modelo_embedding == "nenhum (relatorio sem busca)" and geracao.top_k == 0
    assert geracao.entrada == '{"caso": "relatorio_semanal", "fim": "2026-11-14", "inicio": "2026-11-08"}'
    log = banco.session.scalar(banco.select(LogSistema).filter_by(acao="relatorio_semanal"))
    assert (log.nivel, log.entidade, log.entidade_id) == ("info", "noticia", str(noticia.id))
    # A fila de revisao acha o relatorio pelo caso
    itens, total = listar_para_revisao(caso="relatorio_semanal")
    assert total == 1 and itens[0].id == noticia.id


def test_a_mesma_semana_nao_gera_dois_relatorios(banco):
    primeira, _ = relatorio.gerar_relatorio_semanal(hoje=HOJE)
    segunda, novo = relatorio.gerar_relatorio_semanal(hoje=HOJE)
    assert novo is False and segunda.id == primeira.id
    assert _contar(banco, Noticia) == 1
    assert relatorio.em_texto(segunda, novo) == (
        "a semana ja tem o rascunho a-semana-na-camara-8-a-14-de-novembro-de-2026"
    )


def test_relatorio_rejeitado_pode_ser_refeito(banco):
    primeira, _ = relatorio.gerar_relatorio_semanal(hoje=HOJE)
    primeira.noticia.status = "rejeitada"
    banco.session.commit()
    segunda, novo = relatorio.gerar_relatorio_semanal(hoje=HOJE)
    assert novo is True and segunda.noticia.slug == "a-semana-na-camara-8-a-14-de-novembro-de-2026-2"


def test_semana_sem_movimento_nao_gera_nada(banco):
    geracao, novo = relatorio.gerar_relatorio_semanal(hoje=date(2030, 1, 10))
    assert (geracao, novo) == (None, False)
    assert _contar(banco, Noticia) == 0 and _contar(banco, GeracaoIA) == 0
    log = banco.session.scalar(banco.select(LogSistema).filter_by(acao="relatorio_semanal"))
    assert "sem movimento" in log.descricao
    assert relatorio.em_texto(geracao, novo) == "semana sem movimento, nada foi gerado"


def test_sem_o_tema_do_relatorio_a_geracao_fica_registrada_como_erro(banco):
    banco.session.delete(banco.session.get(fabricas.Tema, 53))
    banco.session.commit()
    geracao, novo = relatorio.gerar_relatorio_semanal(hoje=HOJE)
    assert novo is False and geracao.status == "erro" and geracao.noticia_id is None
    assert "tema 53" in geracao.erro and _contar(banco, Noticia) == 0
    assert geracao.modelo_embedding == "nenhum (relatorio sem busca)"
    assert relatorio.em_texto(geracao, novo).startswith("erro na geracao")


def test_semana_so_com_requerimentos_no_plenario(banco):
    for votacao_id in ("10-1", "11-1"):
        banco.session.delete(banco.session.get(fabricas.Votacao, votacao_id))
    banco.session.commit()
    _, _, resumo, corpo = relatorio.previa(hoje=HOJE)
    assert "No Plenário," not in resumo
    assert (
        "Votações de projetos no Plenário: nenhuma. A votação do Plenário foi de requerimentos, "
        "redação final e outros procedimentos." in corpo
    )


# ======================================================
# COMANDO
# ======================================================
def test_comando_simula_sem_gravar_e_depois_grava(app, banco):
    executor = app.test_cli_runner()
    simulado = executor.invoke(args=["ia", "relatorio-semanal", "--ate", "2026-11-14", "--simular"])
    assert simulado.exit_code == 0, simulado.output
    assert TITULO in simulado.output and "nada foi gravado" in simulado.output
    assert _contar(banco, Noticia) == 0
    gravado = executor.invoke(args=["ia", "relatorio-semanal", "--ate", "2026-11-14"])
    assert gravado.exit_code == 0, gravado.output
    assert "rascunho a-semana-na-camara-8-a-14-de-novembro-de-2026" in gravado.output
    assert _contar(banco, Noticia) == 1
