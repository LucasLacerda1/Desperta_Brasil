from datetime import date

import click
from flask import current_app
from flask.cli import AppGroup

from . import blocos, deputados, eventos, frentes, legislaturas, liderancas, orgaos, partidos, proposicoes
from . import relatorio, rotinas, temas, votacoes
from .cliente import ClienteCamara

coletar = AppGroup("coletar", help="Coleta dados da API da Camara.")


def _cliente():
    return ClienteCamara(current_app.config["CAMARA_API_URL"], timeout=current_app.config["CAMARA_TIMEOUT"])


def _data(ctx, param, valor):
    return date.fromisoformat(valor) if valor else None


def _janela(funcao):
    funcao = click.option("--fim", callback=_data, help="Fim da janela (AAAA-MM-DD).")(funcao)
    return click.option("--inicio", callback=_data, help="Inicio da janela (AAAA-MM-DD).")(funcao)


def _legislatura(funcao):
    return click.option("--legislatura", type=int, help="Id da legislatura (padrao: a atual).")(funcao)


def _tipo(inicio):
    return "completa" if inicio else "incremental"


# ------------------------------------------------------
# ROTINAS DO RF02 (para o agendador)
# ------------------------------------------------------
@coletar.command("base")
@_legislatura
def coletar_base(legislatura):
    """Legislaturas, partidos, deputados, orgaos e temas."""
    rotinas.base(_cliente(), legislatura)


@coletar.command("horaria")
def coletar_horaria():
    """Proposicoes, eventos e votacoes desde a ultima janela concluida."""
    rotinas.horaria(_cliente())


@coletar.command("diaria")
def coletar_diaria():
    """Varredura completa dos ultimos 30 dias."""
    rotinas.diaria(_cliente())


@coletar.command("semanal")
def coletar_semanal():
    """Cargos em orgaos, Mesa, liderancas e blocos."""
    rotinas.semanal(_cliente())


@coletar.command("mensal")
def coletar_mensal():
    """Frentes."""
    rotinas.mensal(_cliente())


# ------------------------------------------------------
# UM RECURSO POR VEZ
# ------------------------------------------------------
@coletar.command("legislaturas")
def coletar_legislaturas():
    legislaturas.coletar(_cliente())


@coletar.command("temas")
def coletar_temas():
    temas.coletar(_cliente())


@coletar.command("orgaos")
def coletar_orgaos():
    orgaos.coletar(_cliente())


@coletar.command("partidos")
@_legislatura
def coletar_partidos(legislatura):
    cliente = _cliente()
    partidos.coletar(cliente, legislatura or legislaturas.id_atual(cliente))


@coletar.command("deputados")
@_legislatura
def coletar_deputados(legislatura):
    cliente = _cliente()
    deputados.coletar(cliente, legislatura or legislaturas.id_atual(cliente))


@coletar.command("proposicoes")
@_janela
@click.option("--sigla-tipo", help="Ex.: PL, PEC.")
@click.option("--limite-pendentes", type=int, default=proposicoes.LIMITE_PENDENTES, show_default=True)
def coletar_proposicoes(inicio, fim, sigla_tipo, limite_pendentes):
    proposicoes.coletar(
        _cliente(), inicio, fim, sigla_tipo=sigla_tipo, tipo=_tipo(inicio), limite_pendentes=limite_pendentes
    )


@coletar.command("eventos")
@_janela
def coletar_eventos(inicio, fim):
    eventos.coletar(_cliente(), inicio, fim, tipo=_tipo(inicio))


@coletar.command("eventos-pendentes")
@click.option("--limite", type=int, default=eventos.LIMITE_PENDENTES, show_default=True)
def coletar_eventos_pendentes(limite):
    eventos.coletar_pendentes(_cliente(), limite)


@coletar.command("votacoes")
@_janela
def coletar_votacoes(inicio, fim):
    votacoes.coletar(_cliente(), inicio, fim, tipo=_tipo(inicio))


@coletar.command("membros")
@click.option("--limite", type=int, help="Maximo de orgaos nesta execucao.")
def coletar_membros(limite):
    orgaos.coletar_membros(_cliente(), limite)


@coletar.command("mesa")
@_legislatura
def coletar_mesa(legislatura):
    cliente = _cliente()
    orgaos.coletar_mesa(cliente, legislatura or legislaturas.id_atual(cliente))


@coletar.command("liderancas")
@_legislatura
def coletar_liderancas(legislatura):
    cliente = _cliente()
    liderancas.coletar(cliente, legislatura or legislaturas.id_atual(cliente))


@coletar.command("blocos")
@_legislatura
def coletar_blocos(legislatura):
    cliente = _cliente()
    blocos.coletar(cliente, legislatura or legislaturas.id_atual(cliente))


@coletar.command("frentes")
@_legislatura
def coletar_frentes(legislatura):
    cliente = _cliente()
    frentes.coletar(cliente, legislatura or legislaturas.id_atual(cliente))


# ------------------------------------------------------
# RELATORIO DA CARGA DE VALIDACAO
# ------------------------------------------------------
@coletar.command("relatorio")
def coletar_relatorio():
    """Colunas que falharam e instabilidade da API, a partir de coleta e log_sistema."""
    click.echo("recurso | coletas | requisicoes | erros_http | itens | novos")
    for linha in relatorio.resumo_por_recurso():
        click.echo(" | ".join(str(valor) for valor in linha))
    click.echo("\ncoluna | falhas")
    for coluna, total in relatorio.falhas_por_coluna():
        click.echo(f"{coluna} | {total}")


def init_app(app):
    app.cli.add_command(coletar)
