from desperta.ext.db import db
from desperta.orgaos.models import DeputadoOrgao, Orgao

from .execucao import Execucao
from .normalizacao import agora_utc, para_data, para_texto
from .referencias import Referencias

ID_MESA = 4


def gravar_orgao(execucao, item):
    """Serve para /orgaos, /orgaos/{id} e para a lista orgaos[] de /eventos (D5)."""
    return execucao.principal(
        Orgao,
        item["id"],
        {
            "id": item["id"],
            "sigla": item.get("sigla"),
            "nome": item.get("nome"),
            "apelido": item.get("apelido"),
            "cod_tipo_orgao": item.get("codTipoOrgao"),
            "tipo_orgao": item.get("tipoOrgao"),
        },
    )


def coletar(cliente):
    with Execucao(cliente, "orgaos", "completa", "/orgaos") as execucao:
        for item in list(cliente.paginar("orgaos", {"itens": 100})):
            gravar_orgao(execucao, item)
        execucao.concluir_item()


def _gravar_membro(execucao, referencias, id_orgao, item):
    """Devolve True se a linha foi gravada."""
    id_deputado = referencias.deputado(item.get("id"))
    if id_deputado is None:
        return False
    data_inicio = para_data(item.get("dataInicio"))
    return execucao.vinculo(
        DeputadoOrgao,
        (id_deputado, id_orgao, data_inicio),
        {
            "deputado_id": id_deputado,
            "orgao_id": id_orgao,
            "data_inicio": data_inicio,
            "cod_titulo": para_texto(item.get("codTitulo")),
            "titulo": item.get("titulo"),
            "data_fim": para_data(item.get("dataFim")),
        },
    )


def _coletar_membros_do_orgao(execucao, referencias, orgao):
    """Vinculos que sumiram da API saem do banco; se alguma linha falhou, nada e apagado."""
    falhas_antes = execucao.falhas
    for item in list(execucao.cliente.paginar(f"orgaos/{orgao.id}/membros", {"itens": 100})):
        _gravar_membro(execucao, referencias, orgao.id, item)
    if execucao.falhas == falhas_antes:
        execucao.remover_sumidos(DeputadoOrgao, DeputadoOrgao.orgao_id == orgao.id)
    orgao.filhos_sincronizados_em = agora_utc()


def coletar_membros(cliente, limite=None, ids=None):
    """Pendentes (nulo) primeiro, depois os sincronizados ha mais tempo."""
    with Execucao(cliente, "orgao_membros", "detalhe", "/orgaos/{id}/membros") as execucao:
        referencias = Referencias(execucao)
        consulta = (
            db.select(Orgao)
            .where(Orgao.id != ID_MESA)
            .order_by(Orgao.filhos_sincronizados_em.is_not(None), Orgao.filhos_sincronizados_em, Orgao.id)
        )
        if ids:
            consulta = consulta.where(Orgao.id.in_(ids))
        if limite:
            consulta = consulta.limit(limite)
        for orgao in db.session.scalars(consulta).all():
            execucao.processar(
                "orgao", orgao.id, lambda orgao=orgao: _coletar_membros_do_orgao(execucao, referencias, orgao)
            )


def coletar_mesa(cliente, id_legislatura):
    """A Mesa e o orgao 4, com membros vindos de /legislaturas/{id}/mesa."""
    caminho = f"legislaturas/{id_legislatura}/mesa"
    with Execucao(cliente, "mesa", "detalhe", f"/{caminho}") as execucao:
        referencias = Referencias(execucao)
        if referencias.orgao(ID_MESA) is None:
            raise RuntimeError("Orgao da Mesa (id 4) nao encontrado")
        for item in cliente.obter(caminho) or []:
            _gravar_membro(execucao, referencias, ID_MESA, item)
        db.session.get(Orgao, ID_MESA).filhos_sincronizados_em = agora_utc()
        execucao.concluir_item()
