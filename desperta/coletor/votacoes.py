from desperta.ext.db import db
from desperta.orgaos.models import Evento
from desperta.parlamentares.models import Partido
from desperta.votacoes.models import Orientacao, Votacao, VotacaoProposicao, Voto

from .execucao import NOVO, Execucao
from .janelas import dividir_janela, janela_incremental
from .normalizacao import agora_utc, id_da_uri, para_bool, para_data, para_data_hora, para_int
from .referencias import Referencias


def _gravar_votacao(execucao, referencias, item):
    id_orgao = item.get("idOrgao") or id_da_uri(item.get("uriOrgao"), "orgaos")
    id_evento = item.get("idEvento") or id_da_uri(item.get("uriEvento"), "eventos")
    return execucao.principal(
        Votacao,
        item["id"],
        {
            "id": item["id"],
            "data": para_data(item.get("data")),
            "data_hora_registro": para_data_hora(item.get("dataHoraRegistro")),
            "evento_id": referencias.evento(id_evento),
            "orgao_id": referencias.orgao(id_orgao),
            "sigla_orgao": item.get("siglaOrgao"),
            # D2: sem uriProposicaoObjeto, fica nulo
            "proposicao_id": referencias.proposicao(id_da_uri(item.get("uriProposicaoObjeto"), "proposicoes")),
            "descricao": item.get("descricao"),
            "aprovacao": para_bool(item.get("aprovacao")),
        },
    )


def _gravar_votos(execucao, referencias, id_votacao):
    # Votacao simbolica tem /votos vazio; ausentes nao aparecem
    for item in execucao.cliente.obter(f"votacoes/{id_votacao}/votos") or []:
        dados = item.get("deputado_") or {}
        id_deputado = referencias.deputado(dados.get("id"))
        if id_deputado is None:
            continue
        execucao.vinculo(
            Voto,
            (id_votacao, id_deputado),
            {
                "votacao_id": id_votacao,
                "deputado_id": id_deputado,
                "tipo_voto": item.get("tipoVoto"),
                "data_registro": para_data_hora(item.get("dataRegistroVoto")),
                "sigla_partido": dados.get("siglaPartido"),
            },
        )


def _gravar_orientacoes(execucao, id_votacao):
    for item in execucao.cliente.obter(f"votacoes/{id_votacao}/orientacoes") or []:
        partido_bloco = item.get("siglaPartidoBloco")
        tipo_lideranca = item.get("codTipoLideranca")
        # Decisao 10.1: nao ligar ao bloco; partido_id so para P, se o partido existe
        partido_id = para_int(item.get("codPartidoBloco")) if tipo_lideranca == "P" else None
        if partido_id is not None and db.session.get(Partido, partido_id) is None:
            partido_id = None
        execucao.vinculo(
            Orientacao,
            (id_votacao, partido_bloco),
            {
                "votacao_id": id_votacao,
                "partido_bloco": partido_bloco,
                "tipo_lideranca": tipo_lideranca,
                "partido_id": partido_id,
                "orientacao": item.get("orientacaoVoto"),
            },
        )


def _gravar_afetadas(execucao, referencias, votacao, afetadas):
    # A proposicao objeto tambem entra em votacao_proposicao
    ids = {item.get("id") for item in afetadas or []}
    if votacao.proposicao_id:
        ids.add(votacao.proposicao_id)
    for id_afetada in sorted(i for i in ids if i):
        if referencias.proposicao(id_afetada) is not None:
            execucao.vinculo(
                VotacaoProposicao,
                (votacao.id, id_afetada),
                {
                    "votacao_id": votacao.id,
                    "proposicao_id": id_afetada,
                },
            )


def _coletar_uma(execucao, referencias, item):
    # O detalhe traz idOrgao, idEvento e proposicoesAfetadas; a listagem traz uriProposicaoObjeto
    detalhe = {**item, **(execucao.cliente.obter(f"votacoes/{item['id']}") or {})}
    votacao = _gravar_votacao(execucao, referencias, detalhe)
    if votacao is None:
        return
    falhas_antes = execucao.falhas
    _gravar_afetadas(execucao, referencias, votacao, detalhe.get("proposicoesAfetadas"))
    _gravar_votos(execucao, referencias, votacao.id)
    _gravar_orientacoes(execucao, votacao.id)
    if execucao.falhas == falhas_antes:
        for modelo in (Voto, Orientacao, VotacaoProposicao):
            execucao.remover_sumidos(modelo, modelo.votacao_id == votacao.id)
    votacao.filhos_sincronizados_em = agora_utc()
    # A pauta aponta para a votacao: com votacao nova, a pauta do evento precisa ser refeita
    if votacao.situacao_coleta == NOVO and votacao.evento_id:
        db.session.get(Evento, votacao.evento_id).filhos_sincronizados_em = None


def coletar(cliente, inicio=None, fim=None, tipo="incremental"):
    if inicio is None or fim is None:
        inicio, fim = janela_incremental("votacoes")
    for inicio_ano, fim_ano in dividir_janela(inicio, fim):
        params = {"dataInicio": inicio_ano.isoformat(), "dataFim": fim_ano.isoformat(), "itens": 100}
        with Execucao(cliente, "votacoes", tipo, "/votacoes", params, inicio_ano, fim_ano) as execucao:
            referencias = Referencias(execucao)
            for item in list(cliente.paginar("votacoes", params)):
                execucao.processar("votacao", item["id"], lambda item=item: _coletar_uma(execucao, referencias, item))
