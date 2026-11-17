from datetime import datetime

import pytest

import fabricas
from desperta.ia.geracao import gerar_noticia
from desperta.ia.gerador import GeradorFrases
from desperta.noticias.models import NoticiaFonte
from desperta.noticias.services import secoes_do_corpo
from desperta.proposicoes.models import Proposicao, ProposicaoTema
from desperta.proposicoes.situacoes import MARCOS, SITUACOES, explicar_situacao, situacao_conhecida
from desperta.sistema import lacunas
from desperta.sistema.models import LogSistema
from desperta.votacoes.models import Votacao

CONSULTA = datetime(2026, 11, 10, 6, 30)


# ======================================================
# SITUACAO EXPLICADA (25.13)
# ======================================================
def test_situacao_conhecida_mostra_o_nome_da_camara_e_a_explicacao():
    situacao = explicar_situacao(924, " Pronta para Pauta ")
    assert situacao == {
        "informada": True,
        "codigo": 924,
        "nome_da_camara": "Pronta para Pauta",
        "explicacao": SITUACOES[924],
    }


def test_situacao_fora_do_dicionario_mostra_so_o_nome_da_camara():
    situacao = explicar_situacao(9999, "Situação Nova da Câmara")
    assert situacao["nome_da_camara"] == "Situação Nova da Câmara" and situacao["explicacao"] is None
    assert situacao_conhecida(9999, "Situação Nova da Câmara") is False


@pytest.mark.parametrize("codigo,nome", [(None, None), (915, None), (915, "."), (1311, "<Não Definido>")])
def test_situacao_nao_informada(codigo, nome):
    assert explicar_situacao(codigo, nome)["informada"] is False
    # Nao informada nao e "desconhecida": nao gera aviso de dicionario
    assert situacao_conhecida(codigo, nome) is True


def test_todo_marco_tem_explicacao():
    assert MARCOS <= set(SITUACOES)


# ======================================================
# LACUNAS DA PROPOSICAO
# ======================================================
@pytest.fixture
def proposicao(db):
    db.session.add_all([fabricas.legislatura(), fabricas.orgao(), fabricas.tema()])
    db.session.flush()
    db.session.add(
        fabricas.proposicao(
            cod_situacao=915,
            situacao="Aguardando Parecer",
            sincronizado_em=CONSULTA,
            filhos_sincronizados_em=CONSULTA,
            data_apresentacao=datetime(2026, 11, 1, 10, 0),
        )
    )
    db.session.add(ProposicaoTema(proposicao_id=2310837, cod_tema=46, relevancia=0))
    db.session.commit()
    return db.session.get(Proposicao, 2310837)


def _codigos(achadas):
    return [lacuna.codigo for lacuna in achadas]


def test_proposicao_completa_nao_tem_lacuna(proposicao):
    assert lacunas.lacunas_da_proposicao(proposicao, agora=datetime(2026, 11, 10)) == []


def test_campos_vazios_com_o_valor_como_veio_e_a_data_da_consulta(db, proposicao):
    proposicao.regime = "."
    proposicao.apreciacao = ""
    proposicao.url_inteiro_teor = None
    proposicao.situacao = None
    proposicao.cod_situacao = None
    db.session.commit()
    achadas = lacunas.lacunas_da_proposicao(proposicao, agora=datetime(2026, 11, 10))
    assert _codigos(achadas) == ["sem_situacao", "sem_regime", "sem_apreciacao", "sem_inteiro_teor"]
    assert {lacuna.nivel for lacuna in achadas} == {lacunas.CAMPO_VAZIO}
    assert {lacuna.certeza for lacuna in achadas} == {lacunas.COMPROVADO}
    regime = achadas[1].provas[0]
    assert (regime.campo, regime.valor, regime.consultado_em) == (
        "statusProposicao.regime",
        '"." (só um ponto)',
        CONSULTA,
    )
    assert regime.endereco.endswith("/proposicoes/2310837")
    assert achadas[2].provas[0].valor == '"" (texto vazio)'
    assert achadas[3].provas[0].valor == "null (vazio)"


def test_sem_tema_e_atraso_e_sobe_de_nivel_depois_de_30_dias(db, proposicao):
    db.session.delete(db.session.get(ProposicaoTema, (2310837, 46)))
    db.session.commit()
    db.session.refresh(proposicao)
    [recente] = lacunas.lacunas_da_proposicao(proposicao, agora=datetime(2026, 11, 10))
    assert (recente.codigo, recente.nivel) == ("sem_tema", lacunas.ATRASO)
    assert recente.texto == "A Câmara ainda não informou o tema desta proposição."
    prova = recente.provas[0]
    assert prova.endereco.endswith("/proposicoes/2310837/temas") and prova.valor == "[] (lista vazia)"
    [antiga] = lacunas.lacunas_da_proposicao(proposicao, agora=datetime(2026, 12, 15))
    assert antiga.nivel == lacunas.OCULTACAO
    assert antiga.texto.endswith("Ela foi apresentada há 44 dias.")


def test_sem_tema_so_conta_depois_que_os_temas_foram_consultados(db, proposicao):
    db.session.delete(db.session.get(ProposicaoTema, (2310837, 46)))
    proposicao.filhos_sincronizados_em = None
    db.session.commit()
    db.session.refresh(proposicao)
    assert lacunas.lacunas_da_proposicao(proposicao) == []


def test_404_depois_da_ultima_consulta_e_contradicao(db, proposicao):
    db.session.add(
        LogSistema(
            data_hora=datetime(2026, 11, 11, 9, 0),
            nivel="aviso",
            modulo="coletor",
            acao="nao_encontrado_na_camara",
            descricao="404",
            entidade="proposicao",
            entidade_id="2310837",
        )
    )
    db.session.commit()
    [sumiu] = lacunas.lacunas_da_proposicao(proposicao, agora=datetime(2026, 11, 12))
    assert (sumiu.codigo, sumiu.nivel, sumiu.certeza) == ("registro_sumiu", lacunas.CONTRADICAO, lacunas.SEM_EXPLICACAO)
    assert sumiu.provas[0].valor == "404 (não encontrado)"
    assert sumiu.provas[0].consultado_em == datetime(2026, 11, 11, 9, 0)
    # A Camara voltou a mandar o registro depois do 404: a lacuna some
    proposicao.sincronizado_em = datetime(2026, 11, 12, 9, 0)
    db.session.commit()
    assert lacunas.lacunas_da_proposicao(proposicao, agora=datetime(2026, 11, 12)) == []


def test_o_leitor_nao_ve_o_nivel_e_toda_lacuna_manda_ao_site_da_camara(db, proposicao):
    proposicao.regime = "."
    db.session.commit()
    [lacuna] = lacunas.lacunas_da_proposicao(proposicao, agora=datetime(2026, 11, 10))
    publica = lacuna.publica()
    assert "nivel" not in publica and publica["falha_da_camara"] is True
    assert publica["mais_informacoes"] == {
        "texto": "Para mais informações, acesse o site da Câmara dos Deputados",
        "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2310837",
    }
    assert publica["provas"][0]["consultado_em"] == "2026-11-10T06:30:00Z"
    assert lacuna.interna()["nivel"] == lacunas.CAMPO_VAZIO and lacuna.interna()["nome_do_nivel"] == "campo vazio"


def test_prova_em_texto_no_horario_de_brasilia(proposicao):
    prova = lacunas.Prova("https://x/proposicoes/1", "statusProposicao.regime", '"."', CONSULTA)
    assert prova.em_texto() == (
        "Consulta aos dados abertos em 10/11/2026 às 03:30: "
        'https://x/proposicoes/1 (campo statusProposicao.regime: ".").'
    )


# ======================================================
# LACUNAS DA VOTACAO
# ======================================================
@pytest.fixture
def votacao(db):
    db.session.add_all([fabricas.legislatura(), fabricas.orgao()])
    db.session.flush()
    db.session.add_all([fabricas.deputado(), fabricas.deputado(id=2), fabricas.proposicao()])
    db.session.flush()
    db.session.add(
        fabricas.votacao(
            proposicao_id=2310837,
            aprovacao=True,
            descricao="Aprovado o Projeto. Sim: 1; Não: 1; Total: 2.",
            sincronizado_em=CONSULTA,
            filhos_sincronizados_em=CONSULTA,
        )
    )
    db.session.commit()
    return db.session.get(Votacao, "2310837-8")


def test_so_o_placar_e_ocultacao_sem_explicacao_e_nunca_diz_secreta(db, votacao):
    db.session.add_all([fabricas.voto(tipo_voto=None), fabricas.voto(deputado_id=2, tipo_voto=None)])
    db.session.commit()
    [lacuna] = lacunas.lacunas_da_votacao(votacao)
    assert (lacuna.codigo, lacuna.nivel, lacuna.certeza) == ("so_placar", lacunas.OCULTACAO, lacunas.SEM_EXPLICACAO)
    assert lacuna.texto == (
        "Os dados abertos da Câmara registram 2 presenças nesta votação, mas não informam o voto de cada "
        "deputado: trazem só o placar total (1 a favor e 1 contra). Os dados abertos não dizem por quê."
    )
    assert "secreta" not in lacuna.texto
    votos, placar = lacuna.provas
    assert votos.endereco.endswith("/votacoes/2310837-8/votos") and votos.valor == "null em 2 de 2 registros"
    assert placar.campo == "descricao" and "Sim: 1" in placar.valor
    assert lacuna.proposicao_id == 2310837


def test_simbolica_e_pratica_normal_e_nao_e_falha(votacao):
    [lacuna] = lacunas.lacunas_da_votacao(votacao)
    assert (lacuna.codigo, lacuna.nivel, lacuna.certeza) == ("simbolica", lacunas.PRATICA_NORMAL, lacunas.INDICADO)
    assert lacuna.falha_da_camara is False


def test_placar_que_nao_bate_com_os_votos_e_contradicao(db, votacao):
    db.session.add_all([fabricas.voto(), fabricas.voto(deputado_id=2, tipo_voto="Sim")])
    db.session.commit()
    [lacuna] = lacunas.lacunas_da_votacao(votacao)
    assert (lacuna.codigo, lacuna.nivel) == ("placar_diferente", lacunas.CONTRADICAO)
    assert "(1 a favor e 1 contra)" in lacuna.texto and "(2 a favor e 0 contra)" in lacuna.texto


def test_votos_parcialmente_sem_tipo_e_contradicao(db, votacao):
    db.session.add_all([fabricas.voto(), fabricas.voto(deputado_id=2, tipo_voto=None)])
    db.session.commit()
    [lacuna] = lacunas.lacunas_da_votacao(votacao)
    assert (lacuna.codigo, lacuna.nivel) == ("votos_sem_tipo", lacunas.CONTRADICAO)


def test_placar_que_bate_e_resultado_sem_valor(db, votacao):
    db.session.add_all([fabricas.voto(), fabricas.voto(deputado_id=2, tipo_voto="Não")])
    votacao.aprovacao = None
    db.session.commit()
    [lacuna] = lacunas.lacunas_da_votacao(votacao)
    assert (lacuna.codigo, lacuna.nivel, lacuna.certeza) == ("sem_resultado", lacunas.CAMPO_VAZIO, lacunas.COMPROVADO)


def test_votos_pendentes_nao_sao_lacuna_da_camara(db, votacao):
    votacao.filhos_sincronizados_em = None
    db.session.commit()
    assert lacunas.lacunas_da_votacao(votacao) == []


def test_lacunas_das_fontes_vem_das_mais_graves_para_as_menos(db, votacao):
    db.session.add_all([fabricas.voto(tipo_voto=None), fabricas.voto(deputado_id=2, tipo_voto=None)])
    db.session.get(Proposicao, 2310837).regime = "."
    db.session.commit()
    achadas = lacunas.lacunas_das_fontes([("votacao", "2310837-8"), ("proposicao", "2310837"), ("orgao", "180")])
    # A proposicao da fabrica nao tem situacao: tambem e campo vazio
    assert [lacuna.codigo for lacuna in achadas] == ["so_placar", "sem_situacao", "sem_regime"]


# ======================================================
# SECOES DO CORPO
# ======================================================
def test_secoes_do_corpo():
    corpo = '## O que propõe\n\nEmenta.\n\n## Onde está na Câmara\n\nSituação: "x".\n\nÚltimos passos:\na\nb'
    assert secoes_do_corpo(corpo) == [
        {"titulo": "O que propõe", "texto": "Ementa."},
        {"titulo": "Onde está na Câmara", "texto": 'Situação: "x".\n\nÚltimos passos:\na\nb'},
    ]


def test_noticia_antiga_sem_secoes_vira_uma_secao_sem_titulo():
    assert secoes_do_corpo("Texto antigo.\n\nOutro paragrafo.") == [
        {"titulo": None, "texto": "Texto antigo.\n\nOutro paragrafo."}
    ]
    assert secoes_do_corpo("") == []


# ======================================================
# GERACAO E API
# ======================================================
def test_noticia_gerada_tem_as_secoes_na_ordem_e_a_situacao_explicada(db, proposicao):
    geracao, _ = gerar_noticia(None, "nova", 2310837, GeradorFrases())
    noticia = geracao.noticia
    titulos = [secao["titulo"] for secao in secoes_do_corpo(noticia.corpo)]
    # Sem lacuna, sem a secao das lacunas
    assert titulos == ["O que propõe", "Onde está na Câmara"]
    assert f'Situação: "Aguardando Parecer". {SITUACOES[915]}' in noticia.corpo


def test_codigo_de_situacao_desconhecido_avisa_no_log(db, proposicao):
    proposicao.cod_situacao, proposicao.situacao = 9999, "Situação Nova"
    db.session.commit()
    geracao, _ = gerar_noticia(None, "nova", 2310837, GeradorFrases())
    assert 'Situação: "Situação Nova".\n' in geracao.noticia.corpo
    aviso = db.session.scalar(db.select(LogSistema).filter_by(acao="situacao_desconhecida"))
    assert aviso.nivel == "aviso" and aviso.entidade_id == "2310837"


def test_api_da_noticia_entrega_secoes_situacao_e_lacunas(app, db):
    dados = fabricas.popular(db)
    proposicao = db.session.get(Proposicao, 2310837)
    proposicao.cod_situacao, proposicao.situacao, proposicao.regime = 924, "Pronta para Pauta", "."
    dados.noticia.status, dados.noticia.publicado_em = "publicada", datetime(2026, 11, 10, 15, 0)
    dados.noticia.corpo = "## O que propõe\n\nEmenta."
    db.session.add(NoticiaFonte(noticia_id=dados.noticia.id, tipo="proposicao", ref_id="2310837", ordem=2))
    db.session.commit()
    detalhe = app.test_client().get(f"/api/noticias/{dados.noticia.slug}").get_json()
    assert detalhe["secoes"] == [{"titulo": "O que propõe", "texto": "Ementa."}]
    situacao = detalhe["transparencia"]["situacao"]
    assert situacao["nome_da_camara"] == "Pronta para Pauta" and situacao["explicacao"] == SITUACOES[924]
    assert situacao["proposicao_id"] == 2310837
    codigos = [lacuna["codigo"] for lacuna in detalhe["transparencia"]["lacunas"]]
    assert "sem_regime" in codigos
    assert all("nivel" not in lacuna for lacuna in detalhe["transparencia"]["lacunas"])


def test_api_da_proposicao_entrega_situacao_explicada_e_lacunas(app, db, proposicao):
    proposicao.url_inteiro_teor = None
    db.session.commit()
    pagina = app.test_client().get("/api/proposicoes/2310837").get_json()
    assert pagina["situacao_explicada"]["explicacao"] == SITUACOES[915]
    assert [lacuna["codigo"] for lacuna in pagina["lacunas"]] == ["sem_inteiro_teor"]
