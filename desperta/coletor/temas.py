from desperta.proposicoes.models import ICONES_TEMA, Tema

from .execucao import Execucao
from .normalizacao import para_int

ICONE_PADRAO = "article"


def coletar(cliente):
    with Execucao(cliente, "temas", "completa", "/referencias/proposicoes/codTema") as execucao:
        for item in cliente.obter("referencias/proposicoes/codTema"):
            cod_tema = para_int(item["cod"])
            execucao.principal(
                Tema,
                cod_tema,
                {
                    "cod_tema": cod_tema,
                    "nome": item.get("nome"),
                    "icone": ICONES_TEMA.get(cod_tema, ICONE_PADRAO),
                },
            )
        execucao.concluir_item()
