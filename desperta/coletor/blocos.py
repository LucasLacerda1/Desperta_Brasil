from desperta.ext.db import db
from desperta.parlamentares.models import Bloco, BlocoPartido, Partido

from .execucao import Execucao
from .normalizacao import agora_utc, para_bool, para_int
from .referencias import Referencias


def _id_do_partido(execucao, referencias, id_bloco, item):
    """
    A API devolve em /blocos/{id}/partidos o id do bloco no lugar do id do partido; so a sigla e confiavel.
    Como a sigla nao e unica, so liga se houver exatamente um partido com ela.
    """
    if item.get("id") != id_bloco:
        return referencias.partido(item.get("id"))
    encontrados = db.session.scalars(db.select(Partido.id).where(Partido.sigla == item.get("sigla"))).all()
    if len(encontrados) == 1:
        return encontrados[0]
    execucao.log(
        "aviso",
        "bloco_partido_sem_id",
        f"Sigla {item.get('sigla')}: {len(encontrados)} partidos encontrados",
        entidade="bloco_partido",
        entidade_id=id_bloco,
    )
    return None


def _coletar_um(execucao, referencias, item):
    id_bloco = para_int(item["id"])
    bloco = execucao.principal(
        Bloco,
        id_bloco,
        {
            "id": id_bloco,
            "nome": item.get("nome"),
            "federacao": para_bool(item.get("federacao")),
            "id_legislatura": para_int(item.get("idLegislatura")),
        },
    )
    if bloco is None:
        return
    falhas_antes = execucao.falhas
    for partido in execucao.cliente.obter(f"blocos/{id_bloco}/partidos") or []:
        id_partido = _id_do_partido(execucao, referencias, id_bloco, partido)
        if id_partido is not None:
            execucao.vinculo(BlocoPartido, (id_bloco, id_partido), {"bloco_id": id_bloco, "partido_id": id_partido})
    # bloco_partido guarda so a composicao atual
    if execucao.falhas == falhas_antes:
        execucao.remover_sumidos(BlocoPartido, BlocoPartido.bloco_id == id_bloco)
    bloco.filhos_sincronizados_em = agora_utc()


def coletar(cliente, id_legislatura):
    params = {"idLegislatura": id_legislatura, "itens": 100}
    with Execucao(cliente, "blocos", "completa", "/blocos", params) as execucao:
        referencias = Referencias(execucao)
        for item in list(cliente.paginar("blocos", params)):
            execucao.processar("bloco", item["id"], lambda item=item: _coletar_um(execucao, referencias, item))
