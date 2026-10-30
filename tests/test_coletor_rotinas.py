import json
import os
import signal
from datetime import date, datetime, timedelta

import pytest

from api_falsa import carregar, envelope
from desperta.coletor import cli as modulo_cli
from desperta.coletor import proposicoes, relatorio, rotinas, trava, votacoes
from desperta.coletor.cliente import ClienteCamara
from desperta.orgaos.models import DeputadoOrgao, Evento, Orgao, PautaItem
from desperta.parlamentares.models import Bloco, Frente, Lideranca
from desperta.proposicoes.models import Proposicao, ProposicaoAutor, Tramitacao
from desperta.sistema.models import Coleta, LogSistema
from desperta.votacoes.models import Votacao, Voto

HOJE = date(2026, 10, 30)
ID_PROPOSICAO = 414367
ID_VOTACAO = "2422697-83"
ID_EVENTO = 73144
FILHOS = ["autores", "temas", "tramitacoes"]


def _proposicao(api):
    api.responder("proposicoes", carregar("proposicoes"))
    api.responder(f"proposicoes/{ID_PROPOSICAO}", carregar("proposicao"))
    api.responder(f"proposicoes/{ID_PROPOSICAO}/autores", carregar("proposicao_autores"))
    api.responder(f"proposicoes/{ID_PROPOSICAO}/temas", carregar("proposicao_temas"))
    api.responder(f"proposicoes/{ID_PROPOSICAO}/tramitacoes", carregar("proposicao_tramitacoes"))


def _evento(api):
    api.responder("eventos", carregar("eventos"))
    api.responder(f"eventos/{ID_EVENTO}", carregar("evento"))
    api.responder(f"eventos/{ID_EVENTO}/pauta", carregar("pauta"))


def _votacao(api):
    api.responder("votacoes", carregar("votacoes"))
    api.responder(f"votacoes/{ID_VOTACAO}", carregar("votacao"))
    api.responder(f"votacoes/{ID_VOTACAO}/votos", carregar("votos"))
    api.responder(f"votacoes/{ID_VOTACAO}/orientacoes", carregar("orientacoes"))


def _apoio(api):
    api.responder("legislaturas", carregar("legislaturas"))
    api.responder("partidos", envelope([{"id": 37906, "sigla": "PL"}]))
    api.responder(
        "deputados", lambda params: carregar("deputados_manual") if params["siglaSexo"] == "M" else envelope([])
    )
    api.responder("orgaos", carregar("orgaos"))
    api.responder("referencias/proposicoes/codTema", carregar("temas"))


def _semanal(api):
    _apoio(api)
    _proposicao(api)
    api.responder("orgaos/111/membros", envelope([]))
    api.responder("orgaos/4/membros", envelope([]))
    api.responder("legislaturas/57/mesa", carregar("mesa"))
    api.responder("legislaturas/57/lideres", carregar("lideres"))
    api.responder("blocos", carregar("blocos"))
    api.responder("blocos/584/partidos", envelope([]))


def _coletas(db):
    return list(db.session.scalars(db.select(Coleta).order_by(Coleta.id)))


def _recursos(db):
    return [coleta.recurso for coleta in _coletas(db)]


def _filhos_chamados(api):
    return [c for c in api.caminhos_chamados() if c.split("/")[-1] in FILHOS]


# ======================================================
# DECISAO 12.1: NAO BUSCAR DE NOVO O QUE NAO MUDOU
# ======================================================
def test_proposicao_nova_busca_os_filhos(base, api, cliente):
    _proposicao(api)
    proposicoes.coletar(cliente, HOJE, HOJE, limite_pendentes=0)
    assert len(_filhos_chamados(api)) == 3


def test_sem_mudanca_no_status_so_chama_o_detalhe(base, api, cliente):
    _proposicao(api)
    proposicoes.coletar(cliente, HOJE, HOJE, limite_pendentes=0)
    registro = base.session.get(Proposicao, ID_PROPOSICAO)
    registro.sincronizado_em = datetime(2020, 1, 1)
    base.session.commit()
    api.chamadas.clear()

    proposicoes.coletar(cliente, HOJE, HOJE, limite_pendentes=0)

    assert _filhos_chamados(api) == []
    assert api.caminhos_chamados().count(f"proposicoes/{ID_PROPOSICAO}") == 1
    base.session.expire_all()
    assert registro.sincronizado_em > datetime(2020, 1, 1)


def test_filhos_nao_sao_apagados_quando_nao_sao_buscados(base, api, cliente):
    _proposicao(api)
    proposicoes.coletar(cliente, HOJE, HOJE, limite_pendentes=0)
    total = len(base.session.scalars(base.select(Tramitacao)).all())
    proposicoes.coletar(cliente, HOJE, HOJE, limite_pendentes=0)
    assert len(base.session.scalars(base.select(Tramitacao)).all()) == total > 0


def test_status_diferente_busca_os_filhos_de_novo(base, api, cliente):
    _proposicao(api)
    proposicoes.coletar(cliente, HOJE, HOJE, limite_pendentes=0)
    corpo = carregar("proposicao")
    corpo["dados"]["statusProposicao"]["dataHora"] = "2026-10-30T10:00"
    api.responder(f"proposicoes/{ID_PROPOSICAO}", corpo)
    api.chamadas.clear()
    proposicoes.coletar(cliente, HOJE, HOJE, limite_pendentes=0)
    assert len(_filhos_chamados(api)) == 3


def test_falha_da_api_nos_filhos_nao_grava_e_tenta_de_novo(base, api, cliente):
    _proposicao(api)
    api.responder(f"proposicoes/{ID_PROPOSICAO}/tramitacoes", [404])
    proposicoes.coletar(cliente, HOJE, HOJE, limite_pendentes=0)
    assert base.session.get(Proposicao, ID_PROPOSICAO) is None

    _proposicao(api)
    proposicoes.coletar(cliente, HOJE, HOJE, limite_pendentes=0)
    assert base.session.get(Proposicao, ID_PROPOSICAO).filhos_sincronizados_em is not None


def test_status_novo_com_falha_na_gravacao_dos_filhos_continua_pendente(base, api, cliente):
    """Sem isto, a data nova ficaria gravada e os filhos nunca mais seriam buscados."""
    _proposicao(api)
    proposicoes.coletar(cliente, HOJE, HOJE, limite_pendentes=0)
    corpo = carregar("proposicao")
    corpo["dados"]["statusProposicao"]["dataHora"] = "2026-10-30T10:00"
    tramitacoes = carregar("proposicao_tramitacoes")
    tramitacoes["dados"][0]["despacho"] = None
    api.responder(f"proposicoes/{ID_PROPOSICAO}", corpo)
    api.responder(f"proposicoes/{ID_PROPOSICAO}/tramitacoes", tramitacoes)
    proposicoes.coletar(cliente, HOJE, HOJE, limite_pendentes=0)
    registro = base.session.get(Proposicao, ID_PROPOSICAO)
    assert registro.data_status == datetime(2026, 10, 30, 10, 0)
    assert registro.filhos_sincronizados_em is None

    _proposicao(api)
    api.responder(f"proposicoes/{ID_PROPOSICAO}", corpo)
    api.chamadas.clear()
    proposicoes.coletar(cliente, HOJE, HOJE, limite_pendentes=0)
    assert len(_filhos_chamados(api)) == 3
    assert base.session.get(Proposicao, ID_PROPOSICAO).filhos_sincronizados_em is not None


# ======================================================
# DECISAO 12.1: TIPOS ACOMPANHADOS
# ======================================================
def test_listagem_usa_os_tipos_acompanhados(base, api, cliente):
    api.responder("proposicoes", envelope([]))
    proposicoes.coletar(cliente, HOJE, HOJE, limite_pendentes=0)
    assert dict(api.chamadas)["proposicoes"]["siglaTipo"] == "PL,PLP,PEC,MPV,PDL"


def test_tipos_acompanhados_vem_da_configuracao(app, base, api, cliente):
    app.config["TIPOS_ACOMPANHADOS"] = ["PEC"]
    api.responder("proposicoes", envelope([]))
    proposicoes.coletar(cliente, HOJE, HOJE, limite_pendentes=0)
    assert dict(api.chamadas)["proposicoes"]["siglaTipo"] == "PEC"


def _proposicao_citada(db, id_proposicao, sigla_tipo):
    db.session.add(
        Proposicao(
            id=id_proposicao,
            sigla_tipo=sigla_tipo,
            cod_tipo=1,
            descricao_tipo="x",
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
    db.session.commit()


def test_pendentes_so_dos_tipos_acompanhados(base, api, cliente):
    """REQ citado por votacao ou pauta fica sem filhos, sem gastar chamadas."""
    _proposicao_citada(base, 1, "REQ")
    _proposicao_citada(base, 2, "PL")
    corpo = carregar("proposicao")
    corpo["dados"].update(id=2, siglaTipo="PL")
    api.responder("proposicoes", envelope([]))
    api.responder("proposicoes/2", corpo)
    for filho in FILHOS:
        api.responder(f"proposicoes/2/{filho}", envelope([]))
    proposicoes.coletar(cliente, HOJE, HOJE)
    assert "proposicoes/1" not in api.caminhos_chamados()
    assert base.session.get(Proposicao, 1).filhos_sincronizados_em is None
    assert base.session.get(Proposicao, 2).filhos_sincronizados_em is not None


def test_tipo_nao_acompanhado_entra_quando_citado(base, api, cliente):
    _votacao(api)
    lista = carregar("votacoes")
    lista["dados"][0]["uriProposicaoObjeto"] = "https://x/api/v2/proposicoes/9"
    api.responder("votacoes", lista)
    corpo = carregar("proposicao")
    corpo["dados"].update(id=9, siglaTipo="REQ")
    api.responder("proposicoes/9", corpo)
    votacoes.coletar(cliente, HOJE, HOJE)
    assert base.session.get(Proposicao, 9).sigla_tipo == "REQ"
    assert base.session.get(Proposicao, 9).filhos_sincronizados_em is None
    assert "proposicoes/9/autores" not in api.caminhos_chamados()


# ======================================================
# DECISAO 12.1: CALENDARIO
# ======================================================
def test_horaria_janelas(base, api, cliente):
    api.responder("proposicoes", envelope([]))
    api.responder("eventos", envelope([]))
    api.responder("votacoes", envelope([]))
    rotinas.horaria(cliente, HOJE)
    chamadas = dict(api.chamadas)
    assert (chamadas["proposicoes"]["dataInicio"], chamadas["proposicoes"]["dataFim"]) == ("2026-10-30", "2026-10-30")
    assert (chamadas["eventos"]["dataInicio"], chamadas["eventos"]["dataFim"]) == ("2026-10-29", "2026-10-30")
    assert (chamadas["votacoes"]["dataInicio"], chamadas["votacoes"]["dataFim"]) == ("2026-10-29", "2026-10-30")


def test_horaria_grava_tudo_na_ordem(base, api, cliente):
    _proposicao(api)
    _evento(api)
    _votacao(api)
    antes = len(_coletas(base))
    rotinas.horaria(cliente, HOJE)
    assert _recursos(base)[antes:] == ["proposicoes", "eventos", "votacoes"]
    assert all(coleta.status == "ok" for coleta in _coletas(base))
    assert base.session.get(Votacao, ID_VOTACAO) is not None
    assert len(base.session.scalars(base.select(PautaItem)).all()) == 3


def test_diaria_proposicoes_de_3_dias_e_pendentes(base, api, cliente):
    _proposicao(api)
    _evento(api)
    _votacao(api)
    votacoes.coletar(cliente, HOJE, HOJE)
    # A proposicao afetada entrou sem filhos e tambem esta pendente
    api.responder("proposicoes/2422697/*", lambda sub: envelope([]))
    # A API falhou nos votos: a votacao fica pendente
    base.session.get(Votacao, ID_VOTACAO).filhos_sincronizados_em = None
    base.session.get(Evento, ID_EVENTO).filhos_sincronizados_em = None
    base.session.commit()
    api.chamadas.clear()
    antes = len(_coletas(base))

    rotinas.diaria(cliente, HOJE)

    params = dict(api.chamadas)["proposicoes"]
    assert (params["dataInicio"], params["dataFim"]) == ("2026-10-27", "2026-10-30")
    assert [(c.recurso, c.tipo) for c in _coletas(base)[antes:]] == [
        ("proposicoes", "incremental"),
        ("eventos", "detalhe"),
        ("votacoes", "detalhe"),
    ]
    assert base.session.get(Votacao, ID_VOTACAO).filhos_sincronizados_em is not None
    assert base.session.get(Evento, ID_EVENTO).filhos_sincronizados_em is not None


def test_votacao_pendente_mantem_a_proposicao_objeto(base, api, cliente):
    _votacao(api)
    lista = carregar("votacoes")
    lista["dados"][0]["uriProposicaoObjeto"] = f"https://x/api/v2/proposicoes/{ID_PROPOSICAO}"
    api.responder("votacoes", lista)
    votacoes.coletar(cliente, HOJE, HOJE)
    base.session.get(Votacao, ID_VOTACAO).filhos_sincronizados_em = None
    base.session.commit()

    votacoes.coletar_pendentes(cliente)

    assert base.session.get(Votacao, ID_VOTACAO).proposicao_id == ID_PROPOSICAO


def test_semanal_varredura_de_30_dias_e_cargos(db, api, cliente):
    _semanal(api)
    rotinas.semanal(cliente, HOJE)
    params = dict(api.chamadas)["proposicoes"]
    assert (params["dataInicio"], params["dataFim"]) == ("2026-09-30", "2026-10-30")
    assert _recursos(db) == [
        "legislaturas",
        "partidos",
        "deputados",
        "orgaos",
        "temas",
        "proposicoes",
        "orgao_membros",
        "mesa",
        "liderancas",
        "blocos",
    ]
    assert db.session.get(Proposicao, ID_PROPOSICAO) is not None
    assert db.session.scalars(db.select(DeputadoOrgao)).first() is not None
    assert db.session.scalars(db.select(Lideranca)).first() is not None
    assert db.session.get(Bloco, 584) is not None
    assert all(coleta.status == "ok" for coleta in _coletas(db)), [c.mensagem_erro for c in _coletas(db)]


def test_base_grava_as_tabelas_de_apoio_e_devolve_a_legislatura(db, api, cliente):
    _apoio(api)
    assert rotinas.base(cliente) == 57
    assert _recursos(db) == ["legislaturas", "partidos", "deputados", "orgaos", "temas"]
    assert db.session.get(Orgao, 4) is not None


def test_mensal_grava_as_frentes(base, api, cliente):
    api.responder("frentes", carregar("frentes"))
    api.responder("frentes/55703", carregar("frente"))
    api.responder("frentes/55703/membros", carregar("frente_membros_manual"))
    rotinas.mensal(cliente)
    assert base.session.get(Frente, 55703) is not None


# ======================================================
# DECISAO 12.1: UMA COLETA POR VEZ
# ======================================================
def test_trava_segura_a_segunda_coleta(tmp_path):
    caminho = str(tmp_path / "sub" / "coletor.lock")
    assert trava.adquirir(caminho) is True
    assert trava.adquirir(caminho) is False
    dados = json.load(open(caminho, encoding="utf-8"))
    assert dados["pid"] == os.getpid() and dados["inicio"]
    trava.liberar(caminho)
    assert trava.adquirir(caminho) is True


def test_liberar_sem_trava_nao_da_erro(tmp_path):
    trava.liberar(str(tmp_path / "coletor.lock"))


def test_trava_com_mais_de_6_horas_e_abandonada(tmp_path):
    caminho = str(tmp_path / "coletor.lock")
    inicio = datetime(2026, 10, 30, 8, 0)
    assert trava.adquirir(caminho, inicio)
    assert trava.adquirir(caminho, inicio + timedelta(hours=5, minutes=59)) is False
    assert trava.adquirir(caminho, inicio + timedelta(hours=6, minutes=1)) is True


def test_trava_ilegivel_e_abandonada(tmp_path):
    caminho = tmp_path / "coletor.lock"
    caminho.write_text("nao e json")
    assert trava.adquirir(str(caminho)) is True


# ======================================================
# COMANDOS DE VERDADE, COM RESPOSTAS GRAVADAS
# ======================================================
@pytest.fixture
def comandos(app, db, api, esperas, monkeypatch, tmp_path):
    caminho = str(tmp_path / "coletor.lock")
    monkeypatch.setattr(
        modulo_cli, "_cliente", lambda: ClienteCamara("https://api.falsa/api/v2", sessao=api, dormir=esperas.append)
    )
    monkeypatch.setattr(modulo_cli, "_caminho_trava", lambda: caminho)
    runner = app.test_cli_runner()
    runner.caminho_trava = caminho
    return runner


def test_comando_base_e_proposicoes_gravam_no_banco(comandos, db, api):
    _apoio(api)
    _proposicao(api)
    assert comandos.invoke(args=["coletar", "base"]).exit_code == 0
    resultado = comandos.invoke(
        args=["coletar", "proposicoes", "--inicio", "2026-10-30", "--fim", "2026-10-30", "--sigla-tipo", "PEC"]
    )
    assert resultado.exit_code == 0, resultado.output
    assert db.session.get(Proposicao, ID_PROPOSICAO) is not None
    assert db.session.scalars(db.select(ProposicaoAutor)).first() is not None
    assert dict(api.chamadas)["proposicoes"]["siglaTipo"] == "PEC"
    coleta = _coletas(db)[-1]
    assert (coleta.tipo, coleta.status) == ("completa", "ok")
    assert not os.path.exists(comandos.caminho_trava)


def test_comando_horaria(comandos, db, api):
    _apoio(api)
    _proposicao(api)
    _evento(api)
    _votacao(api)
    comandos.invoke(args=["coletar", "base"])
    resultado = comandos.invoke(args=["coletar", "horaria"])
    assert resultado.exit_code == 0, resultado.output
    assert db.session.scalars(db.select(Voto)).first() is not None


def test_comando_com_trava_nao_roda_e_avisa(comandos, db, api):
    assert trava.adquirir(comandos.caminho_trava)
    resultado = comandos.invoke(args=["coletar", "horaria"])
    assert resultado.exit_code == 0
    assert "Outra coleta" in resultado.output
    assert api.chamadas == []
    aviso = db.session.scalar(db.select(LogSistema).where(LogSistema.acao == "coleta_em_andamento"))
    assert aviso.nivel == "aviso" and aviso.modulo == "coletor"
    # A trava continua sendo de quem criou
    assert os.path.exists(comandos.caminho_trava)


def test_erro_no_comando_libera_a_trava(comandos, api, monkeypatch):
    def quebrar(*args, **kwargs):
        raise ZeroDivisionError

    monkeypatch.setattr(rotinas, "horaria", quebrar)
    resultado = comandos.invoke(args=["coletar", "horaria"])
    assert isinstance(resultado.exception, ZeroDivisionError)
    assert not os.path.exists(comandos.caminho_trava)


def test_sigterm_libera_a_trava_e_fecha_a_coleta(comandos, db, api, monkeypatch):
    """timeout e kill mandam SIGTERM: a coleta nao pode deixar a trava para tras."""

    def receber_sinal(params):
        os.kill(os.getpid(), signal.SIGTERM)

    api.responder("proposicoes", receber_sinal)
    resultado = comandos.invoke(args=["coletar", "proposicoes", "--inicio", "2026-10-30", "--fim", "2026-10-30"])
    assert resultado.exit_code == 128 + signal.SIGTERM
    assert not os.path.exists(comandos.caminho_trava)
    coleta = _coletas(db)[-1]
    assert coleta.status == "erro" and coleta.finalizado_em is not None


def test_relatorio_nao_precisa_da_trava(comandos, db):
    assert trava.adquirir(comandos.caminho_trava)
    resultado = comandos.invoke(args=["coletar", "relatorio"])
    assert resultado.exit_code == 0
    assert "blocos com id errado" in resultado.output
    assert relatorio.avisos_por_tipo() == []
