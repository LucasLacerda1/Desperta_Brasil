"""
Auxiliares HTTP comuns as rotas: corpo JSON, parametros da URL, paginas e datas.

As rotas so cuidam do HTTP (padrao do TaskFlow); as regras ficam nos services.
"""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from flask import current_app, request

from desperta.ext.erros import DadosInvalidos

POR_PAGINA_PADRAO = 20
POR_PAGINA_MAXIMO = 100
BRASILIA = ZoneInfo("America/Sao_Paulo")


def corpo_json(obrigatorio=True):
    """
    Corpo da requisicao como dicionario. Exigir JSON tambem protege as rotas que mudam dados:
    um formulario de outro site nao consegue mandar application/json sem passar pelo CORS.
    """
    if not request.is_json:
        if obrigatorio:
            raise DadosInvalidos("Envie os dados em JSON (Content-Type: application/json).")
        return {}
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        raise DadosInvalidos("O corpo precisa ser um objeto JSON.")
    return dados


def parametro_int(nome, padrao=None, minimo=None, maximo=None):
    valor = request.args.get(nome)
    if valor in (None, ""):
        return padrao
    try:
        numero = int(valor)
    except ValueError:
        raise DadosInvalidos(f"O parametro '{nome}' precisa ser um numero inteiro.") from None
    if (minimo is not None and numero < minimo) or (maximo is not None and numero > maximo):
        raise DadosInvalidos(f"O parametro '{nome}' esta fora do intervalo permitido.")
    return numero


def parametro_texto(nome, tamanho=200):
    valor = (request.args.get(nome) or "").strip()
    if len(valor) > tamanho:
        raise DadosInvalidos(f"O parametro '{nome}' passa de {tamanho} caracteres.")
    return valor or None


def pagina():
    """(pagina, por_pagina) a partir de ?pagina= e ?por_pagina=."""
    return (
        parametro_int("pagina", 1, minimo=1),
        parametro_int("por_pagina", POR_PAGINA_PADRAO, minimo=1, maximo=POR_PAGINA_MAXIMO),
    )


def paginado(itens, total, pagina_atual, por_pagina):
    return {
        "itens": itens,
        "pagina": pagina_atual,
        "por_pagina": por_pagina,
        "total": total,
        "paginas": (total + por_pagina - 1) // por_pagina,
    }


def iso(valor):
    """Datas do portal (noticia, coleta, log, equipe): gravadas em UTC, saem com o 'Z'."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(valor, date):
        return valor.isoformat()
    return valor


def iso_camara(valor):
    """Datas da Camara (proposicao, tramitacao, votacao): gravadas no horario de Brasilia, saem com -03:00."""
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=BRASILIA).isoformat()
    return iso(valor)


def periodo_em_utc(dia=None, mes=None, ano=None):
    """
    Filtro por dia, mes e ano em horario de Brasilia, convertido para UTC (Fase 4): publicado_em
    esta em UTC, e sem a conversao uma noticia publicada a noite cairia no dia seguinte.
    Devolve (inicio, fim) com fim exclusivo, ou (None, None) sem filtro.
    """
    if ano is None:
        if dia is not None or mes is not None:
            raise DadosInvalidos("Para filtrar por dia ou mes, informe tambem o ano.")
        return None, None
    if dia is not None and mes is None:
        raise DadosInvalidos("Para filtrar por dia, informe tambem o mes.")
    try:
        inicio = datetime(ano, mes or 1, dia or 1, tzinfo=BRASILIA)
    except ValueError:
        raise DadosInvalidos("Data invalida.") from None
    if dia is not None:
        fim = datetime.fromordinal(inicio.toordinal() + 1).replace(tzinfo=BRASILIA)
    elif mes is not None:
        fim = datetime(ano + (mes == 12), mes % 12 + 1, 1, tzinfo=BRASILIA)
    else:
        fim = datetime(ano + 1, 1, 1, tzinfo=BRASILIA)

    def para_utc(momento):
        return momento.astimezone(timezone.utc).replace(tzinfo=None)

    return para_utc(inicio), para_utc(fim)


def url_camara(caminho):
    return f"{current_app.config['CAMARA_API_URL']}/{caminho}"
