import functools
import os
import signal
from datetime import date

import click
from flask import current_app
from flask.cli import AppGroup

from desperta.ext.db import db
from desperta.sistema.models import LogSistema

from . import blocos, deputados, eventos, frentes, legislaturas, liderancas, orgaos, partidos, proposicoes
from . import relatorio, rotinas, temas, trava, votacoes
from .cliente import ClienteCamara

coletar = AppGroup("coletar", help="Coleta dados da API da Camara.")


def _cliente():
    return ClienteCamara(current_app.config["CAMARA_API_URL"], timeout=current_app.config["CAMARA_TIMEOUT"])


def _caminho_trava():
    return os.path.join(current_app.instance_path, "coletor.lock")


def _avisar(acao, descricao):
    db.session.add(LogSistema(nivel="aviso", modulo="coletor", acao=acao, descricao=descricao))
    db.session.commit()


def _uma_coleta_por_vez(funcao):
    """Decisoes 12.1 e 13.6: com outra coleta rodando, este comando nao roda e deixa um aviso no log."""

    @functools.wraps(funcao)
    def executar(*args, **kwargs):
        caminho = _caminho_trava()

        def trava_abandonada(motivo):
            _avisar("trava_abandonada", f"Trava {caminho} removida: {motivo}")

        if not trava.adquirir(caminho, ao_abandonar=trava_abandonada):
            _avisar("coleta_em_andamento", f"{funcao.__name__} nao rodou: existe a trava {caminho}")
            click.echo("Outra coleta esta rodando; nada foi feito.")
            return
        sinal_anterior = trava.sair_limpo_em_sigterm()
        try:
            return funcao(*args, **kwargs)
        finally:
            signal.signal(signal.SIGTERM, sinal_anterior)
            trava.liberar(caminho)

    return executar


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
@_uma_coleta_por_vez
def coletar_base(legislatura):
    """Legislaturas, partidos, deputados, orgaos e temas."""
    rotinas.base(_cliente(), legislatura)


@coletar.command("horaria")
@_uma_coleta_por_vez
def coletar_horaria():
    """Proposicoes (1 dia), eventos e votacoes (ontem e hoje)."""
    rotinas.horaria(_cliente())


@coletar.command("diaria")
@_uma_coleta_por_vez
def coletar_diaria():
    """Proposicoes dos ultimos 3 dias, pautas e votacoes pendentes."""
    rotinas.diaria(_cliente())


@coletar.command("semanal")
@_uma_coleta_por_vez
def coletar_semanal():
    """Varredura de 30 dias, tabelas de apoio, cargos em orgaos, Mesa, liderancas e blocos."""
    rotinas.semanal(_cliente())


@coletar.command("mensal")
@_uma_coleta_por_vez
def coletar_mensal():
    """Frentes."""
    rotinas.mensal(_cliente())


# ------------------------------------------------------
# UM RECURSO POR VEZ
# ------------------------------------------------------
@coletar.command("legislaturas")
@_uma_coleta_por_vez
def coletar_legislaturas():
    legislaturas.coletar(_cliente())


@coletar.command("temas")
@_uma_coleta_por_vez
def coletar_temas():
    temas.coletar(_cliente())


@coletar.command("orgaos")
@_uma_coleta_por_vez
def coletar_orgaos():
    orgaos.coletar(_cliente())


@coletar.command("partidos")
@_legislatura
@_uma_coleta_por_vez
def coletar_partidos(legislatura):
    cliente = _cliente()
    partidos.coletar(cliente, legislatura or legislaturas.id_atual(cliente))


@coletar.command("deputados")
@_legislatura
@_uma_coleta_por_vez
def coletar_deputados(legislatura):
    cliente = _cliente()
    deputados.coletar(cliente, legislatura or legislaturas.id_atual(cliente))


@coletar.command("proposicoes")
@_janela
@click.option("--sigla-tipo", help="Ex.: PL, PEC.")
@click.option("--limite-pendentes", type=int, default=proposicoes.LIMITE_PENDENTES, show_default=True)
@_uma_coleta_por_vez
def coletar_proposicoes(inicio, fim, sigla_tipo, limite_pendentes):
    proposicoes.coletar(
        _cliente(), inicio, fim, sigla_tipo=sigla_tipo, tipo=_tipo(inicio), limite_pendentes=limite_pendentes
    )


@coletar.command("eventos")
@_janela
@_uma_coleta_por_vez
def coletar_eventos(inicio, fim):
    eventos.coletar(_cliente(), inicio, fim, tipo=_tipo(inicio))


@coletar.command("eventos-pendentes")
@click.option("--limite", type=int, default=eventos.LIMITE_PENDENTES, show_default=True)
@_uma_coleta_por_vez
def coletar_eventos_pendentes(limite):
    eventos.coletar_pendentes(_cliente(), limite)


@coletar.command("votacoes")
@_janela
@_uma_coleta_por_vez
def coletar_votacoes(inicio, fim):
    votacoes.coletar(_cliente(), inicio, fim, tipo=_tipo(inicio))


@coletar.command("membros")
@click.option("--limite", type=int, help="Maximo de orgaos nesta execucao.")
@_uma_coleta_por_vez
def coletar_membros(limite):
    orgaos.coletar_membros(_cliente(), limite)


@coletar.command("mesa")
@_legislatura
@_uma_coleta_por_vez
def coletar_mesa(legislatura):
    cliente = _cliente()
    orgaos.coletar_mesa(cliente, legislatura or legislaturas.id_atual(cliente))


@coletar.command("liderancas")
@_legislatura
@_uma_coleta_por_vez
def coletar_liderancas(legislatura):
    cliente = _cliente()
    liderancas.coletar(cliente, legislatura or legislaturas.id_atual(cliente))


@coletar.command("blocos")
@_legislatura
@_uma_coleta_por_vez
def coletar_blocos(legislatura):
    cliente = _cliente()
    blocos.coletar(cliente, legislatura or legislaturas.id_atual(cliente))


@coletar.command("frentes")
@_legislatura
@_uma_coleta_por_vez
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
    click.echo("\nfalha da API | total")
    for falha, total in relatorio.falhas_da_api():
        click.echo(f"{falha} | {total}")
    click.echo("\naviso | total")
    for acao, total in relatorio.avisos_por_tipo():
        click.echo(f"{acao} | {total}")
    com_id_errado, sem_ligacao = relatorio.blocos_com_id_errado()
    click.echo(f"\nblocos com id errado: {com_id_errado}; siglas sem ligacao: {sem_ligacao}")
    pendentes, repetidas = relatorio.proposicoes_pendentes()
    click.echo(f"proposicoes pendentes: {pendentes}; com falha repetida: {repetidas}")


def init_app(app):
    app.cli.add_command(coletar)
