from desperta.parlamentares.models import Bloco, BlocoPartido

from .execucao import Execucao
from .normalizacao import agora_utc, para_bool, para_int
from .referencias import Referencias


def _partidos_da_legislatura(execucao, id_legislatura, cache):
    """Sigla -> ids, so nos partidos daquela legislatura: a sigla sozinha nao e unica."""
    if id_legislatura not in cache:
        siglas = {}
        params = {"idLegislatura": id_legislatura, "itens": 100}
        for partido in execucao.cliente.paginar("partidos", params):
            siglas.setdefault(partido.get("sigla"), []).append(partido.get("id"))
        cache[id_legislatura] = siglas
    return cache[id_legislatura]


def _id_do_partido(execucao, referencias, id_bloco, id_legislatura, item, cache):
    """
    Decisao 12.3: a API devolve em /blocos/{id}/partidos o id do bloco no lugar do id do partido.
    Nesse caso, procura pela sigla entre os partidos da legislatura e so liga se achar exatamente um.
    """
    if item.get("id") != id_bloco:
        return referencias.partido(item.get("id"))
    encontrados = _partidos_da_legislatura(execucao, id_legislatura, cache).get(item.get("sigla"), [])
    if len(encontrados) == 1:
        return referencias.partido(encontrados[0])
    execucao.log(
        "aviso",
        "bloco_partido_sem_id",
        f"Sigla {item.get('sigla')}: {len(encontrados)} partidos na legislatura {id_legislatura}",
        entidade="bloco_partido",
        entidade_id=id_bloco,
    )
    return None


def _coletar_um(execucao, referencias, item, cache):
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
    partidos = execucao.cliente.obter(f"blocos/{id_bloco}/partidos") or []
    if any(partido.get("id") == id_bloco for partido in partidos):
        execucao.log(
            "aviso",
            "bloco_partido_id_errado",
            "A API devolveu o id do bloco nos partidos",
            entidade="bloco",
            entidade_id=id_bloco,
        )
    for partido in partidos:
        id_partido = _id_do_partido(execucao, referencias, id_bloco, bloco.id_legislatura, partido, cache)
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
        cache = {}
        for item in list(cliente.paginar("blocos", params)):
            execucao.processar("bloco", item["id"], lambda item=item: _coletar_um(execucao, referencias, item, cache))
