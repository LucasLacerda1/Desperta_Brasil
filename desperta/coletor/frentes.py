from desperta.parlamentares.models import Frente, FrenteMembro

from .execucao import Execucao
from .normalizacao import agora_utc, opcional, para_data, para_texto
from .referencias import Referencias


def _coletar_uma(execucao, referencias, id_frente):
    item = execucao.cliente.obter(f"frentes/{id_frente}")
    frente = execucao.principal(
        Frente,
        id_frente,
        {
            "id": id_frente,
            "titulo": item.get("titulo"),
            "id_legislatura": item.get("idLegislatura"),
            "keywords": opcional(item.get("keywords")),
        },
    )
    if frente is None:
        return
    falhas_antes = execucao.falhas
    # Este endpoint recusa o parametro itens (HTTP 400)
    for membro in execucao.cliente.obter(f"frentes/{id_frente}/membros") or []:
        # Frentes mistas tem senadores: quem nao e deputado fica de fora
        id_deputado = referencias.deputado(membro.get("id"))
        if id_deputado is None:
            continue
        execucao.vinculo(
            FrenteMembro,
            (id_frente, id_deputado),
            {
                "frente_id": id_frente,
                "deputado_id": id_deputado,
                "cod_titulo": para_texto(membro.get("codTitulo")),
                "titulo": membro.get("titulo"),
                "data_inicio": para_data(membro.get("dataInicio")),
                "data_fim": para_data(membro.get("dataFim")),
            },
        )
    if execucao.falhas == falhas_antes:
        execucao.remover_sumidos(FrenteMembro, FrenteMembro.frente_id == id_frente)
    frente.filhos_sincronizados_em = agora_utc()


def coletar(cliente, id_legislatura):
    params = {"idLegislatura": id_legislatura, "itens": 100}
    with Execucao(cliente, "frentes", "completa", "/frentes", params) as execucao:
        referencias = Referencias(execucao)
        for item in list(cliente.paginar("frentes", params)):
            execucao.processar("frente", item["id"], lambda item=item: _coletar_uma(execucao, referencias, item["id"]))
