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

# Calendario da decisao 12.1 (RF02)
DIAS_DIARIA = 3
DIAS_SEMANAL = 30
# A horaria tem meta de 20 minutos: pendentes ficam para a diaria
LIMITE_EVENTOS_HORARIA = 20
# Decisao 14.2: a diaria da madrugada confere de novo o que a horaria pular
ORCAMENTO_HORARIA_SEGUNDOS = 20 * 60
RECONFERIR_HORARIA_DEPOIS = timedelta(hours=6)


def base(cliente, id_legislatura=None):
    """Tabelas de apoio, na ordem das FKs."""
    legislaturas.coletar(cliente)
    id_legislatura = id_legislatura or legislaturas.id_atual(cliente)
    partidos.coletar(cliente, id_legislatura)
    deputados.coletar(cliente, id_legislatura)
    orgaos.coletar(cliente)
    temas.coletar(cliente)
    return id_legislatura


def horaria(cliente, hoje=None):
    """
    Votacoes e eventos de ontem e hoje; por ultimo, proposicoes dos tipos acompanhados com janela de 1 dia.
    Ao fim do orcamento, a coleta em andamento e as seguintes fecham como parcial, sem itens.
    """
    hoje = hoje or date.today()
    ontem = hoje - timedelta(days=1)
    cliente.definir_orcamento(ORCAMENTO_HORARIA_SEGUNDOS)
    try:
        votacoes.coletar(cliente, ontem, hoje)
        eventos.coletar(cliente, ontem, hoje, limite_pendentes=LIMITE_EVENTOS_HORARIA)
        proposicoes.coletar(cliente, hoje, hoje, limite_pendentes=0, pular_conferidas_ha=RECONFERIR_HORARIA_DEPOIS)
    finally:
        cliente.definir_orcamento(None)


def diaria(cliente, hoje=None):
    """Proposicoes dos ultimos 3 dias, pautas pendentes e votacoes pendentes."""
    hoje = hoje or date.today()
    proposicoes.coletar(cliente, hoje - timedelta(days=DIAS_DIARIA), hoje)
    eventos.coletar_pendentes(cliente)
    votacoes.coletar_pendentes(cliente)


def semanal(cliente, hoje=None):
    """Varredura de 30 dias, cargos em orgaos, Mesa, liderancas e blocos."""
    hoje = hoje or date.today()
    id_legislatura = base(cliente)
    proposicoes.coletar(cliente, hoje - timedelta(days=DIAS_SEMANAL), hoje, tipo="completa")
    orgaos.coletar_membros(cliente)
    orgaos.coletar_mesa(cliente, id_legislatura)
    liderancas.coletar(cliente, id_legislatura)
    blocos.coletar(cliente, id_legislatura)


def mensal(cliente):
    """Frentes."""
    frentes.coletar(cliente, legislaturas.id_atual(cliente))
