from desperta.ext.db import db
from desperta.proposicoes.models import Proposicao, ProposicaoAutor, ProposicaoTema, Tema, Tramitacao

from .execucao import Execucao
from .janelas import dividir_janela, janela_incremental
from .normalizacao import agora_utc, id_da_uri, opcional, para_bool, para_data_hora
from .referencias import Referencias

LIMITE_PENDENTES = 200


def gravar_proposicao(execucao, item, referencias=None):
    """Recebe o item de /proposicoes/{id}, com statusProposicao achatado."""
    status = item.get("statusProposicao") or {}
    return execucao.principal(
        Proposicao,
        item["id"],
        {
            "id": item["id"],
            "sigla_tipo": item.get("siglaTipo"),
            "cod_tipo": item.get("codTipo"),
            "descricao_tipo": item.get("descricaoTipo"),
            "numero": item.get("numero"),
            "ano": item.get("ano"),
            "ementa": item.get("ementa"),
            "ementa_detalhada": opcional(item.get("ementaDetalhada")),
            "keywords": opcional(item.get("keywords")),
            "data_apresentacao": para_data_hora(item.get("dataApresentacao")),
            "url_inteiro_teor": item.get("urlInteiroTeor"),
            "cod_situacao": status.get("codSituacao"),
            "situacao": opcional(status.get("descricaoSituacao")),
            "data_status": para_data_hora(status.get("dataHora")),
            "regime": status.get("regime"),
            "apreciacao": status.get("apreciacao"),
        },
    )


def _gravar_autores(execucao, referencias, id_proposicao):
    for item in execucao.cliente.obter(f"proposicoes/{id_proposicao}/autores") or []:
        ordem = item.get("ordemAssinatura")
        execucao.vinculo(
            ProposicaoAutor,
            (id_proposicao, ordem),
            {
                "proposicao_id": id_proposicao,
                "ordem": ordem,
                # Nulo se o autor nao e deputado (a uri aponta para outro recurso)
                "deputado_id": referencias.deputado(id_da_uri(item.get("uri"), "deputados")),
                "nome": item.get("nome"),
                "cod_tipo": item.get("codTipo"),
                "tipo": item.get("tipo"),
                "proponente": para_bool(item.get("proponente")),
            },
        )


def _gravar_temas(execucao, id_proposicao):
    for item in execucao.cliente.obter(f"proposicoes/{id_proposicao}/temas") or []:
        cod_tema = item.get("codTema")
        if db.session.get(Tema, cod_tema) is None:
            execucao.log(
                "aviso",
                "tema_desconhecido",
                f"Tema {cod_tema} nao esta em /referencias/proposicoes/codTema",
                entidade="tema",
                entidade_id=cod_tema,
            )
            continue
        execucao.vinculo(
            ProposicaoTema,
            (id_proposicao, cod_tema),
            {
                "proposicao_id": id_proposicao,
                "cod_tema": cod_tema,
                "relevancia": item.get("relevancia"),
            },
        )


def _gravar_tramitacoes(execucao, referencias, id_proposicao):
    for item in execucao.cliente.obter(f"proposicoes/{id_proposicao}/tramitacoes") or []:
        sequencia = item.get("sequencia")
        execucao.vinculo(
            Tramitacao,
            (id_proposicao, sequencia),
            {
                "proposicao_id": id_proposicao,
                "sequencia": sequencia,
                "data_hora": para_data_hora(item.get("dataHora")),
                "orgao_id": referencias.orgao(id_da_uri(item.get("uriOrgao"), "orgaos")),
                "sigla_orgao": item.get("siglaOrgao"),
                "cod_tipo_tramitacao": item.get("codTipoTramitacao"),
                "descricao": item.get("descricaoTramitacao"),
                "cod_situacao": item.get("codSituacao"),
                "situacao": opcional(item.get("descricaoSituacao")),
                "despacho": item.get("despacho"),
                "regime": item.get("regime"),
                "ambito": item.get("ambito"),
                "apreciacao": item.get("apreciacao"),
                "url": opcional(item.get("url")),
            },
        )


def _coletar_uma(execucao, referencias, id_proposicao):
    """Grava a proposicao so depois do detalhe; a listagem serve apenas para descobrir ids."""
    proposicao = gravar_proposicao(execucao, execucao.cliente.obter(f"proposicoes/{id_proposicao}"))
    if proposicao is None:
        return
    falhas_antes = execucao.falhas
    _gravar_autores(execucao, referencias, id_proposicao)
    _gravar_temas(execucao, id_proposicao)
    _gravar_tramitacoes(execucao, referencias, id_proposicao)
    if execucao.falhas == falhas_antes:
        for modelo in (ProposicaoAutor, ProposicaoTema, Tramitacao):
            execucao.remover_sumidos(modelo, modelo.proposicao_id == id_proposicao)
    proposicao.filhos_sincronizados_em = agora_utc()


def _ids_pendentes(limite, ja_vistos):
    consulta = (
        db.select(Proposicao.id)
        .where(Proposicao.filhos_sincronizados_em.is_(None), Proposicao.id.not_in(ja_vistos))
        .order_by(Proposicao.id)
        .limit(limite)
    )
    return list(db.session.scalars(consulta))


def coletar(cliente, inicio=None, fim=None, sigla_tipo=None, tipo="incremental", limite_pendentes=LIMITE_PENDENTES):
    if inicio is None or fim is None:
        inicio, fim = janela_incremental("proposicoes")
    # A janela concluida fica registrada: se a coleta parar, a proxima retoma daqui
    for inicio_janela, fim_janela in dividir_janela(inicio, fim):
        params = {
            "dataInicio": inicio_janela.isoformat(),
            "dataFim": fim_janela.isoformat(),
            "ordem": "ASC",
            "ordenarPor": "id",
            "itens": 100,
        }
        if sigla_tipo:
            params["siglaTipo"] = sigla_tipo
        with Execucao(cliente, "proposicoes", tipo, "/proposicoes", params, inicio_janela, fim_janela) as execucao:
            referencias = Referencias(execucao)
            ids = [item["id"] for item in cliente.paginar("proposicoes", params)]
            for id_proposicao in ids + _ids_pendentes(limite_pendentes, ids):
                execucao.processar(
                    "proposicao",
                    id_proposicao,
                    lambda id_proposicao=id_proposicao: _coletar_uma(execucao, referencias, id_proposicao),
                )
