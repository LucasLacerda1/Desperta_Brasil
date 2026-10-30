from datetime import date, timedelta

from . import (
    blocos,
    deputados,
    eventos,
    frentes,
    legislaturas,
    liderancas,
    orgaos,
    partidos,
    proposicoes,
    temas,
    votacoes,
)

JANELA_COMPLETA_DIAS = 30


def base(cliente, id_legislatura=None):
    """Tabelas de apoio, na ordem das FKs."""
    legislaturas.coletar(cliente)
    id_legislatura = id_legislatura or legislaturas.id_atual(cliente)
    partidos.coletar(cliente, id_legislatura)
    deputados.coletar(cliente, id_legislatura)
    orgaos.coletar(cliente)
    temas.coletar(cliente)
    return id_legislatura


def horaria(cliente):
    """RF02: proposicoes, votacoes e eventos, desde a ultima janela concluida."""
    proposicoes.coletar(cliente)
    eventos.coletar(cliente)
    votacoes.coletar(cliente)
    eventos.coletar_pendentes(cliente)


def diaria(cliente, hoje=None):
    """RF02: varredura completa, a noite."""
    hoje = hoje or date.today()
    inicio = hoje - timedelta(days=JANELA_COMPLETA_DIAS)
    base(cliente)
    proposicoes.coletar(cliente, inicio, hoje, tipo="completa")
    eventos.coletar(cliente, inicio, hoje, tipo="completa")
    votacoes.coletar(cliente, inicio, hoje, tipo="completa")
    eventos.coletar_pendentes(cliente)


def semanal(cliente):
    """RF02: cargos em orgaos, Mesa, liderancas e blocos."""
    id_legislatura = legislaturas.id_atual(cliente)
    orgaos.coletar_membros(cliente)
    orgaos.coletar_mesa(cliente, id_legislatura)
    liderancas.coletar(cliente, id_legislatura)
    blocos.coletar(cliente, id_legislatura)


def mensal(cliente):
    """RF02: frentes."""
    frentes.coletar(cliente, legislaturas.id_atual(cliente))
