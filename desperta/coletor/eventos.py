from datetime import timedelta

from desperta.ext.db import db
from desperta.orgaos.models import Evento, PautaItem
from desperta.votacoes.models import Votacao

from .execucao import Execucao
from .janelas import janela_incremental
from .normalizacao import agora_utc, id_texto_da_uri, opcional, para_data_hora
from .orgaos import gravar_orgao
from .referencias import Referencias

# Evento nestas situacoes nao muda mais; os demais sao recoletados
PREFIXOS_ENCERRADO = ("Encerrada", "Cancelada", "Cancelado", "Encerrado")
DIAS_RECOLETA = 30
LIMITE_PENDENTES = 200


def gravar_evento(execucao, item, referencias=None):
    """Recebe o item de /eventos/{id}; todos os orgaos da lista sao cadastrados (D5)."""
    orgaos = item.get("orgaos") or []
    for orgao in orgaos:
        gravar_orgao(execucao, orgao)
    local = item.get("localCamara") or {}
    return execucao.principal(
        Evento,
        item["id"],
        {
            "id": item["id"],
            "data_hora_inicio": para_data_hora(item.get("dataHoraInicio")),
            "data_hora_fim": para_data_hora(item.get("dataHoraFim")),
            "situacao": item.get("situacao"),
            "descricao_tipo": item.get("descricaoTipo"),
            "descricao": item.get("descricao"),
            # D1: o primeiro orgao da lista
            "orgao_id": orgaos[0]["id"] if orgaos else None,
            "local": opcional(local.get("nome")) or opcional(item.get("localExterno")),
            "url_registro": opcional(item.get("urlRegistro")),
            "url_documento_pauta": opcional(item.get("urlDocumentoPauta")),
        },
    )


def _votacao_do_mesmo_evento(id_evento, uri_votacao):
    """A votacao entra depois do evento: se ainda nao existe, a pauta e refeita quando ela chegar."""
    id_votacao = id_texto_da_uri(uri_votacao)
    votacao = db.session.get(Votacao, id_votacao) if id_votacao else None
    return id_votacao if votacao is not None and votacao.evento_id == id_evento else None


def _agrupar_por_ordem(itens):
    """A API repete o item com o mesmo ordem, uma linha por votacao; a PK guarda uma linha por item."""
    grupos = {}
    for item in itens:
        grupos.setdefault(item.get("ordem"), []).append(item)
    return grupos


def _gravar_pauta(execucao, referencias, id_evento):
    falhas_antes = execucao.falhas
    for ordem, repetidos in _agrupar_por_ordem(execucao.cliente.obter(f"eventos/{id_evento}/pauta") or []).items():
        item = repetidos[0]
        votacoes = [_votacao_do_mesmo_evento(id_evento, linha.get("uriVotacao")) for linha in repetidos]
        votacoes = [votacao for votacao in votacoes if votacao]
        if len(repetidos) > 1:
            # As outras votacoes continuam ligadas ao evento por votacao.evento_id
            execucao.log(
                "aviso",
                "pauta_ordem_repetida",
                f"Item {ordem} veio em {len(repetidos)} linhas; ficou uma so",
                entidade="pauta_item",
                entidade_id=(id_evento, ordem),
            )
        execucao.vinculo(
            PautaItem,
            (id_evento, ordem),
            {
                "evento_id": id_evento,
                "ordem": ordem,
                "proposicao_id": referencias.proposicao((item.get("proposicao_") or {}).get("id")),
                # Sem FK, de proposito
                "proposicao_relacionada_id": (item.get("proposicaoRelacionada_") or {}).get("id"),
                "relator_id": referencias.deputado((item.get("relator") or {}).get("id")),
                "regime": opcional(item.get("regime")),
                "situacao_item": opcional(item.get("situacaoItem")),
                "topico": opcional(item.get("topico")),
                "texto_parecer": opcional(item.get("textoParecer")),
                "votacao_id": votacoes[0] if votacoes else None,
            },
        )
    if execucao.falhas == falhas_antes:
        execucao.remover_sumidos(PautaItem, PautaItem.evento_id == id_evento)


def _coletar_um(execucao, referencias, id_evento):
    evento = gravar_evento(execucao, execucao.cliente.obter(f"eventos/{id_evento}"))
    if evento is None:
        return
    _gravar_pauta(execucao, referencias, id_evento)
    evento.filhos_sincronizados_em = agora_utc()


def _ids_para_recoletar(hoje_utc, ja_vistos, limite):
    """Pauta pendente (nulo) e eventos recentes que ainda nao foram encerrados."""
    encerrado = db.or_(*(Evento.situacao.startswith(prefixo) for prefixo in PREFIXOS_ENCERRADO))
    consulta = (
        db.select(Evento.id)
        .where(
            Evento.id.not_in(ja_vistos),
            db.or_(
                Evento.filhos_sincronizados_em.is_(None),
                db.and_(db.not_(encerrado), Evento.data_hora_inicio >= hoje_utc - timedelta(days=DIAS_RECOLETA)),
            ),
        )
        .order_by(Evento.filhos_sincronizados_em.is_not(None), Evento.filhos_sincronizados_em, Evento.id)
        .limit(limite)
    )
    return list(db.session.scalars(consulta))


def coletar(cliente, inicio=None, fim=None, tipo="incremental", limite_pendentes=LIMITE_PENDENTES):
    if inicio is None or fim is None:
        inicio, fim = janela_incremental("eventos")
    params = {"dataInicio": inicio.isoformat(), "dataFim": fim.isoformat(), "itens": 100}
    with Execucao(cliente, "eventos", tipo, "/eventos", params, inicio, fim) as execucao:
        referencias = Referencias(execucao)
        ids = [item["id"] for item in cliente.paginar("eventos", params)]
        for id_evento in ids + _ids_para_recoletar(agora_utc(), ids, limite_pendentes):
            execucao.processar(
                "evento", id_evento, lambda id_evento=id_evento: _coletar_um(execucao, referencias, id_evento)
            )


def coletar_pendentes(cliente, limite=LIMITE_PENDENTES):
    """Refaz as pautas pendentes, por exemplo depois de chegarem votacoes novas do evento."""
    with Execucao(cliente, "eventos", "detalhe", "/eventos/{id}") as execucao:
        referencias = Referencias(execucao)
        consulta = (
            db.select(Evento.id).where(Evento.filhos_sincronizados_em.is_(None)).order_by(Evento.id).limit(limite)
        )
        for id_evento in db.session.scalars(consulta).all():
            execucao.processar(
                "evento", id_evento, lambda id_evento=id_evento: _coletar_um(execucao, referencias, id_evento)
            )
