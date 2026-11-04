from datetime import date, datetime

import pytest

from api_falsa import URL_BASE, carregar, envelope
from desperta.coletor import (
    blocos,
    deputados,
    eventos,
    frentes,
    legislaturas,
    liderancas,
    orgaos,
    partidos,
    proposicoes,
    relatorio,
    rotinas,
    temas,
    votacoes,
)
from desperta.ext.db import db as _db
from desperta.orgaos.models import DeputadoOrgao, Evento, Orgao, PautaItem
from desperta.parlamentares.models import (
    Bloco,
    BlocoPartido,
    Deputado,
    Frente,
    FrenteMembro,
    Legislatura,
    Lideranca,
    Partido,
)
from desperta.proposicoes.models import ICONES_TEMA, Proposicao, ProposicaoAutor, ProposicaoTema, Tema, Tramitacao
from desperta.sistema.models import Coleta, LogSistema
from desperta.votacoes.models import Orientacao, Votacao, VotacaoProposicao, Voto

INICIO = date(2024, 5, 1)
FIM = date(2024, 5, 31)
ID_PROPOSICAO = 414367
ID_VOTACAO = "2422697-83"
ID_EVENTO = 73144


def _ultima_coleta(db):
    return db.session.scalars(db.select(Coleta).order_by(Coleta.id.desc())).first()


def _total(db, modelo):
    return len(db.session.scalars(db.select(modelo)).all())


def _responder_proposicao(api):
    api.responder("proposicoes", carregar("proposicoes"))
    api.responder(f"proposicoes/{ID_PROPOSICAO}", carregar("proposicao"))
    api.responder(f"proposicoes/{ID_PROPOSICAO}/autores", carregar("proposicao_autores"))
    api.responder(f"proposicoes/{ID_PROPOSICAO}/temas", carregar("proposicao_temas"))
    api.responder(f"proposicoes/{ID_PROPOSICAO}/tramitacoes", carregar("proposicao_tramitacoes"))


def _status_mudou(api):
    """A proposicao tramitou: a proxima coleta volta a buscar os filhos (decisao 12.1)."""
    corpo = carregar("proposicao")
    corpo["dados"]["statusProposicao"]["dataHora"] = "2026-10-30T10:00"
    api.responder(f"proposicoes/{ID_PROPOSICAO}", corpo)


def _responder_votacao(api):
    api.responder("votacoes", carregar("votacoes"))
    api.responder(f"votacoes/{ID_VOTACAO}", carregar("votacao"))
    api.responder(f"votacoes/{ID_VOTACAO}/votos", carregar("votos"))
    api.responder(f"votacoes/{ID_VOTACAO}/orientacoes", carregar("orientacoes"))


def _responder_evento(api, pauta=None):
    api.responder("eventos", carregar("eventos"))
    api.responder(f"eventos/{ID_EVENTO}", carregar("evento"))
    api.responder(f"eventos/{ID_EVENTO}/pauta", pauta or carregar("pauta"))


# ======================================================
# TABELAS DE APOIO
# ======================================================
def test_legislaturas(db, api, cliente):
    api.responder("legislaturas", carregar("legislaturas"))
    legislaturas.coletar(cliente)
    legislatura = db.session.get(Legislatura, 57)
    assert legislatura.data_inicio == date(2023, 2, 1)
    assert legislatura.data_fim == date(2027, 1, 31)
    assert legislaturas.id_atual(cliente, date(2026, 10, 30)) == 57


def test_temas_convertem_o_codigo_e_usam_o_icone_padrao(db, api, cliente):
    api.responder("referencias/proposicoes/codTema", carregar("temas"))
    temas.coletar(cliente)
    tema = db.session.get(Tema, 34)
    assert tema.nome == "Administração Pública"
    assert tema.icone == "article"


def test_temas_usam_o_mapa_de_icones(db, api, cliente, monkeypatch):
    monkeypatch.setitem(ICONES_TEMA, 34, "gavel")
    api.responder("referencias/proposicoes/codTema", carregar("temas"))
    temas.coletar(cliente)
    assert db.session.get(Tema, 34).icone == "gavel"


def test_partidos_trazem_o_logo_do_detalhe(db, api, cliente):
    api.responder("partidos", carregar("partidos"))
    api.responder("partidos/36898", carregar("partido"))
    corpo = carregar("partidos")
    corpo["dados"][0]["id"] = 37906
    api.responder("partidos", corpo)
    api.responder("partidos/37906", carregar("partido"))
    partidos.coletar(cliente, 57)
    assert db.session.get(Partido, 37906).url_logo.endswith("PL.gif")


def _responder_deputados(api):
    def por_sexo(params):
        return carregar("deputados") if params["siglaSexo"] == "M" else envelope([])

    api.responder("deputados", por_sexo)


def test_deputados_pegam_o_sexo_do_filtro(base, api, cliente):
    _responder_deputados(api)
    deputados.coletar(cliente, 57)
    deputado = base.session.get(Deputado, 160592)
    assert deputado.sexo == "M"
    assert (deputado.sigla_uf, deputado.sigla_partido, deputado.id_legislatura) == ("PR", "PT", 57)
    params = [params["siglaSexo"] for caminho, params in api.chamadas if caminho == "deputados"]
    assert params == ["M", "F"]


def test_partido_desconhecido_fica_nulo_com_a_sigla(base, api, cliente):
    """D3: partido_id pode ser nulo; sigla_partido sempre vem."""
    _responder_deputados(api)
    deputados.coletar(cliente, 57)
    deputado = base.session.get(Deputado, 160592)
    assert deputado.partido_id is None
    assert deputado.sigla_partido == "PT"
    assert _ultima_coleta(base).status == "ok"


def test_deputado_liga_ao_partido_existente(base, api, cliente):
    base.session.add(Partido(id=36844, sigla="PT", nome="PT", hash_origem="a" * 64))
    base.session.commit()
    _responder_deputados(api)
    deputados.coletar(cliente, 57)
    assert base.session.get(Deputado, 160592).partido_id == 36844


def test_legislatura_mais_antiga_nao_troca_a_mais_nova(base, api, cliente):
    base.session.add(Legislatura(id=56, data_inicio=date(2019, 2, 1), data_fim=date(2023, 1, 31), hash_origem="a" * 64))
    base.session.commit()
    _responder_deputados(api)
    deputados.coletar(cliente, 57)

    corpo = carregar("deputados")
    corpo["dados"][0].update(idLegislatura=56, siglaPartido="ANTIGO", siglaUf="SP")
    api.responder("deputados", lambda params: corpo if params["siglaSexo"] == "M" else envelope([]))
    deputados.coletar(cliente, 56)

    deputado = base.session.get(Deputado, 160592)
    assert (deputado.id_legislatura, deputado.sigla_partido) == (57, "PT")
    # O que nao depende da legislatura continua atualizando
    assert deputado.sigla_uf == "SP"


def test_coleta_de_deputados_com_504_fica_parcial_e_nao_propaga(base, api, cliente):
    api.responder("deputados", [504] * 10)
    deputados.coletar(cliente, 57)
    coleta = _ultima_coleta(base)
    assert coleta.status == "parcial"
    assert (coleta.requisicoes, coleta.erros_http) == (10, 10)


def test_504_na_pagina_2_guarda_a_pagina_1_e_tenta_o_outro_filtro(base, api, cliente):
    """Aconteceu na carga real: a pagina 1 de siglaSexo=M veio, e a pagina 2 deu 504."""
    pagina_1 = carregar("deputados")
    pagina_1["links"].append({"rel": "next", "href": f"{URL_BASE}/deputados-pagina-2"})
    feminino = carregar("deputados")
    feminino["dados"][0]["id"] = 204554

    api.responder("deputados", lambda params: pagina_1 if params["siglaSexo"] == "M" else feminino)
    api.responder("deputados-pagina-2", [504] * 5)
    deputados.coletar(cliente, 57)

    assert base.session.get(Deputado, 160592).sexo == "M"
    assert base.session.get(Deputado, 204554).sexo == "F"
    coleta = _ultima_coleta(base)
    assert coleta.status == "parcial"
    assert base.session.scalar(base.select(LogSistema).where(LogSistema.entidade_id == "siglaSexo=M")).nivel == "erro"


def test_orgaos(db, api, cliente):
    api.responder("orgaos", carregar("orgaos"))
    orgaos.coletar(cliente)
    assert db.session.get(Orgao, 4).sigla == "MESA"


def test_membros_de_orgao_e_vinculos_que_sumiram(base, api, cliente):
    base.session.add(
        Orgao(
            id=2003,
            sigla="CCJC",
            nome="CCJC",
            apelido="CCJC",
            cod_tipo_orgao=2,
            tipo_orgao="Comissao",
            hash_origem="a" * 64,
        )
    )
    base.session.commit()
    corpo = carregar("membros")
    api.responder("orgaos/2003/membros", corpo)
    orgaos.coletar_membros(cliente)

    assert _total(base, DeputadoOrgao) == 2
    cargo = base.session.get(DeputadoOrgao, (178860, 2003, date(2026, 2, 9)))
    assert (cargo.titulo, cargo.cod_titulo) == ("Titular", "101")
    assert base.session.get(Orgao, 2003).filhos_sincronizados_em is not None

    um_so = carregar("membros")
    um_so["dados"] = um_so["dados"][:1]
    api.responder("orgaos/2003/membros", um_so)
    orgaos.coletar_membros(cliente)
    assert _total(base, DeputadoOrgao) == 1


def test_membros_buscam_pendentes_primeiro(base, api, cliente):
    for id_orgao, sincronizado in ((1, datetime(2026, 1, 1)), (2, None), (3, datetime(2025, 1, 1))):
        base.session.add(
            Orgao(
                id=id_orgao,
                sigla="X",
                nome="X",
                apelido="X",
                cod_tipo_orgao=2,
                tipo_orgao="X",
                hash_origem="a" * 64,
                filhos_sincronizados_em=sincronizado,
            )
        )
    base.session.commit()
    for id_orgao in (1, 2, 3):
        api.responder(f"orgaos/{id_orgao}/membros", envelope([]))
    orgaos.coletar_membros(cliente, limite=2)
    assert api.caminhos_chamados()[-2:] == ["orgaos/2/membros", "orgaos/3/membros"]


def test_mesa_usa_o_orgao_4(base, api, cliente):
    api.responder("legislaturas/57/mesa", carregar("mesa"))
    orgaos.coletar_mesa(cliente, 57)
    cargo = base.session.get(DeputadoOrgao, (178947, 4, date(2023, 2, 1)))
    assert (cargo.titulo, cargo.cod_titulo) == ("2º Vice-Presidente", "3")
    assert cargo.data_fim == date(2025, 2, 1)
    assert base.session.get(Orgao, 4) is not None


def test_liderancas_nao_duplicam(base, api, cliente):
    api.responder("legislaturas/57/lideres", carregar("lideres"))
    liderancas.coletar(cliente, 57)
    total = _total(base, Lideranca)
    assert total == 2
    liderancas.coletar(cliente, 57)
    assert _total(base, Lideranca) == total
    coleta = _ultima_coleta(base)
    assert (coleta.itens_novos, coleta.itens_atualizados) == (0, 0)
    lider = base.session.scalar(base.select(Lideranca).where(Lideranca.deputado_id == 133439))
    assert (lider.titulo, lider.bancada_nome, lider.bancada_tipo) == ("Presidente", "PDT", "Partido Político")


def _responder_blocos(api, siglas=(("PT", 36844), ("PCdoB", 36779), ("PV", 36886))):
    api.responder("blocos", carregar("blocos"))
    api.responder("blocos/584/partidos", carregar("bloco_partidos"))
    api.responder("partidos", envelope([{"id": id_partido, "sigla": sigla} for sigla, id_partido in siglas]))


def test_blocos_convertem_ids_e_ligam_partido_pela_sigla_da_legislatura(base, api, cliente):
    """A resposta real de /blocos/584/partidos traz id 584 em todos os partidos (decisao 12.3)."""
    _responder_blocos(api)
    blocos.coletar(cliente, 57)
    bloco = base.session.get(Bloco, 584)
    assert bloco.id == 584 and bloco.id_legislatura == 57 and bloco.federacao is True
    assert {v.partido_id for v in bloco.partidos} == {36844, 36779, 36886}
    assert ("partidos", {"idLegislatura": 57, "itens": 100}) in api.chamadas
    assert _ultima_coleta(base).status == "ok"
    assert relatorio.blocos_com_id_errado() == (1, 0)


def test_partido_de_outra_legislatura_com_a_mesma_sigla_nao_atrapalha(base, api, cliente):
    base.session.add(Partido(id=1, sigla="PT", nome="Antigo", hash_origem="a" * 64))
    base.session.commit()
    _responder_blocos(api)
    blocos.coletar(cliente, 57)
    assert 1 not in {v.partido_id for v in base.session.get(Bloco, 584).partidos}
    assert relatorio.blocos_com_id_errado() == (1, 0)


def test_bloco_guarda_so_a_composicao_atual(base, api, cliente):
    _responder_blocos(api)
    blocos.coletar(cliente, 57)
    menor = carregar("bloco_partidos")
    menor["dados"] = menor["dados"][:2]
    api.responder("blocos/584/partidos", menor)
    blocos.coletar(cliente, 57)
    assert _total(base, BlocoPartido) == 2


def test_sigla_ambigua_ou_desconhecida_nao_liga_e_avisa(base, api, cliente):
    _responder_blocos(api, siglas=(("PT", 1), ("PT", 2), ("PCdoB", 36779)))
    blocos.coletar(cliente, 57)
    assert {v.partido_id for v in base.session.get(Bloco, 584).partidos} == {36779}
    avisos = base.session.scalars(base.select(LogSistema).where(LogSistema.acao == "bloco_partido_sem_id")).all()
    assert len(avisos) == 2
    assert relatorio.blocos_com_id_errado() == (1, 2)


def test_partidos_da_legislatura_sao_pedidos_uma_vez_so(base, api, cliente):
    _responder_blocos(api)
    blocos.coletar(cliente, 57)
    assert api.caminhos_chamados().count("partidos") == 1


def test_id_de_partido_valido_continua_sendo_usado(base, api, cliente):
    _responder_blocos(api)
    corpo = carregar("bloco_partidos")
    corpo["dados"] = [dict(corpo["dados"][0], id=36844)]
    api.responder("blocos/584/partidos", corpo)
    blocos.coletar(cliente, 57)
    assert [v.partido_id for v in base.session.get(Bloco, 584).partidos] == [36844]


def test_frentes_sem_parametro_itens_nos_membros(base, api, cliente):
    api.responder("frentes", carregar("frentes"))
    api.responder("frentes/55703", carregar("frente"))
    api.responder("frentes/55703/membros", carregar("frente_membros"))
    frentes.coletar(cliente, 57)
    assert base.session.get(Frente, 55703).titulo.startswith("Frente Parlamentar")
    membro = base.session.get(FrenteMembro, (55703, 220686))
    assert (membro.titulo, membro.cod_titulo) == ("Coordenador", "14")
    assert ("frentes/55703/membros", None) in api.chamadas


def test_senador_em_frente_fica_de_fora_com_aviso(base, api, cliente):
    api.responder("frentes", carregar("frentes"))
    api.responder("frentes/55703", carregar("frente"))
    api.responder("frentes/55703/membros", carregar("frente_membros"))
    api.responder("deputados/220686", 404)
    frentes.coletar(cliente, 57)
    assert _total(base, FrenteMembro) == 0
    assert _ultima_coleta(base).status == "ok"
    aviso = base.session.scalar(base.select(LogSistema).where(LogSistema.acao == "referencia_ausente"))
    assert aviso.nivel == "aviso"


# ======================================================
# PROPOSICOES
# ======================================================
def test_proposicao_grava_detalhe_autores_temas_e_tramitacoes(base, api, cliente):
    _responder_proposicao(api)
    proposicoes.coletar(cliente, INICIO, FIM, limite_pendentes=0)

    proposicao = base.session.get(Proposicao, ID_PROPOSICAO)
    assert (proposicao.sigla_tipo, proposicao.numero, proposicao.ano) == ("PEC", 300, 2008)
    # statusProposicao achatado
    assert proposicao.situacao == "Tramitando em Conjunto"
    assert proposicao.cod_situacao == 925
    assert proposicao.data_status == datetime(2026, 4, 15, 14, 21)
    assert proposicao.regime.startswith("Especial")
    assert proposicao.apreciacao.startswith("Proposição Sujeita")
    assert proposicao.descricao_tipo == "Proposta de Emenda à Constituição"
    assert proposicao.filhos_sincronizados_em is not None

    assert proposicao.autores[0].deputado_id == 73434
    assert proposicao.autores[0].proponente is True
    assert base.session.get(Tema, 34) is not None and proposicao.temas[0].cod_tema == 34
    assert [t.sequencia for t in proposicao.tramitacoes] == [1, 7, 11]
    assert proposicao.tramitacoes[0].orgao_id == 180


def test_proposicao_so_e_gravada_depois_do_detalhe(base, api, cliente):
    _responder_proposicao(api)
    api.responder(f"proposicoes/{ID_PROPOSICAO}", [404])
    proposicoes.coletar(cliente, INICIO, FIM, limite_pendentes=0)
    assert _total(base, Proposicao) == 0
    assert _ultima_coleta(base).status == "parcial"


def test_reprocessar_nao_duplica_nem_conta_como_novo(base, api, cliente):
    """RNF06: ingestao idempotente."""
    _responder_proposicao(api)
    proposicoes.coletar(cliente, INICIO, FIM, limite_pendentes=0)
    totais = [_total(base, m) for m in (Proposicao, ProposicaoAutor, ProposicaoTema, Tramitacao, Orgao, Deputado)]

    _responder_proposicao(api)
    proposicoes.coletar(cliente, INICIO, FIM, limite_pendentes=0)

    novos_totais = [_total(base, m) for m in (Proposicao, ProposicaoAutor, ProposicaoTema, Tramitacao, Orgao, Deputado)]
    assert novos_totais == totais
    coleta = _ultima_coleta(base)
    assert (coleta.itens_novos, coleta.itens_atualizados) == (0, 0)
    assert coleta.total_itens > 0


def test_mudanca_na_ementa_atualiza_e_marca_atualizado(base, api, cliente):
    _responder_proposicao(api)
    proposicoes.coletar(cliente, INICIO, FIM, limite_pendentes=0)
    corpo = carregar("proposicao")
    corpo["dados"]["ementa"] = "Nova ementa"
    _responder_proposicao(api)
    api.responder(f"proposicoes/{ID_PROPOSICAO}", corpo)
    proposicoes.coletar(cliente, INICIO, FIM, limite_pendentes=0)
    assert base.session.get(Proposicao, ID_PROPOSICAO).ementa == "Nova ementa"
    assert _ultima_coleta(base).itens_atualizados == 1


def test_autor_que_nao_e_deputado_fica_com_deputado_id_nulo(base, api, cliente):
    _responder_proposicao(api)
    autores = carregar("proposicao_autores")
    autores["dados"] = [
        {
            "uri": "https://dadosabertos.camara.leg.br/api/v2/orgaos/4",
            "nome": "Mesa Diretora",
            "codTipo": 40000,
            "tipo": "Órgão do Poder Legislativo",
            "ordemAssinatura": 1,
            "proponente": 1,
        }
    ]
    api.responder(f"proposicoes/{ID_PROPOSICAO}/autores", autores)
    proposicoes.coletar(cliente, INICIO, FIM, limite_pendentes=0)
    autor = base.session.get(ProposicaoAutor, (ID_PROPOSICAO, 1))
    assert autor.deputado_id is None
    assert autor.nome == "Mesa Diretora"


def test_autor_e_orgao_de_fora_da_janela_sao_buscados_sob_demanda(base, api, cliente):
    _responder_proposicao(api)
    proposicoes.coletar(cliente, INICIO, FIM, limite_pendentes=0)
    assert "deputados/73434" in api.caminhos_chamados()
    assert "orgaos/180" in api.caminhos_chamados()
    assert base.session.get(Orgao, 180) is not None


def test_url_inteiro_teor_vazia_vai_para_o_relatorio_sem_afrouxar_nullable(base, api, cliente):
    """Decisao 10.2 e carga de validacao: a coluna aparece na lista de falhas."""
    _responder_proposicao(api)
    corpo = carregar("proposicao")
    corpo["dados"]["urlInteiroTeor"] = None
    api.responder(f"proposicoes/{ID_PROPOSICAO}", corpo)
    proposicoes.coletar(cliente, INICIO, FIM, limite_pendentes=0)

    assert _ultima_coleta(base).status == "parcial"
    assert _total(base, Proposicao) == 0
    assert _total(base, ProposicaoAutor) == 0
    assert relatorio.falhas_por_coluna() == [("proposicao.url_inteiro_teor", 1)]
    assert _db.metadata.tables["proposicao"].c["url_inteiro_teor"].nullable is False


def test_filho_ruim_nao_apaga_os_outros_e_mantem_a_proposicao(base, api, cliente):
    _responder_proposicao(api)
    proposicoes.coletar(cliente, INICIO, FIM, limite_pendentes=0)
    assert _total(base, Tramitacao) == 3

    corpo = carregar("proposicao_tramitacoes")
    corpo["dados"] = corpo["dados"][:1]
    corpo["dados"][0]["despacho"] = None
    _responder_proposicao(api)
    _status_mudou(api)
    api.responder(f"proposicoes/{ID_PROPOSICAO}/tramitacoes", corpo)
    proposicoes.coletar(cliente, INICIO, FIM, limite_pendentes=0)

    assert _ultima_coleta(base).status == "parcial"
    # Com falha, os vinculos que sumiram nao sao apagados
    assert _total(base, Tramitacao) == 3


def test_tramitacao_que_sumiu_e_apagada(base, api, cliente):
    _responder_proposicao(api)
    proposicoes.coletar(cliente, INICIO, FIM, limite_pendentes=0)
    corpo = carregar("proposicao_tramitacoes")
    corpo["dados"] = corpo["dados"][:2]
    _responder_proposicao(api)
    _status_mudou(api)
    api.responder(f"proposicoes/{ID_PROPOSICAO}/tramitacoes", corpo)
    proposicoes.coletar(cliente, INICIO, FIM, limite_pendentes=0)
    assert _total(base, Tramitacao) == 2


def test_tema_fora_da_lista_vira_aviso(base, api, cliente):
    _responder_proposicao(api)
    corpo = carregar("proposicao_temas")
    corpo["dados"] = [{"codTema": 999, "tema": "Novo", "relevancia": 0}]
    api.responder(f"proposicoes/{ID_PROPOSICAO}/temas", corpo)
    proposicoes.coletar(cliente, INICIO, FIM, limite_pendentes=0)
    assert _total(base, ProposicaoTema) == 0
    assert _ultima_coleta(base).status == "ok"


def test_pendentes_sao_buscados_depois_da_janela(base, api, cliente):
    _responder_proposicao(api)
    base.session.add(
        Proposicao(
            id=5,
            sigla_tipo="PL",
            cod_tipo=1,
            descricao_tipo="PL",
            numero=1,
            ano=2000,
            ementa="e",
            data_apresentacao=datetime(2000, 1, 1),
            url_inteiro_teor="u",
            data_status=datetime(2000, 1, 1),
            regime="r",
            apreciacao="a",
            hash_origem="a" * 64,
        )
    )
    base.session.commit()
    for sub in ("autores", "temas", "tramitacoes"):
        api.responder(f"proposicoes/5/{sub}", envelope([]))
    proposicoes.coletar(cliente, INICIO, FIM)
    assert base.session.get(Proposicao, 5).filhos_sincronizados_em is not None


def test_parametros_da_listagem_de_proposicoes(base, api, cliente):
    _responder_proposicao(api)
    proposicoes.coletar(cliente, INICIO, FIM, sigla_tipo="PEC", limite_pendentes=0)
    params = dict(api.chamadas)["proposicoes"]
    assert params["dataInicio"] == "2024-05-01" and params["dataFim"] == "2024-05-31"
    assert params["siglaTipo"] == "PEC" and params["itens"] == 100
    coleta = _ultima_coleta(base)
    assert (coleta.recurso, coleta.tipo) == ("proposicoes", "incremental")
    assert (coleta.data_inicio_ref, coleta.data_fim_ref) == (INICIO, FIM)


# ======================================================
# EVENTOS
# ======================================================
def test_evento_grava_detalhe_e_pauta(base, api, cliente):
    _responder_evento(api)
    eventos.coletar(cliente, INICIO, FIM)
    evento = base.session.get(Evento, ID_EVENTO)
    assert evento.situacao == "Encerrada"
    assert evento.data_hora_inicio == datetime(2024, 5, 28, 14, 0)
    assert evento.local == "Plenário da Câmara dos Deputados"
    assert evento.url_documento_pauta.endswith("/pauta")
    assert evento.orgao_id == 180
    assert evento.filhos_sincronizados_em is not None
    assert _total(base, PautaItem) == 3
    com_relator = base.session.scalar(base.select(PautaItem).where(PautaItem.relator_id.is_not(None)))
    assert com_relator.relator_id == 74856


def test_todos_os_orgaos_do_evento_sao_cadastrados(base, api, cliente):
    """D1 e D5: o primeiro vira orgao_id, os demais tambem entram em orgao."""
    corpo = carregar("evento")
    outro = dict(corpo["dados"]["orgaos"][0], id=2003, sigla="CCJC")
    corpo["dados"]["orgaos"].append(outro)
    _responder_evento(api)
    api.responder(f"eventos/{ID_EVENTO}", corpo)
    eventos.coletar(cliente, INICIO, FIM)
    assert base.session.get(Evento, ID_EVENTO).orgao_id == 180
    assert base.session.get(Orgao, 2003).sigla == "CCJC"


def test_local_externo(base, api, cliente):
    corpo = carregar("evento")
    corpo["dados"]["localCamara"] = {"nome": None}
    corpo["dados"]["localExterno"] = "Auditório em Vitória"
    _responder_evento(api)
    api.responder(f"eventos/{ID_EVENTO}", corpo)
    eventos.coletar(cliente, INICIO, FIM)
    assert base.session.get(Evento, ID_EVENTO).local == "Auditório em Vitória"


def _pauta_com_repeticao(uris):
    corpo = carregar("pauta")
    item = corpo["dados"][0]
    corpo["dados"] = [dict(item, uriVotacao=uri) for uri in uris]
    return corpo


def test_ordem_repetida_vira_uma_linha_com_aviso(base, api, cliente):
    """A API manda uma linha por votacao do mesmo item; a PK e (evento_id, ordem)."""
    _responder_evento(api, _pauta_com_repeticao([None, None]))
    eventos.coletar(cliente, INICIO, FIM)
    assert _total(base, PautaItem) == 1
    assert base.session.scalar(base.select(LogSistema).where(LogSistema.acao == "pauta_ordem_repetida")) is not None
    assert _ultima_coleta(base).status == "ok"


def test_pauta_so_liga_votacao_do_mesmo_evento(base, api, cliente):
    uri = "https://dadosabertos.camara.leg.br/api/v2/votacoes/"
    base.session.add(
        Orgao(id=180, sigla="PLEN", nome="P", apelido="P", cod_tipo_orgao=26, tipo_orgao="P", hash_origem="a" * 64)
    )
    base.session.add(
        Votacao(
            id="1-1",
            data=date(2024, 5, 28),
            data_hora_registro=datetime(2024, 5, 28),
            orgao_id=180,
            sigla_orgao="PLEN",
            descricao="d",
            hash_origem="a" * 64,
        )
    )
    base.session.commit()
    _responder_evento(api, _pauta_com_repeticao([f"{uri}1-1/"]))
    eventos.coletar(cliente, INICIO, FIM)
    assert base.session.scalars(base.select(PautaItem)).first().votacao_id is None


def test_eventos_em_aberto_sao_recoletados(base, api, cliente):
    aberto = carregar("evento")
    aberto["dados"].update(situacao="Convocada", dataHoraInicio=datetime.now().isoformat(timespec="minutes"))
    _responder_evento(api)
    api.responder(f"eventos/{ID_EVENTO}", aberto)
    eventos.coletar(cliente, INICIO, FIM)
    assert base.session.get(Evento, ID_EVENTO).situacao == "Convocada"

    api.responder("eventos", envelope([]))
    encerrado = carregar("evento")
    encerrado["dados"].update(dataHoraInicio=aberto["dados"]["dataHoraInicio"])
    api.responder(f"eventos/{ID_EVENTO}", encerrado)
    eventos.coletar(cliente, INICIO, FIM)
    assert base.session.get(Evento, ID_EVENTO).situacao == "Encerrada"


def test_evento_encerrado_nao_e_recoletado(base, api, cliente):
    _responder_evento(api)
    eventos.coletar(cliente, INICIO, FIM)
    api.responder("eventos", envelope([]))
    api.chamadas.clear()
    eventos.coletar(cliente, INICIO, FIM)
    assert f"eventos/{ID_EVENTO}" not in api.caminhos_chamados()


# ======================================================
# VOTACOES
# ======================================================
def test_votacao_com_votos_orientacoes_e_afetadas(base, api, cliente):
    _responder_votacao(api)
    votacoes.coletar(cliente, INICIO, FIM)
    votacao = base.session.get(Votacao, ID_VOTACAO)
    assert votacao.aprovacao is False
    assert votacao.orgao_id == 180
    assert votacao.evento_id == ID_EVENTO
    assert votacao.proposicao_id is None
    assert votacao.filhos_sincronizados_em is not None
    assert len(votacao.votos) == 3
    assert votacao.votos[0].sigla_partido
    assert _total(base, VotacaoProposicao) == 1
    assert _ultima_coleta(base).status == "ok"


def test_orientacao_de_bloco_fica_so_com_o_texto(base, api, cliente):
    """Decisao 10.1."""
    base.session.add(Partido(id=37901, sigla="NOVO", nome="Novo", hash_origem="a" * 64))
    base.session.commit()
    _responder_votacao(api)
    votacoes.coletar(cliente, INICIO, FIM)
    linhas = {o.partido_bloco: o for o in base.session.scalars(base.select(Orientacao))}
    assert linhas["Bl MdbPsdRepPode"].tipo_lideranca == "B" and linhas["Bl MdbPsdRepPode"].partido_id is None
    assert linhas["NOVO"].tipo_lideranca == "P" and linhas["NOVO"].partido_id == 37901
    assert linhas["Governo"].partido_id is None


def test_orientacao_de_partido_desconhecido_fica_sem_partido_id(base, api, cliente):
    _responder_votacao(api)
    votacoes.coletar(cliente, INICIO, FIM)
    assert base.session.get(Orientacao, (ID_VOTACAO, "NOVO")).partido_id is None
    assert _ultima_coleta(base).status == "ok"


def test_proposicao_objeto_tambem_entra_nas_afetadas(base, api, cliente):
    _responder_votacao(api)
    lista = carregar("votacoes")
    lista["dados"][0]["uriProposicaoObjeto"] = f"https://x/api/v2/proposicoes/{ID_PROPOSICAO}"
    api.responder("votacoes", lista)
    api.responder(f"proposicoes/{ID_PROPOSICAO}", carregar("proposicao"))
    votacoes.coletar(cliente, INICIO, FIM)
    assert base.session.get(Votacao, ID_VOTACAO).proposicao_id == ID_PROPOSICAO
    assert base.session.get(VotacaoProposicao, (ID_VOTACAO, ID_PROPOSICAO)) is not None
    assert base.session.get(VotacaoProposicao, (ID_VOTACAO, 2422697)) is not None


def test_votacao_simbolica_tem_votos_vazios(base, api, cliente):
    _responder_votacao(api)
    api.responder(f"votacoes/{ID_VOTACAO}/votos", envelope([]))
    votacoes.coletar(cliente, INICIO, FIM)
    assert base.session.get(Votacao, ID_VOTACAO).votos == []
    assert _ultima_coleta(base).status == "ok"


def test_votacao_secreta_grava_os_votos_sem_tipo(base, api, cliente):
    """Fase 2b: em votacao secreta, a API so registra quem estava presente."""
    _responder_votacao(api)
    votos = carregar("votos")
    for voto in votos["dados"]:
        voto["tipoVoto"] = None
    api.responder(f"votacoes/{ID_VOTACAO}/votos", votos)
    votacoes.coletar(cliente, INICIO, FIM)
    votacao = base.session.get(Votacao, ID_VOTACAO)
    assert [voto.tipo_voto for voto in votacao.votos] == [None, None, None]
    assert votacao.filhos_sincronizados_em is not None
    assert _ultima_coleta(base).status == "ok"


def test_voto_com_falha_deixa_a_votacao_pendente(base, api, cliente):
    _responder_votacao(api)
    votos = carregar("votos")
    votos["dados"][0]["dataRegistroVoto"] = None
    api.responder(f"votacoes/{ID_VOTACAO}/votos", votos)
    votacoes.coletar(cliente, INICIO, FIM)
    assert base.session.get(Votacao, ID_VOTACAO).filhos_sincronizados_em is None
    assert len(base.session.get(Votacao, ID_VOTACAO).votos) == 2
    assert _ultima_coleta(base).status == "parcial"

    # Na proxima coleta de pendentes, com a API respondendo certo, a votacao fica completa
    api.responder(f"votacoes/{ID_VOTACAO}/votos", carregar("votos"))
    votacoes.coletar_pendentes(cliente)
    base.session.expire_all()
    assert base.session.get(Votacao, ID_VOTACAO).filhos_sincronizados_em is not None
    assert len(base.session.get(Votacao, ID_VOTACAO).votos) == 3


def test_janela_de_votacoes_e_dividida_por_ano(base, api, cliente):
    api.responder("votacoes", envelope([]))
    votacoes.coletar(cliente, date(2023, 12, 1), date(2024, 1, 15))
    janelas = [(p["dataInicio"], p["dataFim"]) for c, p in api.chamadas if c == "votacoes"]
    assert janelas == [("2023-12-01", "2023-12-31"), ("2024-01-01", "2024-01-15")]


def test_janela_longa_de_proposicoes_e_dividida(base, api, cliente):
    """A API responde 400 com janela maior que 3 meses."""
    api.responder("proposicoes", envelope([]))
    proposicoes.coletar(cliente, date(2025, 1, 1), date(2025, 12, 31), limite_pendentes=0)
    janelas = [
        (date.fromisoformat(p["dataInicio"]), date.fromisoformat(p["dataFim"]))
        for _, p in api.chamadas
        if p and "dataInicio" in p
    ]
    assert len(janelas) == 5
    assert janelas[0] == (date(2025, 1, 1), date(2025, 3, 30))
    assert janelas[-1][1] == date(2025, 12, 31)


def test_reprocessar_votacao_nao_duplica(base, api, cliente):
    _responder_votacao(api)
    votacoes.coletar(cliente, INICIO, FIM)
    votos = _total(base, Voto)
    _responder_votacao(api)
    votacoes.coletar(cliente, INICIO, FIM)
    assert _total(base, Voto) == votos
    coleta = _ultima_coleta(base)
    assert (coleta.itens_novos, coleta.itens_atualizados) == (0, 0)


def test_votacao_nova_refaz_a_pauta_do_evento(base, api, cliente):
    """A votacao chega depois do evento: a pauta so consegue ligar nela na segunda passada."""
    uri = f"https://dadosabertos.camara.leg.br/api/v2/votacoes/{ID_VOTACAO}/"
    _responder_evento(api, _pauta_com_repeticao([uri]))
    eventos.coletar(cliente, INICIO, FIM)
    item = base.session.scalars(base.select(PautaItem)).first()
    assert item.votacao_id is None

    _responder_votacao(api)
    votacoes.coletar(cliente, INICIO, FIM)
    assert base.session.get(Evento, ID_EVENTO).filhos_sincronizados_em is None

    eventos.coletar_pendentes(cliente)
    base.session.expire_all()
    assert base.session.scalars(base.select(PautaItem)).first().votacao_id == ID_VOTACAO
    assert base.session.get(Evento, ID_EVENTO).filhos_sincronizados_em is not None


# ======================================================
# ROTINAS, RELATORIO E COMANDOS
# ======================================================
def test_rotina_segue_mesmo_com_um_recurso_fora_do_ar(base, api, cliente):
    api.responder("proposicoes", [504] * 5)
    _responder_evento(api)
    _responder_votacao(api)
    rotinas.horaria(cliente)
    por_recurso = {c.recurso: c.status for c in base.session.scalars(base.select(Coleta).order_by(Coleta.id))}
    assert por_recurso["proposicoes"] == "erro"
    assert por_recurso["votacoes"] == "ok"
    assert _total(base, Votacao) == 1


@pytest.mark.parametrize(
    "comando",
    [
        "base",
        "horaria",
        "diaria",
        "semanal",
        "mensal",
        "legislaturas",
        "temas",
        "orgaos",
        "partidos",
        "deputados",
        "proposicoes",
        "eventos",
        "eventos-pendentes",
        "votacoes",
        "membros",
        "mesa",
        "liderancas",
        "blocos",
        "frentes",
        "relatorio",
    ],
)
def test_comandos_existem(app, comando):
    resultado = app.test_cli_runner().invoke(args=["coletar", comando, "--help"])
    assert resultado.exit_code == 0


def test_comando_relatorio_mostra_as_colunas(app, base, api, cliente):
    _responder_proposicao(api)
    corpo = carregar("proposicao")
    corpo["dados"]["urlInteiroTeor"] = None
    api.responder(f"proposicoes/{ID_PROPOSICAO}", corpo)
    proposicoes.coletar(cliente, INICIO, FIM, limite_pendentes=0)
    saida = app.test_cli_runner().invoke(args=["coletar", "relatorio"]).output
    assert "proposicao.url_inteiro_teor | 1" in saida
    assert "proposicoes |" in saida
