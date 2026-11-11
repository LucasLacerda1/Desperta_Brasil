from datetime import datetime, timedelta, timezone

from flask import current_app

from desperta.ext.api import iso
from desperta.ext.db import db
from desperta.ext.erros import DadosInvalidos

from .models import COLETA_STATUS, LOG_MODULOS, LOG_NIVEIS, Coleta, LogSistema


def ultima_coleta_concluida(recurso=None):
    """Data da ultima coleta com status ok (RNF05), geral ou de um recurso; None se nao houver."""
    consulta = db.select(db.func.max(Coleta.finalizado_em)).where(Coleta.status == "ok")
    if recurso is not None:
        consulta = consulta.where(Coleta.recurso == recurso)
    return db.session.scalar(consulta)


def situacao_dos_dados(agora=None):
    """RNF05: data da ultima coleta concluida e se o portal deve avisar que os dados podem estar desatualizados."""
    agora = agora or datetime.now(timezone.utc).replace(tzinfo=None)
    ultima = ultima_coleta_concluida()
    limite = timedelta(hours=current_app.config["AVISO_DESATUALIZADO_HORAS"])
    desatualizados = ultima is None or agora - ultima > limite
    return {
        "ultima_coleta_concluida": iso(ultima),
        "dados_desatualizados": desatualizados,
        "aviso": (
            "Os dados podem estar desatualizados: a última coleta na Câmara foi há mais de "
            f"{current_app.config['AVISO_DESATUALIZADO_HORAS']} horas."
            if desatualizados
            else None
        ),
    }


def _conferir(valor, permitidos, nome):
    if valor is not None and valor not in permitidos:
        raise DadosInvalidos(f"{nome} invalido: use {', '.join(permitidos)}.")
    return valor


def _paginar(consulta, ordem, pagina, por_pagina):
    total = db.session.scalar(db.select(db.func.count()).select_from(consulta.subquery()))
    itens = db.session.scalars(consulta.order_by(*ordem).offset((pagina - 1) * por_pagina).limit(por_pagina)).all()
    return itens, total


def listar_coletas(status=None, recurso=None, pagina=1, por_pagina=20):
    consulta = db.select(Coleta)
    if _conferir(status, COLETA_STATUS, "Status") is not None:
        consulta = consulta.where(Coleta.status == status)
    if recurso is not None:
        consulta = consulta.where(Coleta.recurso == recurso)
    return _paginar(consulta, (Coleta.id.desc(),), pagina, por_pagina)


def como_coleta(coleta):
    return {
        "id": coleta.id,
        "recurso": coleta.recurso,
        "tipo": coleta.tipo,
        "endpoint": coleta.endpoint,
        "parametros": coleta.parametros,
        "iniciado_em": iso(coleta.iniciado_em),
        "finalizado_em": iso(coleta.finalizado_em),
        "status": coleta.status,
        "total_itens": coleta.total_itens,
        "itens_novos": coleta.itens_novos,
        "itens_atualizados": coleta.itens_atualizados,
        "requisicoes": coleta.requisicoes,
        "erros_http": coleta.erros_http,
        "mensagem_erro": coleta.mensagem_erro,
    }


def listar_log(nivel=None, modulo=None, coleta_id=None, pagina=1, por_pagina=20):
    consulta = db.select(LogSistema)
    if _conferir(nivel, LOG_NIVEIS, "Nivel") is not None:
        consulta = consulta.where(LogSistema.nivel == nivel)
    if _conferir(modulo, LOG_MODULOS, "Modulo") is not None:
        consulta = consulta.where(LogSistema.modulo == modulo)
    if coleta_id is not None:
        consulta = consulta.where(LogSistema.coleta_id == coleta_id)
    return _paginar(consulta, (LogSistema.id.desc(),), pagina, por_pagina)


def como_log(registro):
    return {
        "id": registro.id,
        "data_hora": iso(registro.data_hora),
        "nivel": registro.nivel,
        "modulo": registro.modulo,
        "acao": registro.acao,
        "descricao": registro.descricao,
        "admin_id": registro.admin_id,
        "coleta_id": registro.coleta_id,
        "entidade": registro.entidade,
        "entidade_id": registro.entidade_id,
    }
